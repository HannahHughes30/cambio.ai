const socket = io();
let currentState = null;
let pendingPrompt = null;

// ---- Connection ----
socket.on('connect', () => {
    socket.emit('join_game', { player_id: PLAYER_ID });
});

socket.on('return_to_lobby', () => {
    window.location.href = '/';
});

socket.on('game_restarted', (data) => {
    // If our player_id has a new URL, redirect; otherwise rejoin in place
    if (data.human_urls && data.human_urls[PLAYER_ID]) {
        document.getElementById('game-over').classList.add('hidden');
        pendingPrompt = null;
        currentState = null;
        document.getElementById('game-log').innerHTML = '';
        socket.emit('join_game', { player_id: PLAYER_ID });
    } else {
        window.location.href = '/';
    }
});

// ---- State Updates ----
socket.on('game_state', (state) => {
    currentState = state;
    renderState(state);
});

socket.on('prompt', (prompt) => {
    pendingPrompt = prompt;
    renderPrompt(prompt);
});

socket.on('observe_turn', (data) => {});
socket.on('observe_stick', (data) => {});

socket.on('game_over', (data) => {
    renderGameOver(data);
});

// ---- Rendering ----

function renderState(state) {
    // Turn indicator
    const turnEl = document.getElementById('turn-indicator');
    if (state.is_your_turn) {
        turnEl.textContent = 'Your Turn';
        turnEl.className = 'turn-indicator your-turn';
    } else {
        turnEl.textContent = `Waiting for ${state.current_player}...`;
        turnEl.className = 'turn-indicator waiting';
    }

    const cambioEl = document.getElementById('cambio-banner');
    if (state.cambio_called) {
        cambioEl.textContent = `CAMBIO called by ${state.cambio_caller}! Final round.`;
        cambioEl.classList.remove('hidden');
    } else {
        cambioEl.classList.add('hidden');
    }

    // Deck
    document.getElementById('deck-count').textContent = state.deck_count;

    // Discard
    const discardEl = document.getElementById('discard-pile');
    if (state.discard_top) {
        discardEl.innerHTML = buildCardInner(state.discard_top.rank, state.discard_top.suit);
        discardEl.className = 'card card-face discard-card ' + getSuitClass(state.discard_top.suit);
    } else {
        discardEl.innerHTML = '<span class="empty-label">Empty</span>';
        discardEl.className = 'card discard-card empty';
    }

    // Opponents
    renderOpponents(state.opponents);

    // Your hand (2x2 grid: positions 2,3 on top, 0,1 on bottom)
    renderHand(state.own_hand);

    // Log
    renderLog(state.log || []);
}

function renderOpponents(opponents) {
    const area = document.getElementById('opponents-area');
    area.innerHTML = '';
    opponents.forEach(opp => {
        const div = document.createElement('div');
        div.className = 'opponent';
        div.innerHTML = `<div class="opponent-name">${opp.name} <span class="opp-card-count">(${opp.hand_size} cards)</span></div>`;
        const hand = document.createElement('div');
        hand.className = 'opp-hand-grid';

        // 2x2 grid for opponents too: positions 2,3 on top row, 0,1 on bottom
        const topRow = [];
        const bottomRow = [];
        for (let i = 0; i < opp.hand_size; i++) {
            if (i < 2) bottomRow.push(i);
            else topRow.push(i);
        }
        const ordered = [...topRow, ...bottomRow];

        ordered.forEach(i => {
            const cardData = opp.cards && opp.cards[i];
            const card = document.createElement('div');
            card.dataset.oppIndex = opp.index;
            card.dataset.position = i;
            if (cardData && cardData.known) {
                card.className = 'card card-face card-sm ' + getSuitClass(cardData.suit);
                card.innerHTML = buildCardInner(cardData.rank, cardData.suit) +
                    `<span class="card-pos-label">${i}</span>`;
            } else {
                card.className = 'card card-back card-sm';
                card.innerHTML = `<span class="card-pos-label">${i}</span>`;
            }
            hand.appendChild(card);
        });
        div.appendChild(hand);
        area.appendChild(div);
    });
}

function renderHand(hand) {
    const container = document.getElementById('your-hand');
    container.innerHTML = '';

    // Reorder: positions 2+ (top/far), then 0,1 (bottom/close to player)
    const bottom = hand.filter(c => c.position < 2);
    const top = hand.filter(c => c.position >= 2);
    const ordered = [...top, ...bottom];

    ordered.forEach(c => {
        const card = document.createElement('div');
        card.dataset.position = c.position;
        const eyeHtml = c.compromised ? '<span class="card-eye" title="An opponent has seen this card">👁</span>' : '';
        if (c.known) {
            card.className = 'card card-face ' + getSuitClass(c.suit);
            card.innerHTML = buildCardInner(c.rank, c.suit) +
                eyeHtml +
                `<span class="card-pos-label">${c.position}</span>`;
        } else {
            card.className = 'card card-back';
            card.innerHTML = eyeHtml +
                `<span class="card-pos-label">${c.position}</span>`;
        }
        container.appendChild(card);
    });
}

function buildCardInner(rank, suit) {
    if (rank === 'Joker') {
        return `<div class="card-rank">JKR</div>`;
    }
    return `<div class="card-rank">${rank}</div><div class="card-suit-icon">${getSuitSymbol(suit)}</div>`;
}

function buildPromptCard(rank, suit) {
    const suitClass = getSuitClass(suit);
    const inner = buildCardInner(rank, suit);
    return `<div class="card card-face prompt-card ${suitClass}">${inner}</div>`;
}

function renderLog(log) {
    const logEl = document.getElementById('game-log');
    logEl.innerHTML = '';
    log.forEach((entry, i) => {
        const div = document.createElement('div');
        div.className = 'log-entry';
        div.textContent = `${i + 1}. ${entry}`;
        logEl.appendChild(div);
    });
    logEl.scrollTop = logEl.scrollHeight;
}

// ---- Prompts ----

function renderPrompt(prompt) {
    const area = document.getElementById('prompt-area');
    const text = document.getElementById('prompt-text');
    const buttons = document.getElementById('prompt-buttons');
    area.classList.remove('hidden');
    buttons.innerHTML = '';
    clearCardClickHandlers();

    switch (prompt.type) {
        case 'choose_draw':
            renderDrawPrompt(prompt, text, buttons);
            break;
        case 'choose_swap_position':
            renderSwapPositionPrompt(prompt, text, buttons);
            break;
        case 'choose_action':
            renderActionPrompt(prompt, text, buttons);
            break;
        case 'choose_power_action':
            renderPowerPrompt(prompt, text, buttons);
            break;
        case 'king_swap_confirm':
            renderKingConfirmPrompt(prompt, text, buttons);
            break;
        case 'choose_stick':
            renderStickPrompt(prompt, text, buttons);
            break;
        default:
            text.textContent = 'Waiting...';
    }
}

function hidePrompt() {
    document.getElementById('prompt-area').classList.add('hidden');
    clearCardClickHandlers();
}

function sendDecision(decision) {
    socket.emit('decision', { player_id: PLAYER_ID, decision: decision });
    hidePrompt();
}

// ---- Draw ----

function renderDrawPrompt(prompt, text, buttons) {
    if (prompt.discard_top) {
        text.innerHTML = `Your turn! Choose where to draw from:`;
    } else {
        text.innerHTML = `Your turn! Draw from the deck:`;
    }

    addButton(buttons, 'Draw from Deck', () => {
        sendDecision({ source: 'deck' });
    });

    if (prompt.discard_top) {
        addButton(buttons, `Take Discard (${prompt.discard_top})`, () => {
            sendDecision({ source: 'discard' });
        }, 'btn-secondary');
    }

    if (prompt.can_call_cambio) {
        addButton(buttons, 'Call Cambio!', () => {
            sendDecision({ source: 'cambio' });
        }, 'btn-cambio');
    }
}

// ---- Swap Position (discard draw — must swap) ----

function renderSwapPositionPrompt(prompt, text, buttons) {
    text.innerHTML = `<div class="prompt-card-area">${buildPromptCard(prompt.card_rank, prompt.card_suit)}<div class="prompt-card-desc">Taken from discard (value ${prompt.drawn_value})<br>Choose which card to replace.</div></div>`;

    const hint = document.createElement('div');
    hint.className = 'prompt-hint';
    hint.textContent = 'Click a card in your hand to swap it out. If the replaced card has a power, you can use it!';
    buttons.appendChild(hint);

    makeHandClickable((position) => {
        sendDecision({ position: position });
    });
}

// ---- Action (deck draw — swap or discard) ----

function renderActionPrompt(prompt, text, buttons) {
    text.innerHTML = `<div class="prompt-card-area">${buildPromptCard(prompt.card_rank, prompt.card_suit)}<div class="prompt-card-desc">Drawn from deck (value ${prompt.drawn_value})<br>Swap into your hand or discard it.</div></div><div class="prompt-hint" style="margin-top:0">The card that hits the discard pile activates its power (if any).</div>`;

    addButton(buttons, 'Discard', () => {
        sendDecision({ action: 'discard' });
    }, 'btn-secondary');

    const hint = document.createElement('div');
    hint.className = 'prompt-hint';
    hint.textContent = 'Click a card in your hand to swap it in.';
    buttons.appendChild(hint);

    makeHandClickable((position) => {
        sendDecision({ action: 'swap', position: position });
    });
}

// ---- Power ----

function renderPowerPrompt(prompt, text, buttons) {
    const rank = prompt.card_rank;
    const suit = prompt.card_suit;
    const cardHtml = buildPromptCard(rank, suit);

    if (rank === '7' || rank === '8') {
        text.innerHTML = `<div class="prompt-card-area">${cardHtml}<div class="prompt-card-desc"><strong>Peek</strong> &mdash; look at one of your own unknown cards.</div></div>`;
        addButton(buttons, 'Skip Power', () => sendDecision({ action: 'skip' }), 'btn-muted');
        const hint = document.createElement('div');
        hint.className = 'prompt-hint';
        hint.textContent = 'Click a face-down card in your hand to peek.';
        buttons.appendChild(hint);
        makeHandClickable((position) => {
            sendDecision({ action: 'peek_own', position: position });
        }, true);

    } else if (rank === '9' || rank === '10') {
        text.innerHTML = `<div class="prompt-card-area">${cardHtml}<div class="prompt-card-desc"><strong>Spy</strong> &mdash; peek at an opponent's card.</div></div>`;
        addButton(buttons, 'Skip Power', () => sendDecision({ action: 'skip' }), 'btn-muted');
        const hint = document.createElement('div');
        hint.className = 'prompt-hint';
        hint.textContent = "Click an opponent's card to peek at it.";
        buttons.appendChild(hint);
        makeOpponentClickable((oppIndex, position) => {
            sendDecision({ action: 'peek_opponent', opponent_index: oppIndex, position: position });
        });

    } else if (rank === 'J' || rank === 'Q') {
        renderBlindSwapPrompt(prompt, text, buttons);

    } else if (rank === 'K' && (suit === 'Spades' || suit === 'Clubs')) {
        renderBlackKingPrompt(prompt, text, buttons);

    } else {
        text.innerHTML = `<div class="prompt-card-area">${cardHtml}<div class="prompt-card-desc">No usable power.</div></div>`;
        addButton(buttons, 'OK', () => sendDecision({ action: 'skip' }));
    }
}

function renderBlindSwapPrompt(prompt, text, buttons) {
    text.innerHTML = `<div class="prompt-card-area">${buildPromptCard(prompt.card_rank, prompt.card_suit)}<div class="prompt-card-desc"><strong>Blind Swap</strong> &mdash; swap any two cards on the table.</div></div>`;
    addButton(buttons, 'Skip Power', () => sendDecision({ action: 'skip' }), 'btn-muted');
    const hint = document.createElement('div');
    hint.className = 'prompt-hint';
    hint.textContent = 'Step 1: Click the first card (yours or an opponent\'s).';
    buttons.appendChild(hint);

    let pick1 = null; // {owner: 'self' or oppIndex, position: N}

    makeAllCardsClickable((owner, position) => {
        pick1 = { owner, position };
        clearCardClickHandlers();
        const label = owner === 'self' ? `your position ${position}` : `opponent's position ${position}`;
        text.innerHTML = `Blind Swap &mdash; first card: <strong>${label}</strong>.`;
        buttons.innerHTML = '';
        addButton(buttons, 'Cancel', () => sendDecision({ action: 'skip' }), 'btn-muted');
        const hint2 = document.createElement('div');
        hint2.className = 'prompt-hint';
        hint2.textContent = 'Step 2: Click the second card to swap with.';
        buttons.appendChild(hint2);

        makeAllCardsClickable((owner2, position2) => {
            // Don't allow picking the exact same card
            if (owner2 === pick1.owner && position2 === pick1.position) return;
            sendDecision({
                action: 'blind_swap',
                pick1_owner: pick1.owner,
                pick1_position: pick1.position,
                pick2_owner: owner2,
                pick2_position: position2,
            });
        });
    });
}

function renderBlackKingPrompt(prompt, text, buttons) {
    text.innerHTML = `<div class="prompt-card-area">${buildPromptCard(prompt.card_rank, prompt.card_suit)}<div class="prompt-card-desc"><strong>Black King</strong> &mdash; peek at an opponent's card, then decide whether to swap.</div></div>`;
    addButton(buttons, 'Skip Power', () => sendDecision({ action: 'skip' }), 'btn-muted');
    const hint = document.createElement('div');
    hint.className = 'prompt-hint';
    hint.textContent = 'Step 1: Click one of YOUR cards (for potential swap).';
    buttons.appendChild(hint);

    let myPos = null;
    makeHandClickable((position) => {
        myPos = position;
        clearCardClickHandlers();
        text.innerHTML = `Black King &mdash; your position <strong>${myPos}</strong> selected.`;
        buttons.innerHTML = '';
        addButton(buttons, 'Cancel', () => sendDecision({ action: 'skip' }), 'btn-muted');
        const hint2 = document.createElement('div');
        hint2.className = 'prompt-hint';
        hint2.textContent = "Step 2: Click an opponent's card to peek at.";
        buttons.appendChild(hint2);

        makeOpponentClickable((oppIndex, oppPos) => {
            sendDecision({
                action: 'king_peek',
                my_position: myPos,
                opponent_index: oppIndex,
                opp_position: oppPos,
            });
        });
    });
}

// ---- King Swap Confirm ----

function renderKingConfirmPrompt(prompt, text, buttons) {
    const cardHtml = prompt.peeked_rank ? buildPromptCard(prompt.peeked_rank, prompt.peeked_suit) : '';
    text.innerHTML = `<div class="prompt-card-area">${cardHtml}<div class="prompt-card-desc">${prompt.opponent_name}'s position ${prompt.opp_position} (value ${prompt.peeked_value})<br>Swap with your position ${prompt.my_position}?</div></div>`;
    addButton(buttons, 'Swap!', () => sendDecision({ swap: true }));
    addButton(buttons, "Don't Swap", () => sendDecision({ swap: false }), 'btn-secondary');
}

// ---- Stick ----

function renderStickPrompt(prompt, text, buttons) {
    if (prompt.is_your_turn) {
        text.innerHTML = `<strong>Stick!</strong> Discard top is <span class="highlight">${prompt.discard_top}</span>. Click matching cards to stick them.`;
    } else {
        text.innerHTML = `<strong>Stick!</strong> ${prompt.acting_player} discarded <span class="highlight">${prompt.discard_top}</span> &mdash; you can stick a matching card!`;
    }

    const selected = new Set();
    const stickBtn = document.createElement('button');
    stickBtn.textContent = 'Stick Selected';
    stickBtn.className = 'btn btn-primary';
    stickBtn.style.display = 'none';
    stickBtn.addEventListener('click', () => {
        sendDecision({ positions: Array.from(selected) });
    });

    addButton(buttons, 'Skip', () => sendDecision({ positions: [] }), 'btn-secondary');
    buttons.appendChild(stickBtn);

    prompt.matching_positions.forEach(pos => {
        const handCards = document.querySelectorAll('#your-hand .card');
        handCards.forEach(card => {
            if (parseInt(card.dataset.position) === pos) {
                card.classList.add('card-stickable');
                const handler = () => {
                    const p = parseInt(card.dataset.position);
                    if (selected.has(p)) {
                        selected.delete(p);
                        card.classList.remove('card-selected');
                    } else {
                        selected.add(p);
                        card.classList.add('card-selected');
                    }
                    stickBtn.style.display = selected.size > 0 ? '' : 'none';
                    stickBtn.textContent = `Stick ${selected.size} card${selected.size > 1 ? 's' : ''}`;
                };
                card.addEventListener('click', handler);
                activeClickHandlers.push({ el: card, handler });
            }
        });
    });
}

// ---- Game Over ----

function renderGameOver(data) {
    hidePrompt();
    const overlay = document.getElementById('game-over');
    overlay.classList.remove('hidden');

    const results = document.getElementById('game-over-results');
    let html = `<div class="go-winner">${data.winner} wins!</div>`;
    if (data.cambio_caller) {
        html += `<div class="go-meta">Cambio called by ${data.cambio_caller} &bull; ${data.total_turns} turns</div>`;
    }

    html += '<div class="go-hands">';
    data.players.sort((a, b) => a.score - b.score);
    data.players.forEach(p => {
        const isWinner = p.name === data.winner;
        html += `<div class="go-player ${isWinner ? 'go-winner-row' : ''}">`;
        html += `<div class="go-player-header"><span class="go-pname">${p.name}</span><span class="go-pscore">${p.score} pts</span></div>`;
        html += '<div class="go-cards">';
        p.hand.forEach(c => {
            html += `<div class="card card-face card-sm ${getSuitClass(c.suit)}">${buildCardInner(c.rank, c.suit)}</div>`;
        });
        html += '</div></div>';
    });
    html += '</div>';
    results.innerHTML = html;

    if (data.log) renderLog(data.log);
}

function playAgain() {
    socket.emit('play_again');
}

function playAgainSame() {
    socket.emit('play_again_same');
}

// ---- Helpers ----

function addButton(container, label, onClick, className) {
    const btn = document.createElement('button');
    btn.textContent = label;
    btn.className = 'btn ' + (className || 'btn-primary');
    btn.addEventListener('click', onClick);
    container.appendChild(btn);
}

function getSuitClass(suit) {
    if (!suit) return '';
    return (suit === 'Hearts' || suit === 'Diamonds') ? 'suit-red' : 'suit-black';
}

function getSuitSymbol(suit) {
    switch (suit) {
        case 'Hearts': return '\u2665';
        case 'Diamonds': return '\u2666';
        case 'Clubs': return '\u2663';
        case 'Spades': return '\u2660';
        default: return '';
    }
}

let activeClickHandlers = [];

function clearCardClickHandlers() {
    activeClickHandlers.forEach(({ el, handler }) => {
        el.removeEventListener('click', handler);
        el.classList.remove('card-clickable', 'card-stickable', 'card-selected');
    });
    activeClickHandlers = [];
}

function makeHandClickable(callback, unknownOnly) {
    const handCards = document.querySelectorAll('#your-hand .card');
    handCards.forEach(card => {
        if (unknownOnly && card.classList.contains('card-face')) return;
        card.classList.add('card-clickable');
        const handler = () => callback(parseInt(card.dataset.position));
        card.addEventListener('click', handler);
        activeClickHandlers.push({ el: card, handler });
    });
}

function makeOpponentClickable(callback) {
    const oppCards = document.querySelectorAll('.opp-hand-grid .card');
    oppCards.forEach(card => {
        card.classList.add('card-clickable');
        const handler = () => callback(parseInt(card.dataset.oppIndex), parseInt(card.dataset.position));
        card.addEventListener('click', handler);
        activeClickHandlers.push({ el: card, handler });
    });
}

function makeAllCardsClickable(callback) {
    // callback(owner, position) — owner is 'self' or opponent player index
    const handCards = document.querySelectorAll('#your-hand .card');
    handCards.forEach(card => {
        card.classList.add('card-clickable');
        const handler = () => callback('self', parseInt(card.dataset.position));
        card.addEventListener('click', handler);
        activeClickHandlers.push({ el: card, handler });
    });
    const oppCards = document.querySelectorAll('.opp-hand-grid .card');
    oppCards.forEach(card => {
        card.classList.add('card-clickable');
        const handler = () => callback(parseInt(card.dataset.oppIndex), parseInt(card.dataset.position));
        card.addEventListener('click', handler);
        activeClickHandlers.push({ el: card, handler });
    });
}
