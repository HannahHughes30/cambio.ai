"""Flask app and SocketIO events for the Cambio web GUI."""

import uuid
from flask import Flask, render_template, redirect, url_for
from flask_socketio import SocketIO, emit, join_room

from web.game_manager import GameManager

app = Flask(__name__)
app.config['SECRET_KEY'] = 'cambio-secret'
socketio = SocketIO(app, async_mode='threading', cors_allowed_origins='*')

manager = GameManager(socketio)


# ---- Routes ----

@app.route('/')
def lobby():
    return render_template('lobby.html')


@app.route('/game/<player_id>')
def game(player_id):
    if not manager.game_active:
        return redirect(url_for('lobby'))
    if player_id not in manager.human_players:
        return redirect(url_for('lobby'))
    return render_template('game.html', player_id=player_id)


# ---- SocketIO: Lobby Events ----

@socketio.on('get_lobby_state')
def handle_get_lobby_state():
    emit('lobby_state', manager.get_lobby_state())


@socketio.on('add_player')
def handle_add_player(data):
    name = data.get('name', '').strip()
    ptype = data.get('type', 'human')
    if not name:
        emit('error', {'message': 'Name is required'})
        return
    if len(manager.lobby_players) >= 6:
        emit('error', {'message': 'Maximum 6 players'})
        return
    player_id = str(uuid.uuid4())[:8]
    manager.add_lobby_player(player_id, name, ptype)
    socketio.emit('lobby_state', manager.get_lobby_state())


@socketio.on('remove_player')
def handle_remove_player(data):
    player_id = data.get('player_id')
    manager.remove_lobby_player(player_id)
    socketio.emit('lobby_state', manager.get_lobby_state())


@socketio.on('start_game')
def handle_start_game():
    total = len(manager.lobby_players)
    if total < 2:
        emit('error', {'message': 'Need at least 2 players'})
        return
    human_urls = manager.start_game()
    socketio.emit('game_started', {'human_urls': human_urls})


# ---- SocketIO: Game Events ----

@socketio.on('join_game')
def handle_join_game(data):
    player_id = data.get('player_id')
    if player_id in manager.human_players:
        join_room(player_id)
        manager.on_human_joined(player_id)


@socketio.on('decision')
def handle_decision(data):
    player_id = data.get('player_id')
    decision = data.get('decision')
    if player_id and decision is not None:
        manager.submit_decision(player_id, decision)


@socketio.on('play_again')
def handle_play_again():
    manager.reset()
    socketio.emit('return_to_lobby', {})


@socketio.on('play_again_same')
def handle_play_again_same():
    human_urls = manager.restart_same_players()
    socketio.emit('game_restarted', {'human_urls': human_urls})
