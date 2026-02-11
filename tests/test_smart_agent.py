"""Tests for SmartAgent."""

from random import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from agents.smart_agent import SmartAgent
from game import Card, CambioGame, Player

class TestSmartAgentInit:
    def test_creates_agent(self):
        agent = SmartAgent("TestAgent")
        assert agent.name == "TestAgent"

    def test_default_name(self):
        agent = SmartAgent()
        assert agent.name == "SmartAgent"

class TestCallCambio:
    def test_calls_cambio_by_default(self):
        agent = SmartAgent()
        assert agent.call_cambio() is False

    def test_calls_cambio_with_confidence(self):
        agent = SmartAgent()
        agent.hand = [Card('A', 'Hearts'), Card('A', 'Spades'), Card('A', 'Diamonds'), Card('A', 'Clubs')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1], 2: agent.hand[2], 3: agent.hand[3]}
        opponent = SmartAgent("Opponent")
        opponent.hand = [Card('5', 'Hearts'), Card('6', 'Spades'), Card('7', 'Diamonds'), Card('8', 'Clubs')]
        agent.opponent_known = {opponent: {0: opponent.hand[0], 1: opponent.hand[1], 2: opponent.hand[2], 3: opponent.hand[3]}}
        assert agent.call_cambio() is True

class TestSmartAgentPowerActions:
    def test_power_action_no_card(self):
        agent = SmartAgent()
        agent.hand = [Card('A', 'Hearts')]
        result = agent.choose_power_action(agent.hand[0], None, [])
        assert result is None

    def test_power_action_peak_own(self):
        agent = SmartAgent()
        agent.hand = [Card('7', 'Hearts'), Card('8', 'Spades'), Card('9', 'Diamonds'), Card('10', 'Clubs')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1]}
        result = agent.choose_power_action(agent.hand[0], None, [])
        assert result == {'type': 'peek_own', 'position': 2}

    def test_power_action_peek_opponent(self):
        agent = SmartAgent()
        agent.hand = [Card('A', 'Hearts'), Card('2', 'Spades'), Card('9', 'Diamonds'), Card('10', 'Clubs')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1]}

        opponent = SmartAgent("Opponent")
        opponent.hand = [Card('5', 'Hearts')]
        opponent.known = {0: opponent.hand[0]}
        opponents = [opponent]
        result = agent.choose_power_action(agent.hand[2], None, opponents)
        assert result == {'type': 'peek_opponent', 
                          'opponent': opponent,
                          'position': 0}

    def test_power_action_blind_swap(self):
        agent = SmartAgent()
        agent.hand = [Card('5', 'Hearts'), Card('6', 'Spades'), Card('J', 'Diamonds'), Card('Q', 'Clubs')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1], 2: agent.hand[2], 3: agent.hand[3]}
        
        opponent = SmartAgent("Opponent")
        opponent.hand = [Card('5', 'Hearts')]
        opponent.known = {0: opponent.hand[0]}
        opponents = [opponent]
        result = agent.choose_power_action(agent.hand[2], None, opponents)
        assert result == {'type': 'blind_swap', 
                          'my_position': 2,
                          'opponent': opponents[0],
                          'opp_position': 0}

    def test_power_action_king_swap(self):
        agent = SmartAgent()
        agent.hand = [Card('K', 'Spades'), Card('6', 'Clubs'), Card('3', 'Hearts'), Card('4', 'Hearts')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1], 2: agent.hand[2], 3: agent.hand[3]}
        
        opp_A = SmartAgent("Opponent_A")
        opp_A.hand = [Card('A', 'Hearts')]
        opp_A.known = {0: opp_A.hand[0]}
        opp_B = SmartAgent("Opponent_B")
        opp_B.hand = [Card('10', 'Clubs')]
        opp_B.known = {0: opp_B.hand[0]}
        opponents = [opp_A, opp_B]
        result = agent.choose_power_action(agent.hand[0], None, opponents)
        print(result)
        assert result == {'type': 'king_swap', 
                        'my_position': 0,
                        'opponent': opponents[0],
                        'opp_position': 0}

    

if __name__ == "__main__":
    pytest.main([__file__, "-v"])