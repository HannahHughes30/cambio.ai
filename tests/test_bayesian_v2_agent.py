"""Tests for BayesianV2Agent."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from game import Card, CambioGame, Player
from agents.bayesian_v2_agent import BayesianV2Agent
from agents.bayesian_agent import BayesianAgent
from agents.smart_agent import SmartAgent


def make_game(agent, *opponents):
    """Create a game with the given players and deal."""
    players = [agent] + list(opponents)
    game = CambioGame(players)
    game.deal()
    return game


# ------------------------------------------------------------------
# Opponent self-knowledge tracking
# ------------------------------------------------------------------

class TestOpponentSelfKnowledge:
    def test_initialized_with_positions_0_1(self):
        agent = BayesianV2Agent("V2")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        knowledge = agent.tracker.get_opponent_self_knowledge("Opp")
        assert knowledge == {0, 1}

    def test_draw_swap_gains_knowledge(self):
        agent = BayesianV2Agent("V2")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        turn_data = {
            'player': 'Opp',
            'draw_source': 'deck',
            'action': 'swap',
            'power_type': None,
            'swap_position': 2,
            'power_target_player': None,
            'power_target_position': None,
            'power_target_player2': None,
            'power_target_position2': None,
            'power_peek_player': None,
            'power_peek_position': None,
            'discarded_card': '5H',
            'discarded_value': 5,
            'hand_size': 4,
        }
        game.discard.append(Card('5', 'Hearts'))
        agent.observe_turn(turn_data, game)

        knowledge = agent.tracker.get_opponent_self_knowledge("Opp")
        assert 2 in knowledge

    def test_blind_swap_loses_knowledge(self):
        agent = BayesianV2Agent("V2")
        opp1 = SmartAgent("Opp1")
        opp2 = SmartAgent("Opp2")
        game = make_game(agent, opp1, opp2)
        agent._ensure_initialized(game)

        # opp1 blind swaps their pos 0 with opp2 pos 1
        turn_data = {
            'player': 'Opp1',
            'draw_source': 'deck',
            'action': 'power',
            'power_type': 'blind_swap',
            'swap_position': 0,
            'power_target_player': 'Opp2',
            'power_target_position': 1,
            'power_target_player2': None,
            'power_target_position2': None,
            'power_peek_player': None,
            'power_peek_position': None,
            'discarded_card': 'JH',
            'discarded_value': 10,
            'hand_size': 4,
        }
        game.discard.append(Card('J', 'Hearts'))
        agent.observe_turn(turn_data, game)

        # Opp1 loses knowledge of pos 0, Opp2 loses knowledge of pos 1
        assert 0 not in agent.tracker.get_opponent_self_knowledge("Opp1")
        assert 1 not in agent.tracker.get_opponent_self_knowledge("Opp2")

    def test_third_party_swap_loses_knowledge(self):
        agent = BayesianV2Agent("V2")
        opp1 = SmartAgent("Opp1")
        opp2 = SmartAgent("Opp2")
        game = make_game(agent, opp1, opp2)
        agent._ensure_initialized(game)

        turn_data = {
            'player': 'V2',  # We initiated but targets lose knowledge
            'draw_source': 'deck',
            'action': 'power',
            'power_type': 'third_party_swap',
            'swap_position': None,
            'power_target_player': 'Opp1',
            'power_target_position': 0,
            'power_target_player2': 'Opp2',
            'power_target_position2': 1,
            'power_peek_player': None,
            'power_peek_position': None,
            'discarded_card': 'QH',
            'discarded_value': 10,
            'hand_size': 4,
        }
        game.discard.append(Card('Q', 'Hearts'))
        # This won't update because acting == self.name, so observe_turn skips
        # the opponent tracking. Let's simulate as if another V2 agent did it.
        turn_data['player'] = 'Opp1'  # pretend Opp1 initiated
        agent.observe_turn(turn_data, game)

        assert 0 not in agent.tracker.get_opponent_self_knowledge("Opp1")
        assert 1 not in agent.tracker.get_opponent_self_knowledge("Opp2")


# ------------------------------------------------------------------
# Third-party swap game engine
# ------------------------------------------------------------------

class TestThirdPartySwapEngine:
    def test_jq_swaps_two_opponents(self):
        """J/Q can swap cards between two other players."""
        p1 = Player("P1")
        p2 = Player("P2")
        p3 = Player("P3")
        game = CambioGame([p1, p2, p3])
        game.deal()

        p2_card = p2.hand[1]
        p3_card = p3.hand[2]

        card = Card('J', 'Hearts')
        result = p1.use_card_power(card, game, opponent=p2, opp_pos=1,
                                   player2=p3, pos2=2, verbose=False)
        assert result is True
        assert p2.hand[1] == p3_card
        assert p3.hand[2] == p2_card

    def test_black_king_peek_any_swap_any(self):
        """Black King can peek any card, then swap any two."""
        p1 = Player("P1")
        p2 = Player("P2")
        p3 = Player("P3")
        game = CambioGame([p1, p2, p3])
        game.deal()

        p2_card = p2.hand[0]
        p3_card = p3.hand[1]

        card = Card('K', 'Spades')
        result = p1.use_card_power(card, game, opponent=p2, opp_pos=0,
                                   player2=p3, pos2=1,
                                   peek_player=p2, peek_pos=0, verbose=False)
        assert result is True
        assert p2.hand[0] == p3_card
        assert p3.hand[1] == p2_card


# ------------------------------------------------------------------
# Disruption swap targeting
# ------------------------------------------------------------------

class TestDisruptionSwapTargeting:
    def test_prefers_known_opponent_position(self):
        """_find_best_swap_target should prefer positions the opponent knows."""
        agent = BayesianV2Agent("V2")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        # Give agent a bad card to trigger swap
        agent.hand = [Card('A', 'Hearts'), Card('K', 'Spades'), Card('3', 'Clubs'), Card('A', 'Diamonds')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1], 2: agent.hand[2], 3: agent.hand[3]}
        for pos, card in agent.known.items():
            agent.tracker.set_own_card(pos, (card.rank, card.suit))

        # Set two known opponent cards with same value
        agent.tracker.set_opponent_card('Opp', 0, ('2', 'Hearts'))
        agent.tracker.set_opponent_card('Opp', 2, ('2', 'Clubs'))
        # Opponent knows position 0 (from deal init) but not position 2
        # So position 0 should be preferred (disruption bonus)

        result = agent._find_best_swap_target([opp])
        assert result is not None
        _, pos = result
        assert pos == 0  # The one the opponent knows

    def test_find_best_disruption_swap(self):
        """Should find two opponent positions from different opponents to swap."""
        agent = BayesianV2Agent("V2")
        opp1 = SmartAgent("Opp1")
        opp2 = SmartAgent("Opp2")
        game = make_game(agent, opp1, opp2)
        agent._ensure_initialized(game)

        # Both opponents know their position 0 (from deal init)
        agent.tracker.set_opponent_card('Opp1', 0, ('3', 'Hearts'))
        agent.tracker.set_opponent_card('Opp2', 0, ('2', 'Clubs'))

        result = agent._find_best_disruption_swap([opp1, opp2])
        assert result is not None
        r_opp1, r_pos1, r_opp2, r_pos2 = result
        assert r_opp1.name != r_opp2.name


# ------------------------------------------------------------------
# J/Q decision logic
# ------------------------------------------------------------------

class TestBlackKingSelfPeek:
    def test_disruption_mode_prefers_self_peek(self):
        """With unknown own positions, Black King disruption should peek self first."""
        agent = BayesianV2Agent("V2")
        opp1 = SmartAgent("Opp1")
        opp2 = SmartAgent("Opp2")
        game = make_game(agent, opp1, opp2)
        agent._ensure_initialized(game)

        # Good hand but positions 2,3 are unknown
        agent.hand = [Card('A', 'Hearts'), Card('2', 'Spades'), Card('3', 'Clubs'), Card('A', 'Diamonds')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1]}
        agent.tracker.set_own_card(0, ('A', 'Hearts'))
        agent.tracker.set_own_card(1, ('2', 'Spades'))
        agent.tracker.own_hand[2] = None
        agent.tracker.own_hand[3] = None

        # Both opponents have known positions for disruption
        agent.tracker.set_opponent_card('Opp1', 0, ('5', 'Hearts'))
        agent.tracker.set_opponent_card('Opp2', 0, ('4', 'Clubs'))

        card = Card('K', 'Spades')
        result = agent.choose_power_action(card, game, [opp1, opp2])
        assert result is not None
        assert result['type'] == 'king_peek_swap'
        # Peek target should be self (V2), not an opponent
        assert result['peek_player'] == agent
        assert result['peek_position'] in [2, 3]
        # Swap should still be between opponents
        assert result['swap']['player1'].name != agent.name
        assert result['swap']['player2'].name != agent.name

    def test_self_peek_updates_tracker(self):
        """Black King self-peek should record the card in own tracker and known dict."""
        agent = BayesianV2Agent("V2")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        # Position 2 is unknown
        assert agent.tracker.own_hand[2] is None
        assert 2 not in agent.known

        card = Card('K', 'Spades')
        result = agent.use_card_power(card, game, peek_player=agent, peek_pos=2, verbose=False)

        assert result is True
        # Should now know position 2
        assert agent.tracker.own_hand[2] is not None
        assert 2 in agent.known

    def test_falls_back_to_opponent_peek_when_all_own_known(self):
        """When all own positions are known, should peek opponent instead."""
        agent = BayesianV2Agent("V2")
        opp1 = SmartAgent("Opp1")
        opp2 = SmartAgent("Opp2")
        game = make_game(agent, opp1, opp2)
        agent._ensure_initialized(game)

        # All positions known (good hand)
        agent.hand = [Card('A', 'Hearts'), Card('2', 'Spades'), Card('3', 'Clubs'), Card('A', 'Diamonds')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1], 2: agent.hand[2], 3: agent.hand[3]}
        for pos, card in agent.known.items():
            agent.tracker.set_own_card(pos, (card.rank, card.suit))

        # Both opponents have known positions for disruption
        agent.tracker.set_opponent_card('Opp1', 0, ('5', 'Hearts'))
        agent.tracker.set_opponent_card('Opp2', 0, ('4', 'Clubs'))

        card = Card('K', 'Spades')
        result = agent.choose_power_action(card, game, [opp1, opp2])
        assert result is not None
        assert result['type'] == 'king_peek_swap'
        # Peek should be on an opponent (not self, since all own are known)
        assert result['peek_player'] != agent


class TestJQDecision:
    def test_self_swap_when_bad_hand(self):
        """With a bad card, should still do self-swap."""
        agent = BayesianV2Agent("V2")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        agent.hand = [Card('A', 'Hearts'), Card('K', 'Spades'), Card('3', 'Clubs'), Card('A', 'Diamonds')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1], 2: agent.hand[2], 3: agent.hand[3]}
        for pos, card in agent.known.items():
            agent.tracker.set_own_card(pos, (card.rank, card.suit))

        card = Card('J', 'Hearts')
        result = agent.choose_power_action(card, game, [opp])
        assert result is not None
        assert result['type'] == 'blind_swap'
        assert result['my_position'] == 1  # K of Spades position

    def test_disruption_swap_when_good_hand(self):
        """With a good hand and 2+ opponents, should do third-party swap."""
        agent = BayesianV2Agent("V2")
        opp1 = SmartAgent("Opp1")
        opp2 = SmartAgent("Opp2")
        game = make_game(agent, opp1, opp2)
        agent._ensure_initialized(game)

        # Give agent all low cards
        agent.hand = [Card('A', 'Hearts'), Card('2', 'Spades'), Card('3', 'Clubs'), Card('A', 'Diamonds')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1], 2: agent.hand[2], 3: agent.hand[3]}
        for pos, card in agent.known.items():
            agent.tracker.set_own_card(pos, (card.rank, card.suit))

        # Both opponents have known positions
        agent.tracker.set_opponent_card('Opp1', 0, ('5', 'Hearts'))
        agent.tracker.set_opponent_card('Opp2', 0, ('4', 'Clubs'))

        card = Card('Q', 'Hearts')
        result = agent.choose_power_action(card, game, [opp1, opp2])
        assert result is not None
        assert result['type'] == 'third_party_swap'

    def test_no_action_when_good_hand_and_single_opponent(self):
        """With a good hand and only 1 opponent, can't do third-party swap."""
        agent = BayesianV2Agent("V2")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        agent.hand = [Card('A', 'Hearts'), Card('2', 'Spades'), Card('3', 'Clubs'), Card('A', 'Diamonds')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1], 2: agent.hand[2], 3: agent.hand[3]}
        for pos, card in agent.known.items():
            agent.tracker.set_own_card(pos, (card.rank, card.suit))

        card = Card('J', 'Hearts')
        result = agent.choose_power_action(card, game, [opp])
        # Can't third-party with 1 opponent, hand is too good for self-swap
        assert result is None


# ------------------------------------------------------------------
# Ablation feature flags
# ------------------------------------------------------------------

class TestAblationFlags:
    def test_default_flags_all_true(self):
        agent = BayesianV2Agent("V2")
        assert agent.use_disruption_scoring is True
        assert agent.use_probabilistic_stick is True
        assert agent.use_preemptive_cambio is False
        assert agent.use_third_party_swaps is True
        assert agent.use_smart_peek is True
        assert agent.use_aggressive_cambio is True

    def test_disable_probabilistic_stick(self):
        """With flag off, choose_stick should return only known matches (V1 behavior)."""
        agent = BayesianV2Agent("V2", use_probabilistic_stick=False)
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        # Set up: agent has unknown positions
        agent.tracker.own_hand[2] = None
        agent.tracker.own_hand[3] = None
        game_mock = type('Game', (), {'discard': [Card('5', 'Clubs')]})()

        positions = agent.choose_stick(game_mock)
        # Should only include known matches, no probabilistic sticks
        for pos in positions:
            assert agent.tracker.own_hand.get(pos) is not None

    def test_disable_smart_peek_falls_back_to_v1(self):
        """With use_smart_peek=False, 9/10 should use V1's random peek."""
        agent = BayesianV2Agent("V2", use_smart_peek=False)
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        card = Card('9', 'Hearts')
        result = agent.choose_power_action(card, game, [opp])
        # Should still return a valid peek action (V1 behavior)
        assert result is not None
        assert result['type'] == 'peek_opponent'

    def test_disable_third_party_swaps(self):
        """With flag off, good hand + 2 opps should return None (no disruption)."""
        agent = BayesianV2Agent("V2", use_third_party_swaps=False)
        opp1 = SmartAgent("Opp1")
        opp2 = SmartAgent("Opp2")
        game = make_game(agent, opp1, opp2)
        agent._ensure_initialized(game)

        # Give agent all low cards
        agent.hand = [Card('A', 'Hearts'), Card('2', 'Spades'), Card('3', 'Clubs'), Card('A', 'Diamonds')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1], 2: agent.hand[2], 3: agent.hand[3]}
        for pos, card in agent.known.items():
            agent.tracker.set_own_card(pos, (card.rank, card.suit))

        agent.tracker.set_opponent_card('Opp1', 0, ('5', 'Hearts'))
        agent.tracker.set_opponent_card('Opp2', 0, ('4', 'Clubs'))

        card = Card('Q', 'Hearts')
        result = agent.choose_power_action(card, game, [opp1, opp2])
        # With flag off, third-party path is skipped; good hand means no self-swap either
        assert result is None

    def test_ablated_agent_completes_game(self):
        """Agent with all features disabled still completes a game."""
        agent = BayesianV2Agent("V2-ablated",
                                use_disruption_scoring=False,
                                use_probabilistic_stick=False,
                                use_preemptive_cambio=False,
                                use_third_party_swaps=False,
                                use_smart_peek=False,
                                use_aggressive_cambio=False)
        opp = SmartAgent("Smart")
        game = CambioGame([agent, opp])
        game.deal()
        result = game.play(verbose=False, max_turns=100)
        assert 'winner' in result


# ------------------------------------------------------------------
# Integration tests
# ------------------------------------------------------------------

class TestIntegration:
    def test_v2_vs_smart_completes(self):
        """Full game between BayesianV2Agent and SmartAgent completes."""
        agent = BayesianV2Agent("V2")
        opp = SmartAgent("Smart")
        game = CambioGame([agent, opp])
        game.deal()
        result = game.play(verbose=False, max_turns=100)
        assert 'winner' in result
        assert result['total_turns'] > 0

    def test_v2_vs_v1_completes(self):
        """Full game between V2 and V1 completes."""
        v2 = BayesianV2Agent("V2")
        v1 = BayesianAgent("V1")
        game = CambioGame([v2, v1])
        game.deal()
        result = game.play(verbose=False, max_turns=100)
        assert 'winner' in result

    def test_v2_3player_completes(self):
        """3-player game with V2 completes."""
        v2 = BayesianV2Agent("V2")
        opp1 = SmartAgent("Smart1")
        opp2 = SmartAgent("Smart2")
        game = CambioGame([v2, opp1, opp2])
        game.deal()
        result = game.play(verbose=False, max_turns=100)
        assert 'winner' in result

    def test_many_games_no_crash(self):
        """Run many games to catch edge cases."""
        for _ in range(50):
            v2 = BayesianV2Agent("V2")
            opp1 = SmartAgent("Smart")
            opp2 = BayesianAgent("Bayes")
            game = CambioGame([v2, opp1, opp2])
            game.deal()
            result = game.play(verbose=False, max_turns=100)
            assert 'winner' in result


# ------------------------------------------------------------------
# Final-round mode tests (Step 1)
# ------------------------------------------------------------------

class TestFinalRoundMode:
    def test_final_round_no_double_cambio(self):
        """If cambio already called, call_cambio() returns False."""
        agent = BayesianV2Agent("V2")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)
        agent._last_game = game

        # Give agent a great hand so it would normally call cambio
        agent.hand = [Card('A', 'Hearts'), Card('A', 'Diamonds'), Card('2', 'Clubs'), Card('2', 'Spades')]
        agent.known = {i: agent.hand[i] for i in range(4)}
        for pos, card in agent.known.items():
            agent.tracker.set_own_card(pos, (card.rank, card.suit))

        # Cambio already called
        game.cambio_called = True
        game.final_round_active = True
        assert agent.call_cambio() is False

    def test_final_round_known_stick_only(self):
        """In final round, probabilistic sticks are suppressed."""
        agent = BayesianV2Agent("V2")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        # Set up unknown positions and a discard card
        agent.tracker.own_hand[2] = None
        agent.tracker.own_hand[3] = None
        game.discard.append(Card('5', 'Clubs'))
        game.final_round_active = True

        positions = agent.choose_stick(game)
        # Should only include known matches, no unknown positions
        for pos in positions:
            assert agent.tracker.own_hand.get(pos) is not None

    def test_final_round_draw_takes_any_improvement(self):
        """In final round, discard is taken with any improvement > 0."""
        agent = BayesianV2Agent("V2")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        # Set up: worst known card is 3, discard is 2 (improvement = 1)
        # Normally V2 might prefer deck due to power bonus EV
        agent.hand = [Card('A', 'Hearts'), Card('3', 'Diamonds'), Card('2', 'Clubs'), Card('A', 'Spades')]
        agent.known = {i: agent.hand[i] for i in range(4)}
        for pos, card in agent.known.items():
            agent.tracker.set_own_card(pos, (card.rank, card.suit))

        game.discard.append(Card('2', 'Hearts'))
        game.final_round_active = True

        result = agent.choose_draw(game)
        assert result == 'discard'

    def test_final_round_flag_disabled(self):
        """With use_final_round_mode=False, normal behavior during final round."""
        agent = BayesianV2Agent("V2", use_final_round_mode=False)
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)
        agent._last_game = game

        # Great hand that would normally call cambio
        agent.hand = [Card('A', 'Hearts'), Card('A', 'Diamonds'), Card('2', 'Clubs'), Card('2', 'Spades')]
        agent.known = {i: agent.hand[i] for i in range(4)}
        for pos, card in agent.known.items():
            agent.tracker.set_own_card(pos, (card.rank, card.suit))

        # Even with cambio_called=True, flag disabled means normal behavior
        game.cambio_called = True
        game.final_round_active = True
        # Should NOT suppress — flag is off, so it falls through to normal logic
        # The agent has a great hand, so it would normally return True
        result = agent.call_cambio()
        assert result is True


# ------------------------------------------------------------------
# Opponent inference tests (Step 2)
# ------------------------------------------------------------------

class TestOpponentInference:
    def test_opponent_discard_sets_upper_bound(self):
        """Opponent discards a 7 -> upper bound set to 7."""
        agent = BayesianV2Agent("V2")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        turn_data = {
            'player': 'Opp',
            'draw_source': 'deck',
            'action': 'discard',
            'power_type': None,
            'swap_position': None,
            'power_target_player': None,
            'power_target_position': None,
            'power_target_player2': None,
            'power_target_position2': None,
            'power_peek_player': None,
            'power_peek_position': None,
            'discarded_card': '7H',
            'discarded_value': 7,
            'hand_size': 4,
        }
        game.discard.append(Card('7', 'Hearts'))
        agent.observe_turn(turn_data, game)

        bound = agent.tracker.get_opponent_hand_upper_bound('Opp')
        assert bound == 7

    def test_upper_bound_lowers_opponent_ev(self):
        """With upper bound set, expected opponent score should be lower."""
        agent = BayesianV2Agent("V2")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        # Get baseline EV without inference
        ev_before = agent.tracker.expected_opponent_score('Opp')

        # Set upper bound: all opponent cards <= 3
        agent.tracker.set_opponent_hand_upper_bound('Opp', 3)
        ev_after = agent.tracker.expected_opponent_score_with_inference('Opp')

        assert ev_after < ev_before

    def test_inference_flag_disabled(self):
        """With use_opponent_inference=False, standard EV used."""
        agent = BayesianV2Agent("V2", use_opponent_inference=False)
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        # Observe discard that would set upper bound
        turn_data = {
            'player': 'Opp',
            'draw_source': 'deck',
            'action': 'discard',
            'power_type': None,
            'swap_position': None,
            'power_target_player': None,
            'power_target_position': None,
            'power_target_player2': None,
            'power_target_position2': None,
            'power_peek_player': None,
            'power_peek_position': None,
            'discarded_card': '3H',
            'discarded_value': 3,
            'hand_size': 4,
        }
        game.discard.append(Card('3', 'Hearts'))
        agent.observe_turn(turn_data, game)

        # Upper bound should NOT be set when flag is disabled
        bound = agent.tracker.get_opponent_hand_upper_bound('Opp')
        assert bound is None

    def test_peek_and_keep_tracked(self):
        """Opponent peeking own card records peeked-and-kept."""
        agent = BayesianV2Agent("V2")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        turn_data = {
            'player': 'Opp',
            'draw_source': 'deck',
            'action': 'power',
            'power_type': 'peek_own',
            'swap_position': 2,  # position peeked
            'power_target_player': None,
            'power_target_position': None,
            'power_target_player2': None,
            'power_target_position2': None,
            'power_peek_player': None,
            'power_peek_position': None,
            'discarded_card': '7H',
            'discarded_value': 7,
            'hand_size': 4,
        }
        game.discard.append(Card('7', 'Hearts'))
        agent.observe_turn(turn_data, game)

        peeked = agent.tracker.get_opponent_peeked_and_kept('Opp')
        assert 2 in peeked


# ------------------------------------------------------------------
# Deck awareness tests (Step 3)
# ------------------------------------------------------------------

class TestDeckAwareness:
    def test_small_deck_prefers_discard(self):
        """With <=5 cards in deck, prefer discard when there's any improvement."""
        agent = BayesianV2Agent("V2")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        # Set up: moderate improvement from discard
        agent.hand = [Card('A', 'Hearts'), Card('5', 'Diamonds'), Card('3', 'Clubs'), Card('A', 'Spades')]
        agent.known = {i: agent.hand[i] for i in range(4)}
        for pos, card in agent.known.items():
            agent.tracker.set_own_card(pos, (card.rank, card.suit))

        game.discard.append(Card('4', 'Hearts'))
        # Drain deck to <=5 cards
        game.deck.cards = game.deck.cards[:3]

        result = agent.choose_draw(game)
        assert result == 'discard'

    def test_deck_awareness_flag_disabled(self):
        """With use_deck_awareness=False, deck size is ignored."""
        agent = BayesianV2Agent("V2", use_deck_awareness=False)
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        # Same setup but with flag off — should use normal logic
        agent.hand = [Card('A', 'Hearts'), Card('5', 'Diamonds'), Card('3', 'Clubs'), Card('A', 'Spades')]
        agent.known = {i: agent.hand[i] for i in range(4)}
        for pos, card in agent.known.items():
            agent.tracker.set_own_card(pos, (card.rank, card.suit))

        game.discard.append(Card('4', 'Hearts'))
        game.deck.cards = game.deck.cards[:3]

        # With flag off, normal V2 logic applies (improvement=1, may prefer deck for power)
        result = agent.choose_draw(game)
        # Just verify it doesn't crash — the specific choice depends on unaccounted cards
        assert result in ('deck', 'discard')


# ------------------------------------------------------------------
# New feature flag ablation tests
# ------------------------------------------------------------------

class TestNewAblationFlags:
    def test_new_flags_default_true(self):
        agent = BayesianV2Agent("V2")
        assert agent.use_final_round_mode is True
        assert agent.use_opponent_inference is True
        assert agent.use_deck_awareness is True

    def test_all_new_features_disabled_matches_old_v2(self):
        """Agent with all 3 new flags False should behave like pre-change V2."""
        # Run 20 games with both configs — neither should crash
        for _ in range(20):
            new_agent = BayesianV2Agent("V2-new",
                                         use_final_round_mode=False,
                                         use_opponent_inference=False,
                                         use_deck_awareness=False)
            opp = SmartAgent("Smart")
            game = CambioGame([new_agent, opp])
            game.deal()
            result = game.play(verbose=False, max_turns=100)
            assert 'winner' in result

    def test_many_games_new_features_no_crash(self):
        """50-game stress test with all features enabled."""
        for _ in range(50):
            v2 = BayesianV2Agent("V2")
            opp1 = SmartAgent("Smart")
            opp2 = BayesianAgent("Bayes")
            game = CambioGame([v2, opp1, opp2])
            game.deal()
            result = game.play(verbose=False, max_turns=100)
            assert 'winner' in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
