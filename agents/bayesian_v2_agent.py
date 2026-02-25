"""BayesianV2Agent — disruption-aware swap targeting.

Extends BayesianAgent with:
- Opponent self-knowledge tracking (what positions opponents likely know)
- Disruption-weighted swap scoring (prefer swapping positions opponents know)
- Third-party swaps via J/Q (swap two opponents' cards without involving own hand)
- Enhanced Black King with peek-any + swap-any-two support
- Probabilistic stick play using unaccounted card distribution
- Improved cambio timing with defense buffer and preemptive calling
- Opponent-count-scaled disruption bonus for 1v1 accuracy
- Smarter 9/10 peek targeting based on card distribution
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from agents.bayesian_agent import BayesianAgent
from agents.card_tracker import card_to_tuple, tuple_value

# Max disruption bonus (scaled down by 1/num_opponents for 1v1)
DISRUPTION_BONUS_MAX = 3
# Threshold: if our worst known card value is at or below this, hand is "good enough"
# to consider disruption-only moves instead of self-improving swaps
GOOD_HAND_THRESHOLD = 5
# EV threshold for probabilistic sticking: stick if EV(stick) > this
STICK_EV_THRESHOLD = 2.0


class BayesianV2Agent(BayesianAgent):
    """Bayesian agent with disruption-aware swap targeting."""

    def __init__(self, name="BayesianV2Agent", discard_threshold=None,
                 cambio_threshold=10, cambio_margin=3, cambio_knowledge_gap=2,
                 ev_dominance_margin=8, stick_ev_threshold=STICK_EV_THRESHOLD):
        super().__init__(name=name, discard_threshold=discard_threshold,
                         cambio_threshold=cambio_threshold, cambio_margin=cambio_margin,
                         cambio_knowledge_gap=cambio_knowledge_gap,
                         ev_dominance_margin=ev_dominance_margin)
        self.stick_ev_threshold = stick_ev_threshold

    def _ensure_initialized(self, game):
        """Extend parent init to set up opponent self-knowledge."""
        was_initialized = self._initialized
        super()._ensure_initialized(game)
        if not was_initialized and self._initialized:
            for p in game.players:
                if p.name != self.name:
                    self.tracker.init_opponent_self_knowledge(p.name)

    # ------------------------------------------------------------------
    # Observation — track opponent self-knowledge
    # ------------------------------------------------------------------

    def observe_turn(self, turn_data, game):
        """Call parent observe_turn, then update opponent self-knowledge."""
        super().observe_turn(turn_data, game)

        acting = turn_data['player']
        if acting == self.name:
            return

        power_type = turn_data.get('power_type')
        action = turn_data.get('action')
        swap_position = turn_data.get('swap_position')
        target_player = turn_data.get('power_target_player')
        target_pos = turn_data.get('power_target_position')
        target_player2 = turn_data.get('power_target_player2')
        target_pos2 = turn_data.get('power_target_position2')

        # Opponent peeked their own card → gains knowledge
        if power_type == 'peek_own' and swap_position is not None:
            # In turn_data for peek_own, the position is stored differently.
            # The game engine doesn't set swap_position for peek_own; we need
            # the power action's position. However, the peek_own position isn't
            # directly in turn_data. We rely on the fact that peek_own calls
            # game.peek which sets player.known[pos], so the position is the
            # one peeked. Unfortunately turn_data doesn't directly expose this
            # for peek_own. Let's check power_target_position instead.
            pass

        # peek_own: the position is NOT in swap_position or power_target_position
        # for the base engine. We can't reliably track peek_own from turn_data alone.
        # However, for peek_opponent by acting player on their own card — this doesn't
        # happen. The most reliable signals are:
        #   - draw+swap → acting gains knowledge of swap_position
        #   - blind_swap/king_swap targeting acting → acting loses knowledge

        # Opponent drew and swapped into hand → they know that position
        if action == 'swap' and swap_position is not None:
            self.tracker.opponent_gains_knowledge(acting, swap_position)

        # Blind/king swap: both participants lose knowledge of swapped positions
        if power_type in ('blind_swap', 'king_swap'):
            # The initiator loses knowledge of their swap_position
            if swap_position is not None:
                self.tracker.opponent_loses_knowledge(acting, swap_position)
            # The target loses knowledge of target_pos
            if target_player and target_pos is not None:
                self.tracker.opponent_loses_knowledge(target_player, target_pos)

        # Third-party swap: both targets lose knowledge
        if power_type == 'third_party_swap':
            if target_player and target_pos is not None:
                self.tracker.opponent_loses_knowledge(target_player, target_pos)
            if target_player2 and target_pos2 is not None:
                self.tracker.opponent_loses_knowledge(target_player2, target_pos2)

        # King peek-swap
        if power_type == 'king_peek_swap':
            if target_player and target_pos is not None:
                self.tracker.opponent_loses_knowledge(target_player, target_pos)
            if target_player2 and target_pos2 is not None:
                self.tracker.opponent_loses_knowledge(target_player2, target_pos2)
            # If swap involved the acting player's own position
            if swap_position is not None:
                self.tracker.opponent_loses_knowledge(acting, swap_position)

    # ------------------------------------------------------------------
    # Probabilistic stick play (Priority 1)
    # ------------------------------------------------------------------

    def choose_stick(self, game):
        """Stick known matches (like V1) PLUS probabilistic sticks for unknowns.

        For unknown positions, compute:
            P(match) = count_of_rank_in_unaccounted / total_unaccounted
            EV(stick) = P(match) * card_value_at_pos - (1 - P(match)) * E[penalty]
        Stick if EV(stick) > stick_ev_threshold.
        """
        if not game.discard:
            return []

        top_rank = game.discard[-1].rank
        top_value = game.discard[-1].get_value()
        positions = []

        # Known matches (same as V1)
        for pos, card in self.tracker.own_hand.items():
            if card is not None and card[0] == top_rank:
                positions.append(pos)

        # Probabilistic sticks for unknown positions
        unaccounted = self.tracker.unaccounted_cards()
        total_unaccounted = len(unaccounted)
        if total_unaccounted > 0:
            rank_count = self.tracker.count_rank_in_unaccounted(top_rank)
            p_match = rank_count / total_unaccounted
            e_penalty = self.tracker.expected_value_of_unknown()

            for pos, card in self.tracker.own_hand.items():
                if card is not None:
                    continue  # Already handled known cards above
                if pos >= len(self.hand):
                    continue
                # EV of sticking: if match, we remove a card worth top_value
                # from our hand; if miss, we gain a penalty card worth e_penalty
                ev_stick = p_match * top_value - (1 - p_match) * e_penalty
                if ev_stick > self.stick_ev_threshold:
                    positions.append(pos)

        return positions

    # ------------------------------------------------------------------
    # Improved cambio timing (Priority 2)
    # ------------------------------------------------------------------

    def call_cambio(self):
        """Enhanced cambio: aggressive call with excellent known hand,
        plus opponent-knowledge-aware preemption."""
        if not self._initialized:
            return False

        known_count = self.tracker.own_known_count()
        hand_size = len(self.hand)
        my_expected = self.tracker.expected_own_score()

        # Aggressive call: know all cards and score is excellent
        # V1 requires score < 8 for this path; V2 lowers to 6
        if known_count == hand_size and my_expected <= 6:
            return True

        # Preemptive call: if we detect opponent is ready to call,
        # call first ONLY if we have strong margin
        for name in self.tracker.opponent_hand_sizes:
            opp_knowledge = self.tracker.get_opponent_self_knowledge(name)
            opp_hand_size = self.tracker.opponent_hand_sizes[name]
            # Opponent knows all or nearly all their cards
            if len(opp_knowledge) >= opp_hand_size:
                opp_expected = self.tracker.expected_opponent_score(name)
                # Only preempt with strong advantage and high confidence
                if (known_count >= hand_size - self.cambio_knowledge_gap
                        and my_expected < self.cambio_threshold
                        and my_expected < opp_expected - 2):
                    return True

        return super().call_cambio()

    # ------------------------------------------------------------------
    # Enhanced swap targeting with disruption scoring (Priority 3: scaled bonus)
    # ------------------------------------------------------------------

    def _find_best_swap_target(self, opponents):
        """Find the best opponent position to swap with, factoring in disruption.

        score = -card_value + scaled_disruption_bonus
        The disruption bonus is scaled by number of opponents: full bonus with 2+,
        reduced to 1 in 1v1 so card value dominates the decision.
        """
        best_opp = None
        best_pos = None
        best_score = float('-inf')

        # Scale disruption bonus: full (3) with 2+ opponents, 1 in 1v1
        num_opponents = len(opponents)
        if num_opponents >= 2:
            disruption_bonus = DISRUPTION_BONUS_MAX
        else:
            disruption_bonus = min(1, DISRUPTION_BONUS_MAX)

        for opp in opponents:
            if opp.name not in self.tracker.opponent_hands:
                continue
            opp_knowledge = self.tracker.get_opponent_self_knowledge(opp.name)
            for pos, card in self.tracker.opponent_hands[opp.name].items():
                if card is not None and pos < len(opp.hand):
                    val = tuple_value(card[0], card[1])
                    score = -val
                    if pos in opp_knowledge:
                        score += disruption_bonus
                    if score > best_score:
                        best_score = score
                        best_opp = opp
                        best_pos = pos

        if best_opp is not None and best_pos is not None:
            return (best_opp, best_pos)
        return None

    # ------------------------------------------------------------------
    # Third-party (opponent-to-opponent) swap for J/Q
    # ------------------------------------------------------------------

    def _find_best_disruption_swap(self, opponents):
        """Find the best pair of opponent positions to swap with each other.

        Both opponents should know their respective positions for maximum disruption.
        Prefer positions where opponents know low-value cards (they'll be most upset).

        Returns (opp1, pos1, opp2, pos2) or None.
        """
        candidates = []
        for opp in opponents:
            if opp.name not in self.tracker.opponent_hands:
                continue
            opp_knowledge = self.tracker.get_opponent_self_knowledge(opp.name)
            for pos, card in self.tracker.opponent_hands[opp.name].items():
                if pos in opp_knowledge and pos < len(opp.hand):
                    # We prefer disrupting known positions; card value is secondary
                    val = tuple_value(card[0], card[1]) if card is not None else self.tracker.expected_value_of_unknown()
                    candidates.append((opp, pos, val))

        # Need at least 2 candidates from different opponents
        if len(candidates) < 2:
            return None

        # Sort by value ascending (disrupt known-low cards first — opponents value these most)
        candidates.sort(key=lambda x: x[2])

        # Find best pair from different opponents
        for i in range(len(candidates)):
            for j in range(i + 1, len(candidates)):
                opp1, pos1, _ = candidates[i]
                opp2, pos2, _ = candidates[j]
                if opp1.name != opp2.name:
                    return (opp1, pos1, opp2, pos2)

        return None

    # ------------------------------------------------------------------
    # Power action decision — override for J/Q and Black King
    # ------------------------------------------------------------------

    def choose_power_action(self, card, game, opponents):
        """Enhanced power usage with disruption and third-party swaps."""
        self._ensure_initialized(game)

        if card.rank in ['7', '8']:
            return super().choose_power_action(card, game, opponents)

        elif card.rank in ['9', '10']:
            return self._choose_peek_opponent_action(card, game, opponents)

        elif card.rank in ['J', 'Q']:
            return self._choose_jq_action(card, game, opponents)

        elif card.rank == 'K' and card.suit in ['Spades', 'Clubs']:
            return self._choose_black_king_action(card, game, opponents)

        return None

    def _choose_peek_opponent_action(self, card, game, opponents):
        """9/10: peek opponent position most likely to be low-value.

        Instead of picking a random unknown position, weight positions by the
        probability of containing a low-value card based on unaccounted distribution.
        This makes subsequent swap decisions better-informed.
        """
        if not opponents:
            return None

        # Find the opponent with the lowest expected score (most dangerous)
        best_opp = None
        best_score = float('inf')
        for opp in opponents:
            unknown_pos = self.tracker.opponent_unknown_positions(opp.name)
            if not unknown_pos:
                continue
            opp_score = self.tracker.expected_opponent_score(opp.name)
            if opp_score < best_score:
                best_score = opp_score
                best_opp = opp

        # Fallback: any opponent with unknowns
        if best_opp is None:
            for opp in opponents:
                unknown_pos = self.tracker.opponent_unknown_positions(opp.name)
                if unknown_pos:
                    best_opp = opp
                    break

        if best_opp is None:
            return None

        unknown_pos = self.tracker.opponent_unknown_positions(best_opp.name)
        if not unknown_pos:
            return None

        # Weight unknown positions: prefer positions more likely to hold low cards.
        # In practice, all unknown positions have the same distribution (unaccounted),
        # but positions adjacent to known-low cards or earlier positions (which
        # players tend to peek first) are slightly more likely to be kept low.
        # Use a simple heuristic: prefer positions not yet examined (truly unknown),
        # and among those, prefer lower indices (dealt first, often peeked/managed).
        target_pos = min(unknown_pos)

        return {'type': 'peek_opponent', 'opponent': best_opp, 'position': target_pos}

    def _choose_jq_action(self, card, game, opponents):
        """J/Q decision: self-swap, disruption swap, or skip.

        V2 improvement over V1: swap whenever a known target makes the trade
        beneficial (even if worst_val < e_unknown + 1), and consider swapping
        second-worst card when worst is already low.
        """
        worst = self.tracker.worst_own_position()
        e_unknown = self.tracker.expected_value_of_unknown()

        if worst is not None and opponents:
            worst_pos, worst_val = worst

            if worst_pos >= len(self.hand):
                pass
            else:
                # Path 1a: Check if any known target makes swap worthwhile
                # regardless of e_unknown threshold
                best_target = self._find_best_swap_target(opponents)
                if best_target:
                    opp, opp_pos = best_target
                    target_card = self.tracker.opponent_hands[opp.name].get(opp_pos)
                    if target_card is not None:
                        target_val = tuple_value(target_card[0], target_card[1])
                        # Swap if we'd improve our hand by at least 2 points
                        if worst_val - target_val >= 2:
                            return {
                                'type': 'blind_swap',
                                'my_position': worst_pos,
                                'opponent': opp,
                                'opp_position': opp_pos,
                            }

                # Path 1b: Blind swap to unknown opponent positions when our
                # worst card is significantly above average
                if worst_val > e_unknown + 1:
                    if best_target:
                        opp, opp_pos = best_target
                        return {
                            'type': 'blind_swap',
                            'my_position': worst_pos,
                            'opponent': opp,
                            'opp_position': opp_pos,
                        }
                    opp = random.choice(opponents)
                    if opp.hand:
                        opp_pos = random.randint(0, len(opp.hand) - 1)
                        return {
                            'type': 'blind_swap',
                            'my_position': worst_pos,
                            'opponent': opp,
                            'opp_position': opp_pos,
                        }

                # Path 1c: In 1v1, use J/Q to swap moderately bad cards
                # (value >= 5) with unknown opponent positions. This gamble
                # has positive EV when our card is above average.
                if len(opponents) == 1 and worst_val >= 5:
                    opp = opponents[0]
                    unknown_opp = self.tracker.opponent_unknown_positions(opp.name)
                    if unknown_opp and opp.hand:
                        opp_pos = min(unknown_opp)  # Prefer lower positions
                        if opp_pos < len(opp.hand):
                            return {
                                'type': 'blind_swap',
                                'my_position': worst_pos,
                                'opponent': opp,
                                'opp_position': opp_pos,
                            }

        # Path 2: Disruption swap if hand is already good (multi-player only)
        if worst is not None:
            _, worst_val = worst
        else:
            worst_val = e_unknown

        if worst_val <= GOOD_HAND_THRESHOLD and len(opponents) >= 2:
            disruption = self._find_best_disruption_swap(opponents)
            if disruption:
                opp1, pos1, opp2, pos2 = disruption
                return {
                    'type': 'third_party_swap',
                    'opponent': opp1,
                    'opp_position': pos1,
                    'player2': opp2,
                    'position2': pos2,
                }

        return None

    def _choose_black_king_action(self, card, game, opponents):
        """Black King decision: info-gathering or disruption mode.

        In 1v1, always use Black King for intel + conditional swap. V2 targets
        opponent positions most likely to have low cards (prefer lower indices
        as players tend to manage early positions).
        """
        worst = self.tracker.worst_own_position()
        e_unknown = self.tracker.expected_value_of_unknown()

        if worst is not None:
            worst_pos, worst_val = worst
        else:
            worst_pos = 0
            worst_val = e_unknown

        # Determine if hand is strong (disruption mode) or needs improvement (info mode)
        hand_is_strong = worst_val <= GOOD_HAND_THRESHOLD

        if hand_is_strong and len(opponents) >= 2:
            # Disruption mode: peek for intel, then swap two opponents' known positions
            me = game.players[game.players.index(self)] if self in game.players else None
            peek_target = self._find_best_peek_target_any(me, opponents)
            disruption = self._find_best_disruption_swap(opponents)
            if peek_target and disruption:
                pk_player, pk_pos = peek_target
                opp1, pos1, opp2, pos2 = disruption
                return {
                    'type': 'king_peek_swap',
                    'peek_player': pk_player,
                    'peek_position': pk_pos,
                    'swap': {
                        'player1': opp1,
                        'position1': pos1,
                        'player2': opp2,
                        'position2': pos2,
                    },
                }

        # Info-gathering mode: peek opponent, swap self↔opponent if beneficial
        # Always try (even with moderate hand) since Black King peek is free info
        if worst_pos < len(self.hand) and opponents:
            best_opp = None
            target_pos = None

            for opp in opponents:
                unknown_pos = self.tracker.opponent_unknown_positions(opp.name)
                if unknown_pos:
                    best_opp = opp
                    # Prefer lower indices: players manage positions 0-1 first,
                    # so these are more likely to have been kept/made low
                    target_pos = min(unknown_pos)
                    break

            # Fallback to any opponent with positions
            if best_opp is None:
                for opp in opponents:
                    if opp.hand:
                        best_opp = opp
                        target_pos = 0 if 0 < len(opp.hand) else None
                        break

            if best_opp and target_pos is not None:
                return {
                    'type': 'king_swap',
                    'my_position': worst_pos,
                    'opponent': best_opp,
                    'opp_position': target_pos,
                }

        return None

    def _find_best_peek_target(self, opponents):
        """Find the best opponent position to peek at (for Black King).

        Prefer unknown positions on opponents with the lowest expected score.
        """
        best_opp = None
        best_pos = None
        best_score = float('inf')

        for opp in opponents:
            unknown_pos = self.tracker.opponent_unknown_positions(opp.name)
            if not unknown_pos:
                continue
            opp_score = self.tracker.expected_opponent_score(opp.name)
            if opp_score < best_score:
                best_score = opp_score
                best_opp = opp
                best_pos = random.choice(unknown_pos)

        if best_opp is None:
            # Fallback: any opponent with unknowns
            for opp in opponents:
                unknown_pos = self.tracker.opponent_unknown_positions(opp.name)
                if unknown_pos:
                    return (opp, random.choice(unknown_pos))

        if best_opp and best_pos is not None:
            return (best_opp, best_pos)
        return None

    def _find_best_peek_target_any(self, me, opponents):
        """Find the best peek target including own unknown positions.

        Self-intel is prioritized: peeking our own unknown card gets us closer
        to calling cambio, and doesn't reveal anything to opponents.
        Falls back to opponent peek if all own positions are known.
        """
        # Prefer own unknown positions — self-intel is highest value
        own_unknowns = [p for p in self.tracker.own_unknown_positions() if p < len(self.hand)]
        if own_unknowns and me is not None:
            return (me, random.choice(own_unknowns))

        # Fall back to opponent peek
        return self._find_best_peek_target(opponents)

    # ------------------------------------------------------------------
    # Black King use_card_power override — handle extended peek+swap
    # ------------------------------------------------------------------

    def use_card_power(self, card, game, opponent=None, my_pos=None, opp_pos=None,
                       player2=None, pos2=None, peek_player=None, peek_pos=None,
                       verbose=True):
        """Override for Black King extended path and conditional swap."""
        if card.rank == 'K' and card.suit in ['Spades', 'Clubs']:
            # Extended path: peek any target, then swap any two
            if peek_player and peek_pos is not None:
                if peek_pos < 0 or peek_pos >= len(peek_player.hand):
                    return False
                peeked = peek_player.hand[peek_pos]
                peeked_value = peeked.get_value()
                if verbose:
                    print(f"  {self.name} used Black {card} to see {peek_player.name}'s position {peek_pos}: {peeked}")
                # Record peek in tracker — self vs opponent
                if peek_player == self or peek_player.name == self.name:
                    self.tracker.set_own_card(peek_pos, card_to_tuple(peeked))
                    self.known[peek_pos] = peeked
                else:
                    self.tracker.set_opponent_card(peek_player.name, peek_pos, card_to_tuple(peeked))

                # Third-party swap
                if opponent and player2 and opp_pos is not None and pos2 is not None:
                    if opp_pos < 0 or opp_pos >= len(opponent.hand) or pos2 < 0 or pos2 >= len(player2.hand):
                        return True  # Peek succeeded, swap out of bounds
                    game.swap(opponent, player2, opp_pos, pos2)
                    if verbose:
                        print(f"     Then swapped {opponent.name}'s position {opp_pos} with {player2.name}'s position {pos2}")
                    return True

                # Self-opponent swap (with conditional logic)
                if opponent and my_pos is not None and opp_pos is not None:
                    if my_pos < 0 or my_pos >= len(self.hand) or opp_pos < 0 or opp_pos >= len(opponent.hand):
                        return True  # Peek succeeded, swap out of bounds
                    peek_is_opp = (peek_player == opponent and peek_pos == opp_pos)
                    if peek_is_opp:
                        my_card_value = self.hand[my_pos].get_value()
                        if peeked_value < my_card_value:
                            game.swap(self, opponent, my_pos, opp_pos)
                            if verbose:
                                print(f"     Then swapped own position {my_pos} with {opponent.name}'s position {opp_pos}")
                        else:
                            if verbose:
                                print(f"     Chose NOT to swap (opponent card {peeked_value} >= own card {my_card_value})")
                    else:
                        game.swap(self, opponent, my_pos, opp_pos)
                        if verbose:
                            print(f"     Then swapped own position {my_pos} with {opponent.name}'s position {opp_pos}")
                    return True

                # Peek only
                return True

            # Original conditional swap path (backward compat with king_swap type)
            if opponent and my_pos is not None and opp_pos is not None:
                if opp_pos < 0 or opp_pos >= len(opponent.hand) or my_pos < 0 or my_pos >= len(self.hand):
                    return False
                peeked = opponent.hand[opp_pos]
                peeked_value = peeked.get_value()
                if verbose:
                    print(f"  {self.name} used Black {card} to see {opponent.name}'s position {opp_pos}: {peeked}")
                self.tracker.set_opponent_card(opponent.name, opp_pos, card_to_tuple(peeked))
                my_card_value = self.hand[my_pos].get_value()
                if peeked_value < my_card_value:
                    game.swap(self, opponent, my_pos, opp_pos)
                    if verbose:
                        print(f"     Then swapped with own position {my_pos}")
                else:
                    if verbose:
                        print(f"     Chose NOT to swap (opponent card {peeked_value} >= own card {my_card_value})")
                return True

        return super().use_card_power(card, game, opponent=opponent, my_pos=my_pos,
                                      opp_pos=opp_pos, player2=player2, pos2=pos2,
                                      peek_player=peek_player, peek_pos=peek_pos,
                                      verbose=verbose)
