"""HumanAgent: a Player subclass that blocks on WebSocket input for decisions."""

import threading
from game import Player


class HumanAgent(Player):
    """Player controlled by a human via the web UI.

    Each decision method pushes a prompt to the browser, then blocks on a
    threading.Event until the browser submits a response via WebSocket.
    """

    def __init__(self, name, player_id, notify_callback):
        super().__init__(name)
        self.player_id = player_id
        self._notify = notify_callback  # fn(player_id, event, data)
        self._event = threading.Event()
        self._decision = None
        self._pending_prompt = None
        self._last_draw_source = None  # set by choose_draw for use by choose_action
        self.opponent_known = {}  # {opp_player_index: {position: Card}}
        self._compromised = set()  # positions in our hand that opponents have peeked at

    def _wait_for_decision(self, prompt_type, prompt_data):
        """Push a prompt to the browser and block until a decision arrives."""
        self._event.clear()
        self._decision = None
        prompt = {'type': prompt_type, **prompt_data}
        self._pending_prompt = prompt
        self._notify(self.player_id, 'prompt', prompt)
        self._event.wait()
        self._pending_prompt = None
        return self._decision

    def submit_decision(self, decision):
        """Called by GameManager when the browser sends a decision."""
        self._decision = decision
        self._event.set()

    def get_pending_prompt(self):
        """Return the current pending prompt, if any (for re-sending on reconnect)."""
        return self._pending_prompt

    # ---- Player interface ----

    def choose_draw(self, game):
        discard_top = repr(game.discard[-1]) if game.discard else None
        decision = self._wait_for_decision('choose_draw', {
            'discard_top': discard_top,
            'deck_count': game.deck.size(),
            'can_call_cambio': not game.cambio_called,
        })
        source = decision.get('source', 'deck')
        if source == 'cambio':
            return 'cambio'
        self._last_draw_source = source
        return source

    def choose_action(self, drawn_card):
        from_discard = self._last_draw_source == 'discard'
        if from_discard:
            # Drew from discard: must swap into hand. Only ask which position.
            decision = self._wait_for_decision('choose_swap_position', {
                'drawn_card': repr(drawn_card),
                'drawn_value': drawn_card.get_value(),
                'card_rank': drawn_card.rank,
                'card_suit': drawn_card.suit,
                'hand_size': len(self.hand),
            })
            return {'type': 'swap', 'position': int(decision.get('position', 0))}
        else:
            # Drew from deck: can swap or discard
            decision = self._wait_for_decision('choose_action', {
                'drawn_card': repr(drawn_card),
                'drawn_value': drawn_card.get_value(),
                'hand_size': len(self.hand),
                'has_power': drawn_card.has_power(),
                'card_rank': drawn_card.rank,
                'card_suit': drawn_card.suit,
            })
            action_type = decision.get('action', 'discard')
            if action_type == 'swap':
                return {'type': 'swap', 'position': int(decision.get('position', 0))}
            return {'type': 'discard'}

    def choose_power_action(self, card, game, opponents):
        """Called AFTER the player discards a power card drawn from deck."""
        opponent_info = [
            {'name': opp.name, 'hand_size': len(opp.hand),
             'index': game.players.index(opp)}
            for opp in opponents
        ]
        decision = self._wait_for_decision('choose_power_action', {
            'card': repr(card),
            'card_rank': card.rank,
            'card_suit': card.suit,
            'hand_size': len(self.hand),
            'opponents': opponent_info,
        })

        action = decision.get('action')
        if action == 'skip':
            return None

        if action == 'peek_own':
            return {'type': 'peek_own', 'position': int(decision['position'])}

        if action == 'peek_opponent':
            opp_idx = int(decision['opponent_index'])
            opp = game.players[opp_idx]
            return {'type': 'peek_opponent', 'opponent': opp,
                    'position': int(decision['position'])}

        if action == 'blind_swap':
            # Two picks: each is {owner: 'self' or player_index, position: N}
            p1_owner = decision['pick1_owner']
            p1_pos = int(decision['pick1_position'])
            p2_owner = decision['pick2_owner']
            p2_pos = int(decision['pick2_position'])

            my_idx = game.players.index(self)

            # Resolve owners to player objects
            p1_is_self = (p1_owner == 'self' or int(p1_owner) == my_idx)
            p2_is_self = (p2_owner == 'self' or int(p2_owner) == my_idx)

            if p1_is_self and p2_is_self:
                # Swapping two of your own cards (rare but legal)
                # Use blind_swap with self as opponent
                return {
                    'type': 'blind_swap',
                    'my_position': p1_pos,
                    'opponent': self,
                    'opp_position': p2_pos,
                }
            elif p1_is_self and not p2_is_self:
                opp = game.players[int(p2_owner)]
                return {
                    'type': 'blind_swap',
                    'my_position': p1_pos,
                    'opponent': opp,
                    'opp_position': p2_pos,
                }
            elif p2_is_self and not p1_is_self:
                opp = game.players[int(p1_owner)]
                return {
                    'type': 'blind_swap',
                    'my_position': p2_pos,
                    'opponent': opp,
                    'opp_position': p1_pos,
                }
            else:
                # Both are opponents — third-party swap
                opp1 = game.players[int(p1_owner)]
                opp2 = game.players[int(p2_owner)]
                return {
                    'type': 'third_party_swap',
                    'opponent': opp1,
                    'opp_position': p1_pos,
                    'player2': opp2,
                    'position2': p2_pos,
                }

        if action == 'king_peek':
            opp_idx = int(decision['opponent_index'])
            opp = game.players[opp_idx]
            return {
                'type': 'king_swap',
                'my_position': int(decision['my_position']),
                'opponent': opp,
                'opp_position': int(decision['opp_position']),
            }

        return None

    def use_card_power(self, card, game, opponent=None, my_pos=None, opp_pos=None,
                       player2=None, pos2=None, peek_player=None, peek_pos=None,
                       verbose=True):
        """Override for Black King: peek, show to human, ask swap/skip."""
        if card.rank == 'K' and card.suit in ['Spades', 'Clubs']:
            if opponent and my_pos is not None and opp_pos is not None:
                peeked = opponent.hand[opp_pos]
                if verbose:
                    print(f"  {self.name} used Black {card} to see {opponent.name}'s position {opp_pos}: {peeked}")

                decision = self._wait_for_decision('king_swap_confirm', {
                    'peeked_card': repr(peeked),
                    'peeked_value': peeked.get_value(),
                    'peeked_rank': peeked.rank,
                    'peeked_suit': peeked.suit,
                    'opponent_name': opponent.name,
                    'opp_position': opp_pos,
                    'my_position': my_pos,
                })

                if decision.get('swap', False):
                    game.swap(self, opponent, my_pos, opp_pos)
                    # Player peeked at the card before swapping it in — they know it
                    self.known[my_pos] = self.hand[my_pos]
                    if verbose:
                        print(f"     Then swapped with own position {my_pos}")
                else:
                    if verbose:
                        print(f"     Chose NOT to swap")
                return True

        return super().use_card_power(card, game, opponent=opponent, my_pos=my_pos,
                                      opp_pos=opp_pos, player2=player2, pos2=pos2,
                                      peek_player=peek_player, peek_pos=peek_pos,
                                      verbose=verbose)

    def call_cambio(self):
        # Humans call cambio via the draw prompt, not a separate prompt
        return False

    def choose_stick(self, game):
        if not game.discard:
            return []
        top_card = game.discard[-1]
        matching = []
        for pos, card in self.known.items():
            if pos < len(self.hand) and card.rank == top_card.rank:
                matching.append(pos)
        if not matching:
            return []

        acting_player = game.players[game.current_player]
        is_your_turn = acting_player is self
        decision = self._wait_for_decision('choose_stick', {
            'discard_top': repr(top_card),
            'discard_rank': top_card.rank,
            'matching_positions': matching,
            'acting_player': acting_player.name,
            'is_your_turn': is_your_turn,
        })
        positions = decision.get('positions', [])
        return [int(p) for p in positions]

    def observe_turn(self, turn_data, game):
        my_name = self.name
        acting = turn_data.get('player')
        power = turn_data.get('power_type')
        target = turn_data.get('power_target_player')
        target_pos = turn_data.get('power_target_position')
        target2 = turn_data.get('power_target_player2')
        target2_pos = turn_data.get('power_target_position2')
        peek_player = turn_data.get('power_peek_player')
        peek_pos = turn_data.get('power_peek_position')

        # Mark compromised: another player peeked at one of our cards
        if acting != my_name:
            if power in ('peek_opponent',) and target == my_name and target_pos is not None:
                self._compromised.add(target_pos)
            if power == 'king_peek_swap' and peek_player == my_name and peek_pos is not None:
                self._compromised.add(peek_pos)
            if power == 'king_swap' and target == my_name and target_pos is not None:
                self._compromised.add(target_pos)

        # Clear compromised: card at position changed due to swap
        # Our own swap during draw
        if acting == my_name and turn_data.get('action') == 'swap':
            pos = turn_data.get('swap_position')
            if pos is not None:
                self._compromised.discard(pos)

        # Blind swap / king swap targeting our position
        if power in ('blind_swap', 'king_swap') and target == my_name and target_pos is not None:
            self._compromised.discard(target_pos)
        if power in ('blind_swap', 'king_swap') and acting == my_name:
            pos = turn_data.get('swap_position')
            if pos is not None:
                self._compromised.discard(pos)

        # Third-party swap involving us
        if power == 'third_party_swap':
            if target == my_name and target_pos is not None:
                self._compromised.discard(target_pos)
            if target2 == my_name and target2_pos is not None:
                self._compromised.discard(target2_pos)

        self._notify(self.player_id, 'observe_turn', turn_data)

    def observe_stick(self, stick_data, game):
        # If one of our cards was stuck, update compromised positions
        if stick_data['player'] == self.name and stick_data['success']:
            pos = stick_data['position']
            self._compromised.discard(pos)
            # Shift positions above the stuck card down by 1
            self._compromised = {(p - 1 if p > pos else p) for p in self._compromised}
        self._notify(self.player_id, 'observe_stick', stick_data)
