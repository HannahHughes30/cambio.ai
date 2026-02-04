"""Step-based game wrapper for RL training."""

import sys
from pathlib import Path
from enum import Enum
import importlib.util

# Import from game.py directly (avoiding package name collision)
_game_path = Path(__file__).parent.parent / "game.py"
_spec = importlib.util.spec_from_file_location("game_module", _game_path)
_game_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_game_module)

Card = _game_module.Card
Deck = _game_module.Deck
Player = _game_module.Player
CambioGame = _game_module.CambioGame


class GamePhase(Enum):
    DRAW = 0           # Choose deck or discard
    ACTION = 1         # Swap with hand position or discard
    POWER = 2          # Use power card ability (if applicable)
    STICK_WINDOW = 3   # Opportunity to stick matching cards
    CAMBIO_DECISION = 4  # Call CAMBIO or pass
    OPPONENT_TURN = 5  # Waiting for opponent
    GAME_OVER = 6


# Action ID constants
ACTION_DRAW_DECK = 0
ACTION_DRAW_DISCARD = 1
ACTION_DISCARD = 2
ACTION_SWAP_BASE = 3  # 3-6: swap with position 0-3
ACTION_PEEK_OWN_BASE = 7  # 7-10: peek own position 0-3
ACTION_PEEK_OPP_BASE = 11  # 11-14: peek opponent position 0-3
ACTION_SWAP_CARDS_BASE = 15  # 15-30: swap my_pos x opp_pos (4x4=16 combinations)
ACTION_SKIP_POWER = 31
ACTION_STICK_BASE = 32  # 32-35: stick position 0-3
ACTION_STICK_PASS = 36
ACTION_CAMBIO = 37
ACTION_PASS_CAMBIO = 38


class StepGame:
    """Step-based wrapper for CambioGame that yields control between decisions."""

    def __init__(self, players: list):
        """Initialize with list of Player objects."""
        self.players = players
        self.game = None
        self.phase = None
        self.drawn_card = None
        self.discarded_card = None  # Card that was discarded (for power check)
        self.agent_index = 0  # The agent is always player 0
        self._power_result = None  # Store result of power card usage

    def reset(self) -> dict:
        """Reset game and return initial state."""
        # Reset player hands and known cards
        for p in self.players:
            p.hand = []
            p.known = {}

        # Create new game instance
        self.game = CambioGame(self.players)
        self.game.deal()

        # Set initial phase
        if self.game.current_player == self.agent_index:
            self.phase = GamePhase.DRAW
        else:
            self.phase = GamePhase.OPPONENT_TURN

        self.drawn_card = None
        self.discarded_card = None
        self._power_result = None

        return self.get_state()

    def get_state(self) -> dict:
        """Get current game state from agent's perspective."""
        agent = self.players[self.agent_index]
        opp_index = 1 - self.agent_index
        opponent = self.players[opp_index]

        return {
            'phase': self.phase,
            'current_player': self.game.current_player,
            'my_hand': list(agent.hand),
            'my_known': dict(agent.known),
            'opp_hand_size': len(opponent.hand),
            'discard_top': self.game.discard[-1] if self.game.discard else None,
            'deck_size': len(self.game.deck.cards),
            'drawn_card': self.drawn_card,
            'cambio_called': self.game.cambio_called,
            'cambio_caller': self.game.cambio_caller,
            'final_round': self.game.final_round_active,
            'valid_actions': self.get_valid_actions(),
        }

    def get_valid_actions(self) -> list:
        """Return list of valid action IDs for current phase."""
        if self.phase == GamePhase.GAME_OVER:
            return []

        if self.phase == GamePhase.OPPONENT_TURN:
            return []

        if self.phase == GamePhase.DRAW:
            actions = [ACTION_DRAW_DECK]
            if self.game.discard:
                actions.append(ACTION_DRAW_DISCARD)
            return actions

        if self.phase == GamePhase.ACTION:
            agent = self.players[self.agent_index]
            actions = [ACTION_DISCARD]
            # Can swap with any position in hand
            for i in range(len(agent.hand)):
                actions.append(ACTION_SWAP_BASE + i)
            return actions

        if self.phase == GamePhase.POWER:
            return self._get_power_actions()

        if self.phase == GamePhase.STICK_WINDOW:
            return self._get_stick_actions()

        if self.phase == GamePhase.CAMBIO_DECISION:
            actions = [ACTION_PASS_CAMBIO]
            if not self.game.cambio_called:
                actions.append(ACTION_CAMBIO)
            return actions

        return []

    def _get_power_actions(self) -> list:
        """Get valid actions for power card phase."""
        if not self.discarded_card or not self.discarded_card.has_power():
            return [ACTION_SKIP_POWER]

        card = self.discarded_card
        agent = self.players[self.agent_index]
        opponent = self.players[1 - self.agent_index]

        actions = [ACTION_SKIP_POWER]  # Can always skip

        if card.rank in ['7', '8']:
            # Peek own card
            for i in range(len(agent.hand)):
                actions.append(ACTION_PEEK_OWN_BASE + i)

        elif card.rank in ['9', '10']:
            # Peek opponent card
            for i in range(len(opponent.hand)):
                actions.append(ACTION_PEEK_OPP_BASE + i)

        elif card.rank in ['J', 'Q']:
            # Blind swap: my_pos x opp_pos
            for my_pos in range(len(agent.hand)):
                for opp_pos in range(len(opponent.hand)):
                    action_id = ACTION_SWAP_CARDS_BASE + my_pos * 4 + opp_pos
                    actions.append(action_id)

        elif card.rank == 'K' and card.suit in ['Spades', 'Clubs']:
            # Black King: see opponent card then swap
            # Same as J/Q for action purposes
            for my_pos in range(len(agent.hand)):
                for opp_pos in range(len(opponent.hand)):
                    action_id = ACTION_SWAP_CARDS_BASE + my_pos * 4 + opp_pos
                    actions.append(action_id)

        return actions

    def _get_stick_actions(self) -> list:
        """Get valid actions for stick window."""
        actions = [ACTION_STICK_PASS]

        if not self.game.discard:
            return actions

        agent = self.players[self.agent_index]

        # Can attempt to stick any position (game will penalize wrong attempts)
        for i in range(len(agent.hand)):
            actions.append(ACTION_STICK_BASE + i)

        return actions

    def step(self, action: int) -> tuple:
        """Execute action and return (state, result_info)."""
        valid = self.get_valid_actions()
        if action not in valid:
            raise ValueError(f"Invalid action {action}. Valid: {valid}")

        result = {'action': action, 'success': True}

        if self.phase == GamePhase.DRAW:
            result.update(self._handle_draw(action))
        elif self.phase == GamePhase.ACTION:
            result.update(self._handle_action(action))
        elif self.phase == GamePhase.POWER:
            result.update(self._handle_power(action))
        elif self.phase == GamePhase.STICK_WINDOW:
            result.update(self._handle_stick(action))
        elif self.phase == GamePhase.CAMBIO_DECISION:
            result.update(self._handle_cambio(action))

        return self.get_state(), result

    def _handle_draw(self, action: int) -> dict:
        """Process draw choice."""
        result = {}

        if action == ACTION_DRAW_DECK:
            self.drawn_card = self.game.deck.draw()
            result['source'] = 'deck'
        elif action == ACTION_DRAW_DISCARD:
            self.drawn_card = self.game.discard.pop()
            result['source'] = 'discard'

        result['drawn_card'] = self.drawn_card
        self.phase = GamePhase.ACTION
        return result

    def _handle_action(self, action: int) -> dict:
        """Process swap or discard."""
        agent = self.players[self.agent_index]
        result = {}

        if action == ACTION_DISCARD:
            # Discard the drawn card
            self.game.discard.append(self.drawn_card)
            self.discarded_card = self.drawn_card
            result['type'] = 'discard'
            result['discarded'] = self.drawn_card

        elif ACTION_SWAP_BASE <= action <= ACTION_SWAP_BASE + 3:
            # Swap with position
            pos = action - ACTION_SWAP_BASE
            if pos < len(agent.hand):
                old_card = agent.hand[pos]
                agent.hand[pos] = self.drawn_card
                self.game.discard.append(old_card)
                agent.known[pos] = self.drawn_card
                self.discarded_card = old_card
                result['type'] = 'swap'
                result['position'] = pos
                result['old_card'] = old_card
                result['new_card'] = self.drawn_card
            else:
                # Invalid position, just discard
                self.game.discard.append(self.drawn_card)
                self.discarded_card = self.drawn_card
                result['type'] = 'discard'
                result['discarded'] = self.drawn_card

        self.drawn_card = None

        # Check if discarded card has power
        if self.discarded_card and self.discarded_card.has_power():
            self.phase = GamePhase.POWER
        else:
            self.phase = GamePhase.STICK_WINDOW

        return result

    def _handle_power(self, action: int) -> dict:
        """Process power card usage."""
        result = {'used_power': False}
        agent = self.players[self.agent_index]
        opponent = self.players[1 - self.agent_index]
        card = self.discarded_card

        if action == ACTION_SKIP_POWER:
            result['skipped'] = True
            self.phase = GamePhase.STICK_WINDOW
            return result

        if card.rank in ['7', '8']:
            # Peek own card
            if ACTION_PEEK_OWN_BASE <= action <= ACTION_PEEK_OWN_BASE + 3:
                pos = action - ACTION_PEEK_OWN_BASE
                if pos < len(agent.hand):
                    self.game.peek(agent, pos)
                    result['used_power'] = True
                    result['power_type'] = 'peek_own'
                    result['position'] = pos
                    result['peeked_card'] = agent.hand[pos]

        elif card.rank in ['9', '10']:
            # Peek opponent card
            if ACTION_PEEK_OPP_BASE <= action <= ACTION_PEEK_OPP_BASE + 3:
                pos = action - ACTION_PEEK_OPP_BASE
                if pos < len(opponent.hand):
                    result['used_power'] = True
                    result['power_type'] = 'peek_opponent'
                    result['position'] = pos
                    result['peeked_card'] = opponent.hand[pos]

        elif card.rank in ['J', 'Q']:
            # Blind swap
            if ACTION_SWAP_CARDS_BASE <= action <= ACTION_SWAP_CARDS_BASE + 15:
                idx = action - ACTION_SWAP_CARDS_BASE
                my_pos = idx // 4
                opp_pos = idx % 4
                if my_pos < len(agent.hand) and opp_pos < len(opponent.hand):
                    self.game.swap(agent, opponent, my_pos, opp_pos)
                    # Invalidate knowledge of swapped position
                    if my_pos in agent.known:
                        del agent.known[my_pos]
                    result['used_power'] = True
                    result['power_type'] = 'blind_swap'
                    result['my_position'] = my_pos
                    result['opp_position'] = opp_pos

        elif card.rank == 'K' and card.suit in ['Spades', 'Clubs']:
            # Black King: see then swap
            if ACTION_SWAP_CARDS_BASE <= action <= ACTION_SWAP_CARDS_BASE + 15:
                idx = action - ACTION_SWAP_CARDS_BASE
                my_pos = idx // 4
                opp_pos = idx % 4
                if my_pos < len(agent.hand) and opp_pos < len(opponent.hand):
                    # Agent sees opponent's card before swap
                    result['peeked_card'] = opponent.hand[opp_pos]
                    self.game.swap(agent, opponent, my_pos, opp_pos)
                    # Agent now knows their position (was opponent's card)
                    agent.known[my_pos] = agent.hand[my_pos]
                    result['used_power'] = True
                    result['power_type'] = 'king_swap'
                    result['my_position'] = my_pos
                    result['opp_position'] = opp_pos

        self.phase = GamePhase.STICK_WINDOW
        return result

    def _handle_stick(self, action: int) -> dict:
        """Process stick attempt."""
        result = {}
        agent = self.players[self.agent_index]

        if action == ACTION_STICK_PASS:
            result['attempted'] = False
            self.phase = GamePhase.CAMBIO_DECISION
            return result

        if ACTION_STICK_BASE <= action <= ACTION_STICK_BASE + 3:
            pos = action - ACTION_STICK_BASE
            if pos < len(agent.hand):
                success = self.game.attempt_stick(agent, pos)
                result['attempted'] = True
                result['position'] = pos
                result['success'] = success
                if success:
                    result['stuck_card'] = self.game.discard[-1]
            else:
                result['attempted'] = False

        self.phase = GamePhase.CAMBIO_DECISION
        return result

    def _handle_cambio(self, action: int) -> dict:
        """Process CAMBIO decision."""
        result = {}

        if action == ACTION_CAMBIO and not self.game.cambio_called:
            self.game.cambio_called = True
            self.game.cambio_caller = self.game.current_player
            self.game.final_round_active = True
            result['called_cambio'] = True
        else:
            result['called_cambio'] = False

        # Advance turn
        self._advance_turn()

        return result

    def _advance_turn(self):
        """Advance to next turn and set appropriate phase."""
        self.game.advance_turn()
        self.discarded_card = None

        # Check game over
        if self.game.game_over():
            self.phase = GamePhase.GAME_OVER
            return

        # Check if it's agent's turn
        if self.game.current_player == self.agent_index:
            self.phase = GamePhase.DRAW
        else:
            self.phase = GamePhase.OPPONENT_TURN
            # Simulate opponent's turn (simple AI)
            self._play_opponent_turn()

    def _play_opponent_turn(self):
        """Simulate opponent's turn with simple AI."""
        while self.game.current_player != self.agent_index and not self.game.game_over():
            opponent = self.players[self.game.current_player]

            # Simple AI: draw from deck, discard
            drawn = self.game.deck.draw()
            if drawn:
                self.game.discard.append(drawn)

            # Maybe call cambio randomly
            if not self.game.cambio_called and len(self.game.deck.cards) < 20:
                # Simple heuristic: call cambio when deck is low
                import random
                if random.random() < 0.1:
                    self.game.cambio_called = True
                    self.game.cambio_caller = self.game.current_player
                    self.game.final_round_active = True

            self.game.advance_turn()

        # Set phase after opponent's turn
        if self.game.game_over():
            self.phase = GamePhase.GAME_OVER
        else:
            self.phase = GamePhase.DRAW

    def is_game_over(self) -> bool:
        """Check if game has ended."""
        return self.phase == GamePhase.GAME_OVER or self.game.game_over()

    def get_scores(self) -> dict:
        """Get final scores for all players."""
        return {
            p.name: self.game.calculate_score(p)
            for p in self.players
        }

    def get_winner(self) -> tuple:
        """Get winner name and score."""
        scores = self.get_scores()
        winner = min(scores, key=scores.get)
        return winner, scores[winner]
