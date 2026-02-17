"""Bayesian agent that tracks all 54 cards and computes expected values dynamically."""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from game import Player
from agents.card_tracker import CardTracker, card_to_tuple, tuple_value


class BayesianAgent(Player):
    """Agent that maintains a full card tracker for EV-based decisions."""

    def __init__(self, name="BayesianAgent", discard_threshold=None, cambio_threshold=10,
                 cambio_margin=4, cambio_knowledge_gap=1, ev_dominance_margin=8):
        super().__init__(name)
        self.tracker = CardTracker()
        self.cambio_threshold = cambio_threshold
        self.cambio_margin = cambio_margin
        self.cambio_knowledge_gap = cambio_knowledge_gap
        self.ev_dominance_margin = ev_dominance_margin
        self._initialized = False
        self._last_discard_len = 0
        self._prev_discard_top = None  # Track discard top before each turn
        self.opponent_known = {}  # Bug fix A: {opp_player_index: {pos: Card}}

    def _ensure_initialized(self, game):
        """Lazy-initialize tracker on first interaction with the game."""
        if self._initialized:
            return
        opponent_names = [p.name for p in game.players if p.name != self.name]
        self.tracker.initialize(self.known, len(self.hand), opponent_names)
        # Sync the initial discard card
        self.tracker.sync_discard(game.discard)
        self._last_discard_len = len(game.discard)
        if game.discard:
            self._prev_discard_top = card_to_tuple(game.discard[-1])
        self._initialized = True

    def observe_turn(self, turn_data, game):
        """Core observation: update tracker from any player's turn."""
        self._ensure_initialized(game)

        # Capture prev discard top BEFORE syncing (used to infer discard-draw info)
        prev_top = self._prev_discard_top

        # Sync discard pile to pick up any new cards
        self.tracker.sync_discard(game.discard)
        self._last_discard_len = len(game.discard)
        # Update prev_discard_top for next turn
        if game.discard:
            self._prev_discard_top = card_to_tuple(game.discard[-1])
        else:
            self._prev_discard_top = None

        acting_player = turn_data['player']

        # Update opponent hand sizes
        for p in game.players:
            if p.name != self.name:
                self.tracker.update_opponent_hand_size(p.name, len(p.hand))

        # Update own hand tracking size
        if len(self.hand) != len(self.tracker.own_hand):
            self.tracker.update_own_hand_size(len(self.hand))

        # --- Bug fix A: Sync opponent_known into tracker ---
        for opp_id, positions in self.opponent_known.items():
            # opp_id is the player index; find the name
            if opp_id < len(game.players):
                opp_name = game.players[opp_id].name
                if opp_name != self.name:
                    for pos, card in positions.items():
                        self.tracker.set_opponent_card(opp_name, pos, card_to_tuple(card))

        # --- Process actions by OTHER players ---
        if acting_player != self.name:
            power_type = turn_data.get('power_type')
            action = turn_data.get('action')
            draw_source = turn_data.get('draw_source')
            swap_position = turn_data.get('swap_position')
            target_player = turn_data.get('power_target_player')
            target_pos = turn_data.get('power_target_position')

            # Opponent blind/king swapped US — clear our targeted position
            if power_type in ('blind_swap', 'king_swap'):
                if target_player == self.name and target_pos is not None:
                    self.tracker.own_card_swapped_out(target_pos)
                    if target_pos in self.known:
                        del self.known[target_pos]
                # Opponent-to-opponent swap: both positions become uncertain
                elif target_player is not None and target_player != self.name:
                    # The acting player's swap_position and target's position are both unknown now
                    if swap_position is not None:
                        self.tracker.clear_opponent_position(acting_player, swap_position)
                    if target_pos is not None:
                        self.tracker.clear_opponent_position(target_player, target_pos)

            # Opponent drew from discard + swapped: we know what they put where
            if draw_source == 'discard' and action == 'swap' and swap_position is not None and prev_top is not None:
                self.tracker.set_opponent_card(acting_player, swap_position, prev_top)

            # Opponent drew from deck + swapped: the card at swap_position is now unknown to us
            elif draw_source == 'deck' and action == 'swap' and swap_position is not None:
                self.tracker.clear_opponent_position(acting_player, swap_position)

            # Opponent drew from discard + used power (swap): we know what they got
            if draw_source == 'discard' and power_type in ('blind_swap', 'king_swap'):
                # They drew from discard but the power card itself got discarded,
                # not the discard card — the discard card they drew was used to decide power usage.
                # Actually, in the game engine, power cards are drawn then discarded after use.
                # The drawn card IS the power card. If they drew from discard, they chose NOT
                # to use the power (they swapped it into hand). But power path always discards the power card.
                # So this case doesn't apply — power cards are always discarded.
                pass

        # --- Bug fix C: Self-initiated blind/king swap clears own position ---
        if acting_player == self.name:
            power_type = turn_data.get('power_type')
            swap_position = turn_data.get('swap_position')
            if power_type in ('blind_swap', 'king_swap') and swap_position is not None:
                # After swapping, our position has the opponent's old card (unknown)
                self.tracker.own_card_swapped_out(swap_position)
                if swap_position in self.known:
                    del self.known[swap_position]

        # Sync own known cards with tracker
        for pos, card in self.known.items():
            self.tracker.set_own_card(pos, card_to_tuple(card))

    def observe_stick(self, stick_data, game):
        """Update tracker after a stick attempt."""
        self._ensure_initialized(game)
        self.tracker.sync_discard(game.discard)

        if stick_data['player'] == self.name and stick_data['success']:
            # Our own stick removed a card — tracker updated via observe_turn hand size sync
            pass

        # Update opponent hand sizes
        for p in game.players:
            if p.name != self.name:
                self.tracker.update_opponent_hand_size(p.name, len(p.hand))

    def choose_draw(self, game):
        """Take from discard only when it's clearly better than drawing from deck."""
        self._ensure_initialized(game)

        if not game.discard:
            return 'deck'

        discard_value = game.discard[-1].get_value()

        # Find the position that would benefit most from the discard card
        best_improvement = 0
        for pos in self.tracker.own_hand:
            current_ev = self.tracker.expected_value_at_position(pos)
            improvement = current_ev - discard_value
            if improvement > best_improvement:
                best_improvement = improvement

        # Tighter threshold: only take from discard when clearly worth it
        # Joker (0) or Red King (-1) are always worth taking
        if discard_value <= 0:
            return 'discard'
        # Otherwise require a large improvement
        if best_improvement >= 3:
            return 'discard'

        return 'deck'

    def choose_action(self, drawn_card):
        """Swap into the position with biggest EV improvement, with info bonus for unknowns."""
        drawn_value = drawn_card.get_value()

        best_pos = None
        best_score = 0  # Must be positive to swap

        for pos in self.tracker.own_hand:
            if pos >= len(self.hand):
                continue
            current_ev = self.tracker.expected_value_at_position(pos)
            improvement = current_ev - drawn_value

            # Info bonus: placing a known-low card into an unknown slot
            # has extra value (we gain certainty, getting closer to calling cambio)
            is_unknown = self.tracker.own_hand.get(pos) is None
            info_bonus = 0
            if is_unknown and drawn_value <= 3:
                info_bonus = 1

            score = improvement + info_bonus
            if score > best_score:
                best_score = score
                best_pos = pos

        if best_pos is not None and best_score > 0:
            return {'type': 'swap', 'position': best_pos}

        return {'type': 'discard'}

    def choose_power_action(self, card, game, opponents):
        """Use power cards strategically based on information gain and EV."""
        self._ensure_initialized(game)

        if card.rank in ['7', '8']:
            # Peek own: target first unknown position
            unknowns = [p for p in self.tracker.own_unknown_positions() if p < len(self.hand)]
            if unknowns:
                return {'type': 'peek_own', 'position': unknowns[0]}

        elif card.rank in ['9', '10']:
            # Peek opponent: prefer opponents likely winning (lower expected score)
            if opponents:
                best_opp = None
                best_score = float('inf')
                best_pos = None
                for opp in opponents:
                    unknown_pos = self.tracker.opponent_unknown_positions(opp.name)
                    if not unknown_pos:
                        continue
                    opp_score = self.tracker.expected_opponent_score(opp.name)
                    if opp_score < best_score:
                        best_score = opp_score
                        best_opp = opp
                        best_pos = random.choice(unknown_pos)
                # Fallback: if all positions are known for low-score opps, pick any with unknowns
                if best_opp is None:
                    for opp in opponents:
                        unknown_pos = self.tracker.opponent_unknown_positions(opp.name)
                        if unknown_pos:
                            best_opp = opp
                            best_pos = random.choice(unknown_pos)
                            break
                if best_opp and best_pos is not None:
                    return {'type': 'peek_opponent', 'opponent': best_opp, 'position': best_pos}

        elif card.rank in ['J', 'Q']:
            # Blind swap: swap our worst card for opponent's best known (or random unknown)
            worst = self.tracker.worst_own_position()
            if worst is not None and opponents:
                worst_pos, worst_val = worst
                if worst_pos >= len(self.hand):
                    return None
                e_unknown = self.tracker.expected_value_of_unknown()
                if worst_val > e_unknown + 1:
                    # Smart targeting: prefer known-low opponent positions
                    best_target = self._find_best_swap_target(opponents)
                    if best_target:
                        opp, opp_pos = best_target
                        return {
                            'type': 'blind_swap',
                            'my_position': worst_pos,
                            'opponent': opp,
                            'opp_position': opp_pos,
                        }
                    # Fallback: random opponent, random position
                    opp = random.choice(opponents)
                    if opp.hand:
                        opp_pos = random.randint(0, len(opp.hand) - 1)
                        return {
                            'type': 'blind_swap',
                            'my_position': worst_pos,
                            'opponent': opp,
                            'opp_position': opp_pos,
                        }

        elif card.rank == 'K' and card.suit in ['Spades', 'Clubs']:
            # Black King: more aggressive threshold since we peek before swapping
            worst = self.tracker.worst_own_position()
            if worst is not None and opponents:
                worst_pos, worst_val = worst
                if worst_pos >= len(self.hand):
                    return None
                e_unknown = self.tracker.expected_value_of_unknown()
                # Lower threshold — we get to see before committing
                if worst_val > e_unknown - 2:
                    best_opp = None
                    target_pos = None
                    most_unknowns = -1
                    for opp in opponents:
                        unknown_pos = self.tracker.opponent_unknown_positions(opp.name)
                        if len(unknown_pos) > most_unknowns:
                            most_unknowns = len(unknown_pos)
                            best_opp = opp
                            target_pos = random.choice(unknown_pos) if unknown_pos else None

                    if best_opp and target_pos is not None:
                        return {
                            'type': 'king_swap',
                            'my_position': worst_pos,
                            'opponent': best_opp,
                            'opp_position': target_pos,
                        }

        return None

    def _find_best_swap_target(self, opponents):
        """Find the best opponent position to blind-swap with.

        Prefer known-low opponent positions (we want their good cards).
        """
        best_opp = None
        best_pos = None
        best_val = float('inf')

        for opp in opponents:
            if opp.name not in self.tracker.opponent_hands:
                continue
            for pos, card in self.tracker.opponent_hands[opp.name].items():
                if card is not None and pos < len(opp.hand):
                    val = tuple_value(card[0], card[1])
                    if val < best_val:
                        best_val = val
                        best_opp = opp
                        best_pos = pos

        if best_opp is not None and best_pos is not None:
            return (best_opp, best_pos)
        return None

    def use_card_power(self, card, game, opponent=None, my_pos=None, opp_pos=None,
                       player2=None, pos2=None, peek_player=None, peek_pos=None,
                       verbose=True):
        """Override for Black King: peek first, only swap if beneficial."""
        if card.rank == 'K' and card.suit in ['Spades', 'Clubs']:
            if opponent and my_pos is not None and opp_pos is not None:
                # Peek at opponent's card
                peeked = opponent.hand[opp_pos]
                peeked_value = peeked.get_value()
                if verbose:
                    print(f"  {self.name} used Black {card} to see {opponent.name}'s position {opp_pos}: {peeked}")

                # Record in tracker regardless of swap decision
                self.tracker.set_opponent_card(opponent.name, opp_pos, card_to_tuple(peeked))

                # Get our card's value at my_pos
                my_card_value = self.hand[my_pos].get_value()

                # Only swap if opponent's card is better (lower value) than ours
                if peeked_value < my_card_value:
                    game.swap(self, opponent, my_pos, opp_pos)
                    if verbose:
                        print(f"     Then swapped with own position {my_pos}")
                else:
                    if verbose:
                        print(f"     Chose NOT to swap (opponent card {peeked_value} >= own card {my_card_value})")

                return True

        # Delegate all other powers to base implementation
        return super().use_card_power(card, game, opponent=opponent, my_pos=my_pos, opp_pos=opp_pos,
                                      player2=player2, pos2=pos2, peek_player=peek_player,
                                      peek_pos=peek_pos, verbose=verbose)

    def call_cambio(self):
        """Call cambio with adaptive timing based on hand size and knowledge.

        Two paths to calling cambio (OR logic):
          (a) High-confidence: know nearly all cards + score is good + margin over opponents
          (b) EV dominance: even with unknowns, expected score is far ahead of all opponents
        """
        known_count = self.tracker.own_known_count()
        hand_size = len(self.hand)
        my_expected = self.tracker.expected_own_score()

        # Compute opponent info used by both paths
        total_opp_known = 0
        total_opp_positions = 0
        for name in self.tracker.opponent_hand_sizes:
            total_opp_positions += self.tracker.opponent_hand_sizes[name]
            if name in self.tracker.opponent_hands:
                total_opp_known += sum(1 for c in self.tracker.opponent_hands[name].values() if c is not None)

        adaptive_margin = self.cambio_margin
        if total_opp_positions > 0:
            knowledge_ratio = total_opp_known / total_opp_positions
            # Reduce margin as we know more (from 4 down to 0)
            # At 100% knowledge our estimates are exact — no buffer needed
            adaptive_margin = self.cambio_margin * (1 - knowledge_ratio)

        # --- Path (a): High-confidence call ---
        if known_count >= hand_size - self.cambio_knowledge_gap:
            # Adaptive threshold: smaller hands can achieve lower scores
            adaptive_threshold = self.cambio_threshold
            if hand_size <= 3:
                adaptive_threshold = 7
            elif hand_size <= 2:
                adaptive_threshold = 5

            # Check margin against all opponents
            has_margin = True
            for name in self.tracker.opponent_hand_sizes:
                opp_expected = self.tracker.expected_opponent_score(name)
                if my_expected >= opp_expected - adaptive_margin:
                    has_margin = False
                    break

            if has_margin and my_expected < adaptive_threshold:
                return True

            # If we know ALL cards and score is excellent
            if known_count == hand_size and my_expected < 8:
                return True

        # --- Path (b): EV dominance — ahead of everyone by a large margin ---
        ev_dominant = True
        for name in self.tracker.opponent_hand_sizes:
            opp_expected = self.tracker.expected_opponent_score(name)
            if my_expected >= opp_expected - self.ev_dominance_margin:
                ev_dominant = False
                break

        if ev_dominant:
            return True

        return False

    def choose_stick(self, game):
        """Return positions of known cards matching the discard top rank."""
        if not game.discard:
            return []

        top_rank = game.discard[-1].rank
        positions = []
        for pos, card in self.tracker.own_hand.items():
            if card is not None and card[0] == top_rank:
                positions.append(pos)
        return positions
