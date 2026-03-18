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

# Grid-search-optimized parameter presets by table size.
# Tuned against mixed opponents (Smart + V1 + Base), 100 matches each.
PRESETS = {
    'duel': {  # 1v1 optimal (vs Smart)
        'stick_ev_threshold': 1.5,
        'cambio_aggressive_threshold': 7,
        'cambio_margin': 4,
        'cambio_knowledge_gap': 1,
        'cambio_threshold': 9,
        'ev_dominance_margin': 12,
        'disruption_bonus_max': 4,
        'good_hand_threshold': 2,
        'info_bonus_max_value': 1,
        'small_deck_threshold': 8,
        'jq_swap_improvement': 1,
    },
    'multi': {  # 4p optimal (vs Smart + V1 + Base)
        'stick_ev_threshold': 2.0,
        'cambio_aggressive_threshold': 5,
        'cambio_margin': 5,
        'cambio_knowledge_gap': 0,
        'cambio_threshold': 8,
        'ev_dominance_margin': 10,
        'disruption_bonus_max': 0.5,
        'good_hand_threshold': 8,
        'info_bonus_max_value': 1,
        'small_deck_threshold': 8,
        'jq_swap_improvement': 4,
    },
}


class BayesianV2Agent(BayesianAgent):
    """Bayesian agent with disruption-aware swap targeting."""

    def __init__(self, name="BayesianV2Agent", discard_threshold=None,
                 cambio_threshold=10, cambio_margin=2, cambio_knowledge_gap=1,
                 ev_dominance_margin=8, stick_ev_threshold=2.5,
                 cambio_aggressive_threshold=8,
                 use_disruption_scoring=True, use_probabilistic_stick=True,
                 use_preemptive_cambio=False, use_third_party_swaps=True,
                 use_smart_peek=True, use_aggressive_cambio=True,
                 use_final_round_mode=True, use_opponent_inference=True,
                 use_deck_awareness=True,
                 disruption_bonus_max=3, good_hand_threshold=5,
                 info_bonus_max_value=3, small_deck_threshold=5,
                 jq_swap_improvement=2,
                 preset=None):
        # Apply preset overrides (preset values are overridden by explicit kwargs)
        if preset and preset in PRESETS:
            p = PRESETS[preset]
            cambio_threshold = p.get('cambio_threshold', cambio_threshold)
            cambio_margin = p.get('cambio_margin', cambio_margin)
            cambio_knowledge_gap = p.get('cambio_knowledge_gap', cambio_knowledge_gap)
            ev_dominance_margin = p.get('ev_dominance_margin', ev_dominance_margin)
            stick_ev_threshold = p.get('stick_ev_threshold', stick_ev_threshold)
            cambio_aggressive_threshold = p.get('cambio_aggressive_threshold', cambio_aggressive_threshold)
            disruption_bonus_max = p.get('disruption_bonus_max', disruption_bonus_max)
            good_hand_threshold = p.get('good_hand_threshold', good_hand_threshold)
            info_bonus_max_value = p.get('info_bonus_max_value', info_bonus_max_value)
            small_deck_threshold = p.get('small_deck_threshold', small_deck_threshold)
            jq_swap_improvement = p.get('jq_swap_improvement', jq_swap_improvement)

        super().__init__(name=name, discard_threshold=discard_threshold,
                         cambio_threshold=cambio_threshold, cambio_margin=cambio_margin,
                         cambio_knowledge_gap=cambio_knowledge_gap,
                         ev_dominance_margin=ev_dominance_margin)
        self.stick_ev_threshold = stick_ev_threshold
        self.cambio_aggressive_threshold = cambio_aggressive_threshold
        # Ablation feature flags (all True for full V2 behavior)
        self.use_disruption_scoring = use_disruption_scoring
        self.use_probabilistic_stick = use_probabilistic_stick
        self.use_preemptive_cambio = use_preemptive_cambio
        self.use_third_party_swaps = use_third_party_swaps
        self.use_smart_peek = use_smart_peek
        self.use_aggressive_cambio = use_aggressive_cambio
        # New feature flags
        self.use_final_round_mode = use_final_round_mode
        self.use_opponent_inference = use_opponent_inference
        self.use_deck_awareness = use_deck_awareness
        # Tunable thresholds (previously hardcoded)
        self.disruption_bonus_max = disruption_bonus_max
        self.good_hand_threshold = good_hand_threshold
        self.info_bonus_max_value = info_bonus_max_value
        self.small_deck_threshold = small_deck_threshold
        self.jq_swap_improvement = jq_swap_improvement
        self._last_game = None

    def _ensure_initialized(self, game):
        """Extend parent init to set up opponent self-knowledge."""
        was_initialized = self._initialized
        super()._ensure_initialized(game)
        self._last_game = game  # Always keep game reference current
        if not was_initialized and self._initialized:
            for p in game.players:
                if p.name != self.name:
                    self.tracker.init_opponent_self_knowledge(p.name)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_final_round(self, game):
        """Check if we're in the final round (someone called Cambio)."""
        return self.use_final_round_mode and getattr(game, 'final_round_active', False)

    # ------------------------------------------------------------------
    # Observation — track opponent self-knowledge + action inference
    # ------------------------------------------------------------------

    def observe_turn(self, turn_data, game):
        """Call parent observe_turn, then update opponent self-knowledge."""
        super().observe_turn(turn_data, game)
        self._last_game = game  # Keep game ref current for call_cambio

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

        # --- Opponent action inference (Step 2) ---
        if self.use_opponent_inference:
            draw_source = turn_data.get('draw_source')

            # 2a: Opponent drew from deck and discarded (didn't swap) →
            # all their cards are likely <= discarded value
            if draw_source == 'deck' and action == 'discard':
                discarded_value = turn_data.get('discarded_value')
                if discarded_value is not None:
                    self.tracker.set_opponent_hand_upper_bound(acting, discarded_value)

            # 2b: Opponent peeked own card (7/8 power) and kept it →
            # that position is likely low-value
            if power_type == 'peek_own':
                peek_pos = turn_data.get('power_peek_position')
                if peek_pos is None:
                    # For peek_own, the position might be in different fields
                    # depending on engine version. Try swap_position as fallback.
                    peek_pos = turn_data.get('swap_position')
                if peek_pos is not None:
                    self.tracker.add_opponent_peeked_and_kept(acting, peek_pos)

    # ------------------------------------------------------------------
    # Probabilistic stick play (Priority 1)
    # ------------------------------------------------------------------

    def choose_stick(self, game):
        """Stick known matches (like V1) PLUS probabilistic sticks for unknowns.

        For unknown positions, compute:
            P(match) = count_of_rank_in_unaccounted / total_unaccounted
            EV(stick) = P(match) * card_value_at_pos - (1 - P(match)) * E[penalty]
        Stick if EV(stick) > stick_ev_threshold.

        Final-round mode: only stick known matches (no probabilistic sticks).
        A failed stick adds a penalty card that directly hurts our final score.
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

        # Final round: only known matches — probabilistic sticks are too risky
        if self._is_final_round(game):
            return positions

        # Probabilistic sticks for unknown positions (ablation-gated)
        if not self.use_probabilistic_stick:
            return positions

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
    # Smarter draw decision (deck EV comparison)
    # ------------------------------------------------------------------

    def choose_draw(self, game):
        """Improved draw: compare discard improvement vs expected deck improvement.

        Drawing from deck has two advantages V1 ignores:
        1. If the deck card is bad, we can discard it and potentially trigger a power.
        2. The deck may contain many cards better than the discard option.

        We compute E[improvement from deck] and only take the discard when it
        clearly beats the deck's expected value.

        Final-round mode: lower improvement threshold to 0 (any improvement is
        worth it since there's no future to optimize for).

        Deck awareness: prefer discard when deck is very small (<=5 cards).
        """
        self._ensure_initialized(game)
        self._last_game = game  # Store for choose_action's final-round check

        if not game.discard:
            return 'deck'

        discard_value = game.discard[-1].get_value()

        # Joker (0) or Red King (-1) are always worth taking
        if discard_value <= 0:
            return 'discard'

        # Find best improvement from discard card
        worst_ev = 0
        for pos in self.tracker.own_hand:
            current_ev = self.tracker.expected_value_at_position(pos)
            if current_ev > worst_ev:
                worst_ev = current_ev

        discard_improvement = worst_ev - discard_value

        # Final round: take any improvement (threshold 0 instead of 1)
        if self._is_final_round(game):
            if discard_improvement > 0:
                return 'discard'
            return 'deck'

        # Deck awareness: small deck favors known discard over risky draw
        deck_size = len(game.deck.cards) if self.use_deck_awareness else 999
        if self.use_deck_awareness and deck_size <= self.small_deck_threshold and discard_improvement > 0:
            return 'discard'

        # Compute expected improvement from a random deck draw
        unaccounted = self.tracker.unaccounted_cards()
        if not unaccounted:
            # No info — fall back to V1 logic
            return 'discard' if discard_improvement >= 1 else 'deck'

        # For each possible deck card, the improvement is max(0, worst_ev - card_value)
        # Plus a power bonus: if we draw a power card and don't swap, we get info
        deck_improvements = []
        for rank, suit in unaccounted:
            val = tuple_value(rank, suit)
            improvement = max(0, worst_ev - val)
            # Power card bonus: 7/8 peek own (~1 pt info value), 9/10 peek opp (~0.5),
            # J/Q swap (~1 if we have a bad card), Black K (~1.5 for peek+swap)
            power_bonus = 0
            if rank in ['7', '8']:
                power_bonus = 1.0
            elif rank in ['9', '10']:
                power_bonus = 0.5
            elif rank in ['J', 'Q']:
                power_bonus = 1.0
            elif rank == 'K' and suit in ['Spades', 'Clubs']:
                power_bonus = 1.5
            # If we wouldn't swap this card, we get the power instead
            if improvement == 0:
                deck_improvements.append(power_bonus)
            else:
                deck_improvements.append(improvement)

        expected_deck_improvement = sum(deck_improvements) / len(deck_improvements)

        # Take from discard only when it clearly beats the deck
        if discard_improvement >= 1 and discard_improvement >= expected_deck_improvement:
            return 'discard'

        return 'deck'

    # ------------------------------------------------------------------
    # Stick-chain and anti-stick swap scoring
    # ------------------------------------------------------------------

    def choose_action(self, drawn_card, game=None):
        """Swap with stick-chain bonus and anti-stick penalty.

        Beyond V1's improvement + info_bonus, V2 adds:
        - Stick-chain bonus: if displacing a card creates sticking opportunities
          (we have OTHER known cards of the same rank), add those cards' values.
        - Anti-stick penalty: if displacing a common rank that opponents likely
          have, penalize (they'll stick and shrink their hands).

        Final-round mode: more aggressive swaps — swap into unknown positions
        even with moderate improvement since reducing unknowns has no future
        value but reducing score does.
        """
        drawn_value = drawn_card.get_value()

        # Detect final round from the game object stored during choose_draw
        final_round = (self.use_final_round_mode
                       and hasattr(self, '_last_game')
                       and self._last_game is not None
                       and self._last_game.final_round_active)

        best_pos = None
        best_score = 0  # Must be positive to swap

        for pos in self.tracker.own_hand:
            if pos >= len(self.hand):
                continue
            current_ev = self.tracker.expected_value_at_position(pos)
            improvement = current_ev - drawn_value

            # Info bonus (same as V1)
            is_unknown = self.tracker.own_hand.get(pos) is None
            info_bonus = 0
            if is_unknown and drawn_value <= self.info_bonus_max_value:
                info_bonus = 1

            # Final round: boost info bonus for unknowns and lower swap bar
            if final_round and is_unknown and improvement > -2:
                info_bonus = max(info_bonus, 2)

            # Stick-chain bonus: if we displace this card, does its rank match
            # any OTHER known cards in our hand? If so, we can stick them.
            stick_chain_bonus = 0
            displaced_card = self.tracker.own_hand.get(pos)
            if displaced_card is not None:
                displaced_rank = displaced_card[0]
                for other_pos, other_card in self.tracker.own_hand.items():
                    if other_pos != pos and other_card is not None and other_card[0] == displaced_rank:
                        stick_chain_bonus += tuple_value(other_card[0], other_card[1])

            # Anti-stick penalty: if displaced rank is common in unaccounted cards,
            # opponents may have matches and stick (reducing their hand size).
            anti_stick_penalty = 0
            if displaced_card is not None:
                displaced_rank = displaced_card[0]
                # Check how many of this rank opponents are known to have
                for name, opp_hand in self.tracker.opponent_hands.items():
                    for opp_pos, opp_card in opp_hand.items():
                        if opp_card is not None and opp_card[0] == displaced_rank:
                            anti_stick_penalty += 0.5

            score = improvement + info_bonus + stick_chain_bonus - anti_stick_penalty
            if score > best_score:
                best_score = score
                best_pos = pos

        if best_pos is not None and best_score > 0:
            return {'type': 'swap', 'position': best_pos}

        return {'type': 'discard'}

    # ------------------------------------------------------------------
    # Improved cambio timing (Priority 2)
    # ------------------------------------------------------------------

    def call_cambio(self):
        """Enhanced cambio: aggressive call with excellent known hand,
        plus opponent-knowledge-aware preemption.

        Cambio parameters scale with opponent count: calling Cambio with
        many opponents is riskier (more chances someone beats you), so
        we widen the margin and knowledge requirements.

        Final-round suppression: if someone already called Cambio, return False.
        Deck awareness: if deck is very small and we're ahead, call early.
        """
        if not self._initialized:
            return False

        # Final-round suppression: can't call Cambio twice
        if self.use_final_round_mode and hasattr(self, '_last_game') and self._last_game is not None:
            if self._last_game.cambio_called:
                return False

        known_count = self.tracker.own_known_count()
        hand_size = len(self.hand)
        my_expected = self.tracker.expected_own_score()

        # Scale conservatism with opponent count
        num_opps = len(self.tracker.opponent_hand_sizes)
        # Extra margin per additional opponent beyond the first
        opp_scaling = max(0, num_opps - 1)

        # Deck awareness: if deck is very small, consider calling early
        if self.use_deck_awareness and hasattr(self, '_last_game') and self._last_game is not None:
            deck_size = len(self._last_game.deck.cards)
            if deck_size <= self.small_deck_threshold and known_count >= hand_size - 1:
                # Deck nearly exhausted — reshuffle increases variance.
                # Call if we're ahead of all opponents.
                all_ahead = True
                for name in self.tracker.opponent_hand_sizes:
                    opp_expected = self._get_opponent_expected(name)
                    if my_expected >= opp_expected:
                        all_ahead = False
                        break
                if all_ahead and my_expected < self.cambio_threshold:
                    return True

        # Aggressive call: know all cards and score is excellent
        # V1 requires score < 8 for this path; V2 lowers to 3 (ablation-gated)
        # But widen threshold with more opponents
        if self.use_aggressive_cambio:
            scaled_threshold = self.cambio_aggressive_threshold + opp_scaling
            if known_count == hand_size and my_expected <= scaled_threshold:
                return True
        else:
            # Fall back to V1 threshold (8)
            if known_count == hand_size and my_expected < 8:
                return True

        # Preemptive call: if we detect opponent is ready to call,
        # call first ONLY if we have strong margin (ablation-gated)
        if self.use_preemptive_cambio:
            for name in self.tracker.opponent_hand_sizes:
                opp_knowledge = self.tracker.get_opponent_self_knowledge(name)
                opp_hand_size = self.tracker.opponent_hand_sizes[name]
                # Opponent knows all or nearly all their cards
                if len(opp_knowledge) >= opp_hand_size:
                    opp_expected = self._get_opponent_expected(name)
                    # Only preempt with strong advantage and high confidence
                    if (known_count >= hand_size - self.cambio_knowledge_gap
                            and my_expected < self.cambio_threshold
                            and my_expected < opp_expected - 2):
                        return True

        # Scale margin for V1's cambio logic based on opponent count
        original_margin = self.cambio_margin
        self.cambio_margin = self.cambio_margin + opp_scaling
        result = super().call_cambio()
        self.cambio_margin = original_margin
        return result

    def _get_opponent_expected(self, name):
        """Get opponent expected score, using inference if enabled."""
        if self.use_opponent_inference:
            return self.tracker.expected_opponent_score_with_inference(name)
        return self.tracker.expected_opponent_score(name)

    # ------------------------------------------------------------------
    # Enhanced swap targeting with disruption scoring (Priority 3: scaled bonus)
    # ------------------------------------------------------------------

    def _find_best_swap_target(self, opponents):
        """Find the best opponent position to swap with, factoring in disruption.

        score = -card_value + scaled_disruption_bonus
        The disruption bonus is scaled by number of opponents: full bonus with 2+,
        reduced to 1 in 1v1 so card value dominates the decision.
        """
        # When disruption scoring is disabled, fall back to V1 behavior
        if not self.use_disruption_scoring:
            return super()._find_best_swap_target(opponents)

        best_opp = None
        best_pos = None
        best_score = float('-inf')

        # Scale disruption bonus: full (3) with 2+ opponents, 1 in 1v1
        num_opponents = len(opponents)
        if num_opponents >= 2:
            disruption_bonus = self.disruption_bonus_max
        else:
            disruption_bonus = min(1, self.disruption_bonus_max)

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
            if self.use_smart_peek:
                return self._choose_peek_opponent_action(card, game, opponents)
            else:
                return super().choose_power_action(card, game, opponents)

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

        # Prefer positions the opponent does NOT know about (unmanaged positions).
        # These are more likely to hold high-value unswapped cards, giving us
        # more useful intel for future swap decisions.
        opp_knowledge = self.tracker.get_opponent_self_knowledge(best_opp.name)
        unmanaged = [p for p in unknown_pos if p not in opp_knowledge]
        target_pos = min(unmanaged) if unmanaged else min(unknown_pos)

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
                        if worst_val - target_val >= self.jq_swap_improvement:
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


        # Path 2: Disruption swap if hand is already good AND we're winning (multi-player only)
        if not self.use_third_party_swaps:
            return None

        if worst is not None:
            _, worst_val = worst
        else:
            worst_val = e_unknown

        if worst_val <= self.good_hand_threshold and len(opponents) >= 2:
            # Only disrupt if we're actually ahead — no point sabotaging when losing
            my_expected = self.tracker.expected_own_score()
            best_opp_expected = min(
                self.tracker.expected_opponent_score(o.name) for o in opponents
            )
            if my_expected > best_opp_expected:
                return None  # We're behind; disruption won't help

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
        hand_is_strong = worst_val <= self.good_hand_threshold

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
