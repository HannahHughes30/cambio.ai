"""Tests for SmartAgent."""

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
    def test_calls_cambio(self):
        agent = SmartAgent()
        assert agent.call_cambio() is True

if __name__ == "__main__":
    pytest.main([__file__, "-v"])