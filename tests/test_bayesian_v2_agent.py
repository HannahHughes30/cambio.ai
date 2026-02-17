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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
