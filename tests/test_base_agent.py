"""Tests for BaseAgent."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from agents.base_agent import BaseAgent
from game import Card, CambioGame, Player


class TestBaseAgentInit:
    def test_creates_agent(self):
        agent = BaseAgent("TestAgent")
        assert agent.name == "TestAgent"

    def test_default_name(self):
        agent = BaseAgent()
        assert agent.name == "BaseAgent"


class MockGame:
    """Minimal game mock with a discard pile."""
    def __init__(self, discard=None):
        self.discard = discard or []


class TestChooseDraw:
    def test_draws_from_deck_by_default(self):
        agent = BaseAgent()
        game = MockGame()
        assert agent.choose_draw(game) == 'deck'

    def test_draws_low_card_from_discard(self):
        agent = BaseAgent()
        game = MockGame([Card('2', 'Hearts')])  # Value 2 < 4
        assert agent.choose_draw(game) == 'discard'

    def test_draws_from_deck_for_high_discard(self):
        agent = BaseAgent()
        game = MockGame([Card('K', 'Spades')])
        assert agent.choose_draw(game) == 'deck'

    def test_draws_from_deck_for_4(self):
        agent = BaseAgent()
        game = MockGame([Card('4', 'Hearts')])  # Value 4 is not < 4
        assert agent.choose_draw(game) == 'deck'

    def test_draws_ace_from_discard(self):
        agent = BaseAgent()
        game = MockGame([Card('A', 'Hearts')])  # Value 1 < 4
        assert agent.choose_draw(game) == 'discard'

    def test_draws_3_from_discard(self):
        agent = BaseAgent()
        game = MockGame([Card('3', 'Hearts')])  # Value 3 < 4
        assert agent.choose_draw(game) == 'discard'


class TestChooseAction:
    def test_discards_high_card_with_low_hand(self):
        agent = BaseAgent()
        agent.hand = [Card('A', 'Hearts'), Card('2', 'Hearts'), Card('3', 'Hearts'), Card('4', 'Hearts')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1]}

        drawn = Card('K', 'Spades')  # Value 10
        action = agent.choose_action(drawn)
        assert action['type'] == 'discard'

    def test_swaps_with_known_high_card(self):
        agent = BaseAgent()
        agent.hand = [Card('K', 'Spades'), Card('Q', 'Hearts'), Card('3', 'Hearts'), Card('4', 'Hearts')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1]}

        drawn = Card('2', 'Hearts')  # Value 2
        action = agent.choose_action(drawn)
        assert action['type'] == 'swap'
        assert action['position'] in [0, 1]  # Should swap with K or Q

    def test_swaps_with_worst_card(self):
        agent = BaseAgent()
        agent.hand = [Card('K', 'Spades'), Card('5', 'Hearts'), Card('3', 'Hearts'), Card('4', 'Hearts')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1]}  # K=10, 5=5

        drawn = Card('2', 'Hearts')
        action = agent.choose_action(drawn)
        assert action['type'] == 'swap'
        assert action['position'] == 0  # K is worst (10 > 5)


class TestCallCambio:
    def test_never_calls_cambio(self):
        agent = BaseAgent()
        assert agent.call_cambio() is False


class TestPowerActions:
    def test_peek_own_unknown(self):
        agent = BaseAgent()
        agent.hand = [Card('A', 'Hearts'), Card('2', 'Hearts'), Card('3', 'Hearts'), Card('4', 'Hearts')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1]}

        card = Card('7', 'Hearts')
        action = agent.choose_power_action(card, None, [])

        assert action is not None
        assert action['type'] == 'peek_own'
        assert action['position'] in [2, 3]  # Unknown positions

    def test_skip_peek_when_all_known(self):
        agent = BaseAgent()
        agent.hand = [Card('A', 'Hearts'), Card('2', 'Hearts'), Card('3', 'Hearts'), Card('4', 'Hearts')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1], 2: agent.hand[2], 3: agent.hand[3]}

        card = Card('7', 'Hearts')
        action = agent.choose_power_action(card, None, [])

        assert action is None  # No unknown cards to peek


class TestGameIntegration:
    def test_agent_plays_game(self):
        agent = BaseAgent("Agent")
        opponent = Player("Opponent")

        game = CambioGame([agent, opponent])
        game.deal()

        # Agent should have hand and known cards
        assert len(agent.hand) == 4
        assert 0 in agent.known
        assert 1 in agent.known


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
