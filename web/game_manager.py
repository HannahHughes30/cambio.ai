"""Orchestrates lobby, game lifecycle, and broadcasting."""

import time
import threading
from collections import OrderedDict

from game import CambioGame
from agents import BaseAgent, SmartAgent, BayesianAgent, BayesianV2Agent
from web.human_agent import HumanAgent
from web.state_serializer import build_player_view, build_game_over_view

AGENT_REGISTRY = {
    'base': BaseAgent,
    'smart': SmartAgent,
    'bayesian': BayesianAgent,
    'bayesian_v2': BayesianV2Agent,
}

BOT_TURN_DELAY = 0.8  # seconds between bot turns for readability


class GameManager:
    def __init__(self, socketio):
        self.socketio = socketio
        self.lobby_players = OrderedDict()  # player_id -> {name, type}
        self.human_players = {}  # player_id -> HumanAgent instance
        self.game = None
        self.game_active = False
        self.game_thread = None
        self._game_log = []
        self._connected_humans = set()

    def add_lobby_player(self, player_id, name, ptype):
        self.lobby_players[player_id] = {'name': name, 'type': ptype, 'id': player_id}

    def remove_lobby_player(self, player_id):
        self.lobby_players.pop(player_id, None)

    def get_lobby_state(self):
        return {
            'players': list(self.lobby_players.values()),
            'can_start': len(self.lobby_players) >= 2,
        }

    def start_game(self):
        """Create agents and prepare the game. Thread starts when all humans connect."""
        players = []
        human_urls = {}
        self.human_players = {}
        self._game_log = []
        self._connected_humans = set()
        self.game_thread = None

        for pid, info in self.lobby_players.items():
            if info['type'] == 'human':
                agent = HumanAgent(info['name'], pid, self._notify_player)
                self.human_players[pid] = agent
                players.append(agent)
                human_urls[pid] = f'/game/{pid}'
            else:
                cls = AGENT_REGISTRY[info['type']]
                agent = cls(name=info['name'])
                players.append(agent)

        self.game = CambioGame(players)
        self.game.deal()
        self.game_active = True

        # If no humans, start the game immediately
        if not self.human_players:
            self._start_game_thread()

        return human_urls

    def on_human_joined(self, player_id):
        """Called when a human player's browser connects to the game room."""
        self._connected_humans.add(player_id)
        self.send_state_to_player(player_id)

        # Start game once all humans are connected
        if (self.game_thread is None
                and self._connected_humans >= set(self.human_players.keys())):
            self._start_game_thread()

    def _start_game_thread(self):
        self.game_thread = threading.Thread(target=self._run_game, daemon=True)
        self.game_thread.start()

    def _run_game(self):
        """Game loop running on a background thread."""
        turn = 0
        max_turns = 100

        while not self.game.game_over() and turn < max_turns:
            self._broadcast_state()

            current = self.game.players[self.game.current_player]
            is_bot = not isinstance(current, HumanAgent)

            turn_data = self.game.play_turn(turn_number=turn, verbose=True)
            self._game_log.append(self._format_log_entry(turn_data))
            turn += 1

            # Broadcast updated state after turn completes
            self._broadcast_state()

            # Delay after bot turns so humans can follow the action
            if is_bot:
                time.sleep(BOT_TURN_DELAY)

        # Game over
        results = self.game.compute_results(turn)

        game_over_view = build_game_over_view(self.game, results)
        game_over_view['log'] = self._game_log

        for pid in self.human_players:
            self.socketio.emit('game_over', game_over_view, room=pid)

        self.game_active = False

    def _broadcast_state(self):
        """Send filtered game state to each human player."""
        if not self.game:
            return
        for pid, agent in self.human_players.items():
            state = build_player_view(self.game, agent)
            state['log'] = self._game_log
            self.socketio.emit('game_state', state, room=pid)

    def send_state_to_player(self, player_id):
        """Send current state to a single player. Re-send pending prompt if any."""
        if not self.game or player_id not in self.human_players:
            return
        agent = self.human_players[player_id]
        state = build_player_view(self.game, agent)
        state['log'] = self._game_log
        self.socketio.emit('game_state', state, room=player_id)

        # Re-send pending prompt (handles reconnect / page refresh)
        prompt = agent.get_pending_prompt()
        if prompt:
            self.socketio.emit('prompt', prompt, room=player_id)

    def submit_decision(self, player_id, decision):
        """Route a decision from the browser to the correct HumanAgent."""
        agent = self.human_players.get(player_id)
        if agent:
            agent.submit_decision(decision)

    def _notify_player(self, player_id, event, data):
        """Callback used by HumanAgent to push prompts/observations to the browser."""
        if event == 'prompt' and self.game:
            agent = self.human_players.get(player_id)
            if agent:
                state = build_player_view(self.game, agent)
                state['log'] = self._game_log
                self.socketio.emit('game_state', state, room=player_id)
        self.socketio.emit(event, data, room=player_id)

    def _format_log_entry(self, turn_data):
        """Create a human-readable log string from turn_data."""
        player = turn_data['player']
        action = turn_data.get('action', '?')

        if action == 'cambio':
            return f"{player} CALLED CAMBIO!"
        if action == 'auto_cambio':
            entry = f"{player} has no cards — auto Cambio"
            if turn_data.get('cambio_called'):
                entry += " (CALLED CAMBIO!)"
            return entry

        source = turn_data.get('draw_source', '?')
        parts = [f"{player} drew from {source}"]

        if action == 'swap':
            pos = turn_data.get('swap_position', '?')
            discarded = turn_data.get('discarded_card', '?')
            parts.append(f"swapped position {pos} (discarded {discarded})")
        elif action == 'discard':
            discarded = turn_data.get('discarded_card', '?')
            parts.append(f"discarded {discarded}")
        elif action == 'power':
            ptype = turn_data.get('power_type', '?')
            if ptype == 'peek_own':
                parts.append(f"peeked at own card")
            elif ptype == 'peek_opponent':
                target = turn_data.get('power_target_player', '?')
                parts.append(f"peeked at {target}'s card")
            elif ptype in ('blind_swap', 'king_swap'):
                target = turn_data.get('power_target_player', '?')
                parts.append(f"swapped with {target}")
            elif ptype == 'king_peek_swap':
                target = turn_data.get('power_peek_player', '?')
                parts.append(f"used Black King on {target}")
            elif ptype == 'third_party_swap':
                t1 = turn_data.get('power_target_player', '?')
                t2 = turn_data.get('power_target_player2', '?')
                parts.append(f"swapped {t1} with {t2}")
            else:
                parts.append(f"used power ({ptype})")

        if turn_data.get('cambio_called'):
            parts.append("CALLED CAMBIO!")

        return ', '.join(parts)

    def restart_same_players(self):
        """Start a new game with the same lobby_players configuration."""
        saved_lobby = OrderedDict(self.lobby_players)
        self.game = None
        self.game_active = False
        self.human_players = {}
        self._game_log = []
        self._connected_humans = set()
        self.game_thread = None
        self.lobby_players = saved_lobby
        return self.start_game()

    def reset(self):
        """Reset for a new game."""
        self.game = None
        self.game_active = False
        self.human_players = {}
        self._game_log = []
        self._connected_humans = set()
        self.game_thread = None
        self.lobby_players = OrderedDict()
