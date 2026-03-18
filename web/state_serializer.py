"""Build per-player JSON views of game state (no information leaking)."""


def build_player_view(game, viewing_player):
    """Return a dict representing what `viewing_player` is allowed to see."""
    player_idx = game.players.index(viewing_player)

    # Own hand: show known cards face-up, unknown face-down
    compromised = getattr(viewing_player, '_compromised', set())
    own_hand = []
    for i, card in enumerate(viewing_player.hand):
        entry = {
            'position': i,
            'compromised': i in compromised,
        }
        if i in viewing_player.known:
            entry.update({
                'known': True,
                'card': repr(card),
                'rank': card.rank,
                'suit': card.suit,
                'value': card.get_value(),
            })
        else:
            entry.update({
                'known': False,
                'card': None,
                'rank': None,
                'suit': None,
                'value': None,
            })
        own_hand.append(entry)

    # Opponents: show peeked cards face-up, others face-down
    opp_known = getattr(viewing_player, 'opponent_known', {})
    opponents = []
    for i, p in enumerate(game.players):
        if i == player_idx:
            continue
        cards = []
        known_for_opp = opp_known.get(i, {})
        for j in range(len(p.hand)):
            known_card = known_for_opp.get(j)
            if known_card:
                cards.append({
                    'position': j,
                    'known': True,
                    'rank': known_card.rank,
                    'suit': known_card.suit,
                    'value': known_card.get_value(),
                })
            else:
                cards.append({'position': j, 'known': False})
        opponents.append({
            'name': p.name,
            'index': i,
            'hand_size': len(p.hand),
            'cards': cards,
        })

    discard_top = None
    if game.discard:
        top = game.discard[-1]
        discard_top = {
            'card': repr(top),
            'rank': top.rank,
            'suit': top.suit,
            'value': top.get_value(),
        }

    current = game.players[game.current_player]

    return {
        'your_name': viewing_player.name,
        'your_index': player_idx,
        'own_hand': own_hand,
        'opponents': opponents,
        'discard_top': discard_top,
        'discard_count': len(game.discard),
        'deck_count': game.deck.size(),
        'current_player': current.name,
        'current_player_index': game.current_player,
        'is_your_turn': game.current_player == player_idx,
        'cambio_called': game.cambio_called,
        'cambio_caller': game.players[game.cambio_caller].name if game.cambio_caller is not None else None,
    }


def build_game_over_view(game, results):
    """Return full reveal for game over screen."""
    caller_name = results['cambio_caller']
    players = []
    for p in game.players:
        hand = []
        for i, card in enumerate(p.hand):
            hand.append({
                'position': i,
                'card': repr(card),
                'rank': card.rank,
                'suit': card.suit,
                'value': card.get_value(),
            })
        raw_score = game.calculate_score(p)
        final_score = results['scores'][p.name]
        penalty = final_score - raw_score  # +10, -10, or 0
        players.append({
            'name': p.name,
            'hand': hand,
            'score': final_score,
            'raw_score': raw_score,
            'penalty': penalty,
            'is_caller': p.name == caller_name,
        })

    return {
        'players': players,
        'winner': results['winner'],
        'scores': results['scores'],
        'total_turns': results['total_turns'],
        'cambio_caller': results['cambio_caller'],
    }
