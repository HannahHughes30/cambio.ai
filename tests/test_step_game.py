"""Tests for StepGame wrapper."""

import sys
from pathlib import Path
import importlib.util

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from game.step_game import (
    StepGame, GamePhase,
    ACTION_DRAW_DECK, ACTION_DRAW_DISCARD,
    ACTION_DISCARD, ACTION_SWAP_BASE,
    ACTION_PEEK_OWN_BASE, ACTION_PEEK_OPP_BASE,
    ACTION_SWAP_CARDS_BASE, ACTION_SKIP_POWER,
    ACTION_STICK_BASE, ACTION_STICK_PASS,
    ACTION_CAMBIO, ACTION_PASS_CAMBIO,
    Card, Player,
)


class TestStepGameInit:
    """Test initialization and reset."""

    def test_init_creates_game(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        state = g.reset()

        assert g.game is not None
        assert g.phase in [GamePhase.DRAW, GamePhase.OPPONENT_TURN]

    def test_reset_returns_state(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        state = g.reset()

        assert 'phase' in state
        assert 'current_player' in state
        assert 'my_hand' in state
        assert 'valid_actions' in state

    def test_initial_state_has_4_cards(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        state = g.reset()

        assert len(state['my_hand']) == 4

    def test_initial_known_cards(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        state = g.reset()

        # Players know positions 0 and 1 initially
        assert 0 in state['my_known']
        assert 1 in state['my_known']


class TestPhaseTransitions:
    """Test phase flow: DRAW -> ACTION -> POWER/STICK -> CAMBIO."""

    def test_draw_phase_to_action(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        g.reset()

        # Force agent's turn
        g.game.current_player = 0
        g.phase = GamePhase.DRAW

        state, result = g.step(ACTION_DRAW_DECK)
        assert state['phase'] == GamePhase.ACTION
        assert result['drawn_card'] is not None

    def test_action_discard_no_power(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        g.reset()

        # Setup: draw a non-power card
        g.game.current_player = 0
        g.phase = GamePhase.DRAW
        g.step(ACTION_DRAW_DECK)

        # Replace drawn card with non-power card
        g.drawn_card = Card('2', 'Hearts')

        state, result = g.step(ACTION_DISCARD)
        # Non-power card goes to stick window
        assert state['phase'] == GamePhase.STICK_WINDOW

    def test_action_discard_with_power(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        g.reset()

        g.game.current_player = 0
        g.phase = GamePhase.DRAW
        g.step(ACTION_DRAW_DECK)

        # Replace drawn card with power card
        g.drawn_card = Card('7', 'Hearts')

        state, result = g.step(ACTION_DISCARD)
        # Power card goes to power phase
        assert state['phase'] == GamePhase.POWER

    def test_stick_window_to_cambio(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        g.reset()

        g.game.current_player = 0
        g.phase = GamePhase.STICK_WINDOW

        state, result = g.step(ACTION_STICK_PASS)
        assert state['phase'] == GamePhase.CAMBIO_DECISION


class TestValidActions:
    """Test that valid actions are correct per phase."""

    def test_draw_phase_valid_actions(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        g.reset()

        g.game.current_player = 0
        g.phase = GamePhase.DRAW
        # Add a discard to test both options
        g.game.discard.append(Card('5', 'Hearts'))

        valid = g.get_valid_actions()
        assert ACTION_DRAW_DECK in valid
        assert ACTION_DRAW_DISCARD in valid

    def test_draw_phase_no_discard(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        g.reset()

        g.game.current_player = 0
        g.phase = GamePhase.DRAW
        g.game.discard = []

        valid = g.get_valid_actions()
        assert ACTION_DRAW_DECK in valid
        assert ACTION_DRAW_DISCARD not in valid

    def test_action_phase_valid_actions(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        g.reset()

        g.game.current_player = 0
        g.phase = GamePhase.ACTION
        g.drawn_card = Card('3', 'Hearts')

        valid = g.get_valid_actions()
        assert ACTION_DISCARD in valid
        # Should have swap actions for 4 positions
        for i in range(4):
            assert (ACTION_SWAP_BASE + i) in valid

    def test_cambio_phase_valid_actions(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        g.reset()

        g.game.current_player = 0
        g.phase = GamePhase.CAMBIO_DECISION

        valid = g.get_valid_actions()
        assert ACTION_CAMBIO in valid
        assert ACTION_PASS_CAMBIO in valid

    def test_cambio_already_called(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        g.reset()

        g.game.current_player = 0
        g.game.cambio_called = True
        g.phase = GamePhase.CAMBIO_DECISION

        valid = g.get_valid_actions()
        assert ACTION_CAMBIO not in valid
        assert ACTION_PASS_CAMBIO in valid

    def test_game_over_no_actions(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        g.reset()

        g.phase = GamePhase.GAME_OVER
        valid = g.get_valid_actions()
        assert valid == []


class TestPowerCards:
    """Test power card integration."""

    def test_power_7_8_peek_own(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        g.reset()

        g.game.current_player = 0
        g.phase = GamePhase.POWER
        g.discarded_card = Card('7', 'Hearts')

        valid = g.get_valid_actions()
        assert ACTION_SKIP_POWER in valid
        # Should have peek own actions for 4 positions
        for i in range(4):
            assert (ACTION_PEEK_OWN_BASE + i) in valid

    def test_power_9_10_peek_opponent(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        g.reset()

        g.game.current_player = 0
        g.phase = GamePhase.POWER
        g.discarded_card = Card('9', 'Clubs')

        valid = g.get_valid_actions()
        assert ACTION_SKIP_POWER in valid
        # Should have peek opponent actions
        for i in range(4):
            assert (ACTION_PEEK_OPP_BASE + i) in valid

    def test_power_jq_blind_swap(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        g.reset()

        g.game.current_player = 0
        g.phase = GamePhase.POWER
        g.discarded_card = Card('J', 'Spades')

        valid = g.get_valid_actions()
        assert ACTION_SKIP_POWER in valid
        # Should have swap actions (4x4 = 16 combinations)
        swap_actions = [a for a in valid if ACTION_SWAP_CARDS_BASE <= a <= ACTION_SWAP_CARDS_BASE + 15]
        assert len(swap_actions) == 16

    def test_power_black_king(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        g.reset()

        g.game.current_player = 0
        g.phase = GamePhase.POWER
        g.discarded_card = Card('K', 'Spades')  # Black King

        valid = g.get_valid_actions()
        assert ACTION_SKIP_POWER in valid
        # Should have swap actions like J/Q
        swap_actions = [a for a in valid if ACTION_SWAP_CARDS_BASE <= a <= ACTION_SWAP_CARDS_BASE + 15]
        assert len(swap_actions) == 16

    def test_power_red_king_no_power(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        g.reset()

        g.game.current_player = 0
        g.phase = GamePhase.POWER
        g.discarded_card = Card('K', 'Hearts')  # Red King (no swap power)

        valid = g.get_valid_actions()
        # Red kings don't have the swap power
        assert valid == [ACTION_SKIP_POWER]

    def test_peek_own_updates_known(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        g.reset()

        g.game.current_player = 0
        g.phase = GamePhase.POWER
        g.discarded_card = Card('7', 'Hearts')

        # Clear position 2 knowledge
        if 2 in p1.known:
            del p1.known[2]

        state, result = g.step(ACTION_PEEK_OWN_BASE + 2)

        assert result['used_power'] is True
        assert result['power_type'] == 'peek_own'
        assert 2 in p1.known

    def test_blind_swap_invalidates_knowledge(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        g.reset()

        g.game.current_player = 0
        g.phase = GamePhase.POWER
        g.discarded_card = Card('J', 'Hearts')

        # Agent knows position 0
        assert 0 in p1.known

        # Swap position 0 with opponent position 0
        action = ACTION_SWAP_CARDS_BASE + 0  # my_pos=0, opp_pos=0
        state, result = g.step(action)

        # Knowledge of position 0 should be cleared
        assert 0 not in p1.known


class TestStickMechanic:
    """Test stick window functionality."""

    def test_stick_window_actions(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        g.reset()

        g.game.current_player = 0
        g.phase = GamePhase.STICK_WINDOW
        g.game.discard.append(Card('5', 'Hearts'))

        valid = g.get_valid_actions()
        assert ACTION_STICK_PASS in valid
        for i in range(4):
            assert (ACTION_STICK_BASE + i) in valid

    def test_successful_stick(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        g.reset()

        g.game.current_player = 0
        g.phase = GamePhase.STICK_WINDOW

        # Put a 5 on discard and a 5 in player's hand
        g.game.discard.append(Card('5', 'Hearts'))
        p1.hand[0] = Card('5', 'Spades')

        state, result = g.step(ACTION_STICK_BASE + 0)

        assert result['attempted'] is True
        assert result['success'] is True
        # Hand should now have 3 cards
        assert len(p1.hand) == 3

    def test_failed_stick_penalty(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        g.reset()

        g.game.current_player = 0
        g.phase = GamePhase.STICK_WINDOW

        # Put a 5 on discard but different card in hand
        g.game.discard.append(Card('5', 'Hearts'))
        p1.hand[0] = Card('3', 'Spades')  # Different rank

        initial_hand_size = len(p1.hand)
        state, result = g.step(ACTION_STICK_BASE + 0)

        assert result['attempted'] is True
        assert result['success'] is False
        # Hand should now have 5 cards (penalty)
        assert len(p1.hand) == initial_hand_size + 1


class TestCambio:
    """Test CAMBIO calling."""

    def test_call_cambio(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        g.reset()

        g.game.current_player = 0
        g.phase = GamePhase.CAMBIO_DECISION

        state, result = g.step(ACTION_CAMBIO)

        assert result['called_cambio'] is True
        assert g.game.cambio_called is True
        # After cambio, opponent plays their turn, then game ends
        # In 2-player game, final_round_active becomes False when back to caller
        assert state['phase'] == GamePhase.GAME_OVER

    def test_pass_cambio(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        g.reset()

        g.game.current_player = 0
        g.phase = GamePhase.CAMBIO_DECISION

        state, result = g.step(ACTION_PASS_CAMBIO)

        assert result['called_cambio'] is False
        assert g.game.cambio_called is False


class TestGameCompletion:
    """Test game ending conditions."""

    def test_game_over_property(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        g.reset()

        assert g.is_game_over() is False

        g.phase = GamePhase.GAME_OVER
        assert g.is_game_over() is True

    def test_get_scores(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        g.reset()

        scores = g.get_scores()
        assert "Agent" in scores
        assert "Opponent" in scores

    def test_get_winner(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        g.reset()

        # Set known hands
        p1.hand = [Card('A', 'Hearts'), Card('2', 'Hearts')]  # Score: 3
        p2.hand = [Card('K', 'Hearts'), Card('K', 'Diamonds')]  # Score: -2 (red kings)

        winner, score = g.get_winner()
        assert winner == "Opponent"
        assert score == -2


class TestInvalidActions:
    """Test error handling for invalid actions."""

    def test_invalid_action_raises(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        g.reset()

        g.game.current_player = 0
        g.phase = GamePhase.DRAW

        with pytest.raises(ValueError):
            g.step(ACTION_CAMBIO)  # Invalid during DRAW phase


class TestFullTurn:
    """Test complete turn flow."""

    def test_full_turn_no_power(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        g.reset()

        g.game.current_player = 0
        g.phase = GamePhase.DRAW

        # DRAW
        state, _ = g.step(ACTION_DRAW_DECK)
        assert state['phase'] == GamePhase.ACTION

        # Replace with non-power card
        g.drawn_card = Card('2', 'Hearts')

        # ACTION - discard
        state, _ = g.step(ACTION_DISCARD)
        assert state['phase'] == GamePhase.STICK_WINDOW

        # STICK - pass
        state, _ = g.step(ACTION_STICK_PASS)
        assert state['phase'] == GamePhase.CAMBIO_DECISION

        # CAMBIO - pass
        state, _ = g.step(ACTION_PASS_CAMBIO)
        # Should advance to opponent turn or back to draw
        assert state['phase'] in [GamePhase.DRAW, GamePhase.OPPONENT_TURN, GamePhase.GAME_OVER]

    def test_full_turn_with_power(self):
        p1, p2 = Player("Agent"), Player("Opponent")
        g = StepGame([p1, p2])
        g.reset()

        g.game.current_player = 0
        g.phase = GamePhase.DRAW

        # DRAW
        state, _ = g.step(ACTION_DRAW_DECK)

        # Replace with power card (7)
        g.drawn_card = Card('7', 'Hearts')

        # ACTION - discard
        state, _ = g.step(ACTION_DISCARD)
        assert state['phase'] == GamePhase.POWER

        # POWER - use it
        state, _ = g.step(ACTION_PEEK_OWN_BASE + 2)
        assert state['phase'] == GamePhase.STICK_WINDOW

        # STICK - pass
        state, _ = g.step(ACTION_STICK_PASS)
        assert state['phase'] == GamePhase.CAMBIO_DECISION


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
