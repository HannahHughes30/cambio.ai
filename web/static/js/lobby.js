const socket = io();

socket.on('connect', () => {
    socket.emit('get_lobby_state');
});

socket.on('lobby_state', (data) => {
    renderPlayerList(data.players);
    const startBtn = document.getElementById('start-btn');
    startBtn.disabled = !data.can_start;
    const msg = document.getElementById('lobby-msg');
    if (data.players.length < 2) {
        msg.textContent = 'Add at least 2 players to start';
    } else {
        msg.textContent = `${data.players.length} players ready`;
    }
});

socket.on('error', (data) => {
    const el = document.getElementById('error-msg');
    el.textContent = data.message;
    setTimeout(() => { el.textContent = ''; }, 3000);
});

socket.on('game_started', (data) => {
    const urls = data.human_urls;
    const ids = Object.keys(urls);
    if (ids.length > 0) {
        // Open first human in this tab, rest in new tabs
        window.location.href = urls[ids[0]];
        for (let i = 1; i < ids.length; i++) {
            window.open(urls[ids[i]], '_blank');
        }
    } else {
        // All bots - just show a message
        document.getElementById('lobby-msg').textContent = 'Game started (all bots)';
    }
});

function renderPlayerList(players) {
    const list = document.getElementById('player-list');
    list.innerHTML = '';
    players.forEach(p => {
        const div = document.createElement('div');
        div.className = 'player-item';
        const typeLabel = p.type === 'human' ? 'Human' : `Bot: ${p.type}`;
        div.innerHTML = `
            <span class="player-name">${p.name}</span>
            <span class="player-type ${p.type === 'human' ? 'type-human' : 'type-bot'}">${typeLabel}</span>
            <button class="remove-btn" onclick="removePlayer('${p.id}')">x</button>
        `;
        list.appendChild(div);
    });
}

function addPlayer() {
    const nameInput = document.getElementById('player-name');
    const typeSelect = document.getElementById('player-type');
    const name = nameInput.value.trim();
    if (!name) return;
    socket.emit('add_player', { name: name, type: typeSelect.value });
    nameInput.value = '';
    nameInput.focus();
}

function removePlayer(playerId) {
    socket.emit('remove_player', { player_id: playerId });
}

function startGame() {
    socket.emit('start_game');
}

// Allow Enter key to add player
document.getElementById('player-name').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') addPlayer();
});
