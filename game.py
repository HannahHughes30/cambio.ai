import random

class Card:
    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit
    
    def get_value(self):
        if self.rank == 'A':
            return 1
        elif self.rank in ['2','3','4','5','6','7','8','9','10']:
            return int(self.rank)
        elif self.rank in ['J', 'Q']:
            return 10
        elif self.rank == 'K':
            if self.suit in ['Hearts', 'Diamonds']:
                return -1
            else:
                return 10
        elif self.rank == 'Joker':
            return 0
        return 0
    
    def has_power(self):
        if self.rank == 'K':
            return self.suit in ['Spades', 'Clubs']
        return self.rank in ['7','8','9','10','J','Q']
    
    def __repr__(self):
        if self.rank == 'Joker':
            return "Joker"
        return f"{self.rank}{self.suit[0]}"

class Deck:
    def __init__(self):
        suits = ['Hearts', 'Diamonds', 'Clubs', 'Spades']
        ranks = ['A','2','3','4','5','6','7','8','9','10','J','Q','K']
        
        self.cards = []
        for suit in suits:
            for rank in ranks:
                self.cards.append(Card(rank, suit))
        
        self.cards.append(Card('Joker', 'None'))
        self.cards.append(Card('Joker', 'None'))
        
        random.shuffle(self.cards)
    
    def draw(self):
        if len(self.cards) > 0:
            return self.cards.pop()
        return None
    
    def size(self):
        return len(self.cards)
    
    def is_empty(self):
        return len(self.cards) == 0

class Player:
    def __init__(self, name):
        self.name = name
        self.hand = []
        self.known = {}

    def set_hand(self, cards):
        self.hand = cards

    def choose_draw(self, game):
        return 'deck'

    def choose_action(self, drawn_card):
        return {'type': 'discard'}

    def call_cambio(self):
        return False

    def observe_turn(self, turn_data, game):
        """Called on ALL players after each turn. Override in subclasses."""
        pass

    def choose_stick(self, game):
        """Return list of positions to stick (empty = no stick). Override in subclasses."""
        return []

    def observe_stick(self, stick_data, game):
        """Called on ALL players after any stick attempt. Override in subclasses."""
        pass
    
    def use_card_power(self, card, game, opponent=None, my_pos=None, opp_pos=None,
                        player2=None, pos2=None, peek_player=None, peek_pos=None,
                        verbose=True):
        if card.rank in ['7', '8']:
            if my_pos is not None and 0 <= my_pos < len(self.hand):
                game.peek(self, my_pos)
                if verbose:
                    print(f"  {self.name} used {card} to peek at own position {my_pos}: {self.hand[my_pos]}")
                return True

        elif card.rank in ['9', '10']:
            if opponent and opp_pos is not None and 0 <= opp_pos < len(opponent.hand):
                peeked = opponent.hand[opp_pos]
                if verbose:
                    print(f"  {self.name} used {card} to peek at {opponent.name}'s position {opp_pos}: {peeked}")
                return True

        elif card.rank in ['J', 'Q']:
            # Third-party swap: swap opponent[opp_pos] with player2[pos2]
            if opponent and player2 and opp_pos is not None and pos2 is not None:
                game.swap(opponent, player2, opp_pos, pos2)
                if verbose:
                    print(f"  {self.name} used {card} to swap {opponent.name}'s position {opp_pos} with {player2.name}'s position {pos2}")
                return True
            # Self-opponent swap (original path)
            if opponent and my_pos is not None and opp_pos is not None:
                game.swap(self, opponent, my_pos, opp_pos)
                if verbose:
                    print(f"  {self.name} used {card} to blind swap position {my_pos} with {opponent.name}'s position {opp_pos}")
                return True

        elif card.rank == 'K' and card.suit in ['Spades', 'Clubs']:
            # Extended Black King: peek any card, then swap any two
            if peek_player and peek_pos is not None:
                if peek_pos < 0 or peek_pos >= len(peek_player.hand):
                    return False
                peeked = peek_player.hand[peek_pos]
                if verbose:
                    print(f"  {self.name} used Black {card} to see {peek_player.name}'s position {peek_pos}: {peeked}")
                # Third-party swap path
                if opponent and player2 and opp_pos is not None and pos2 is not None:
                    if 0 <= opp_pos < len(opponent.hand) and 0 <= pos2 < len(player2.hand):
                        game.swap(opponent, player2, opp_pos, pos2)
                        if verbose:
                            print(f"     Then swapped {opponent.name}'s position {opp_pos} with {player2.name}'s position {pos2}")
                    return True
                # Self-opponent swap after peek
                if opponent and my_pos is not None and opp_pos is not None:
                    if 0 <= my_pos < len(self.hand) and 0 <= opp_pos < len(opponent.hand):
                        game.swap(self, opponent, my_pos, opp_pos)
                        # Player peeked at the card before swapping it in — they know it
                        self.known[my_pos] = self.hand[my_pos]
                        if verbose:
                            print(f"     Then swapped own position {my_pos} with {opponent.name}'s position {opp_pos}")
                    return True
                # Peek-only (no swap)
                return True
            # Original Black King path (backward compat)
            if opponent and my_pos is not None and opp_pos is not None:
                if 0 <= my_pos < len(self.hand) and 0 <= opp_pos < len(opponent.hand):
                    peeked = opponent.hand[opp_pos]
                    if verbose:
                        print(f"  {self.name} used Black {card} to see {opponent.name}'s position {opp_pos}: {peeked}")
                    game.swap(self, opponent, my_pos, opp_pos)
                    # Player peeked at the card before swapping it in — they know it
                    self.known[my_pos] = self.hand[my_pos]
                    if verbose:
                        print(f"     Then swapped with own position {my_pos}")
                    return True

        return False

class CambioGame:
    def __init__(self, players):
        self.deck = Deck()
        self.discard = []
        self.players = players
        self.current_player = 0
        self.cambio_called = False
        self.cambio_caller = None
        self.final_round_active = False
    
    def deal(self):
        for p in self.players:
            p.set_hand([self.deck.draw() for _ in range(4)])
        
        for p in self.players:
            p.known[0] = p.hand[0]
            p.known[1] = p.hand[1]
        
        first_card = self.deck.draw()
        if first_card:
            self.discard.append(first_card)
    
    def reshuffle_deck(self):
        """Shuffle all discard pile cards except the top one back into the deck."""
        if len(self.discard) <= 1:
            return
        top = self.discard[-1]
        reshuffle_cards = self.discard[:-1]
        self.discard = [top]
        self.deck.cards.extend(reshuffle_cards)
        random.shuffle(self.deck.cards)

    def swap(self, p1, p2, i1, i2):
        tmp = p1.hand[i1]
        p1.hand[i1] = p2.hand[i2]
        p2.hand[i2] = tmp

        if p1 is p2:
            # Same player: move known entries with the cards
            k1 = p1.known.pop(i1, None)
            k2 = p1.known.pop(i2, None)
            if k1 is not None:
                p1.known[i2] = k1
            if k2 is not None:
                p1.known[i1] = k2
        else:
            # Cross-player swap: neither player knows the new card
            p1.known.pop(i1, None)
            p2.known.pop(i2, None)
    
    def peek(self, player, index):
        if index < 0 or index >= len(player.hand):
            raise ValueError("Invalid peek index")
        player.known[index] = player.hand[index]
    
    def attempt_stick(self, player, position, verbose=True):
        if not self.discard or position >= len(player.hand):
            return False

        top_card = self.discard[-1]
        player_card = player.hand[position]

        if player_card.rank == top_card.rank:
            stuck_card = player.hand.pop(position)
            self.discard.append(stuck_card)
            if position in player.known:
                del player.known[position]

            new_known = {}
            for pos, card in player.known.items():
                if pos > position:
                    new_known[pos - 1] = card
                else:
                    new_known[pos] = card
            player.known = new_known

            if verbose:
                print(f"  {player.name} successfully stuck {stuck_card}!")
            return True
        else:
            penalty = self.deck.draw()
            if penalty:
                player.hand.append(penalty)
                if verbose:
                    print(f"  {player.name} failed stick! Got penalty card")
            return False
    
    def calculate_score(self, player):
        return sum(card.get_value() for card in player.hand)
    
    def score_game(self):
        w_score = 1000
        w_name = ""
        for p in self.players:
            current = self.calculate_score(p)
            if current < w_score:
                w_score = current
                w_name = p.name
        return f'"{w_name}" wins with a score of {w_score}!'
    
    def play_turn(self, turn_number=0, verbose=True):
        player = self.players[self.current_player]
        if verbose:
            print(f"\n--- {player.name}'s turn ---")

        if len(player.hand) == 0:
            turn_data = {
                'turn_number': turn_number,
                'player': player.name,
                'draw_source': None,
                'drawn_card': None,
                'drawn_value': None,
                'action': 'auto_cambio',
                'power_type': None,
                'swap_position': None,
                'cambio_called': False,
                'hand_size': 0,
                'discarded_card': None,
                'discarded_value': None,
                'power_target_player': None,
                'power_target_position': None,
                'power_target_player2': None,
                'power_target_position2': None,
                'power_peek_player': None,
                'power_peek_position': None,
            }
            if not self.cambio_called:
                self.cambio_called = True
                self.cambio_caller = self.current_player
                self.final_round_active = True
                turn_data['cambio_called'] = True
                if verbose:
                    print(f"  {player.name} has no cards! Auto-Cambio called!")
            self._broadcast_and_stick(turn_data, verbose)
            self.advance_turn()
            return turn_data

        # Start-of-turn cambio check for bots (humans use choose_draw)
        if not self.cambio_called and player.call_cambio():
            return self._handle_cambio(turn_number, verbose)

        if self.deck.is_empty():
            self.reshuffle_deck()

        draw_choice = player.choose_draw(self)

        # Humans call cambio via the draw prompt
        if draw_choice == 'cambio':
            return self._handle_cambio(turn_number, verbose)

        turn_data = {
            'turn_number': turn_number,
            'player': player.name,
            'draw_source': None,
            'drawn_card': None,
            'drawn_value': None,
            'action': None,
            'power_type': None,
            'swap_position': None,
            'cambio_called': False,
            'hand_size': len(player.hand),
            'discarded_card': None,
            'discarded_value': None,
            'power_target_player': None,
            'power_target_position': None,
            'power_target_player2': None,
            'power_target_position2': None,
            'power_peek_player': None,
            'power_peek_position': None,
        }

        from_discard = draw_choice == 'discard' and len(self.discard) > 0

        if from_discard:
            drawn_card = self.discard.pop()
            turn_data['draw_source'] = 'discard'
            if verbose:
                print(f"{player.name} drew from discard: {drawn_card}")
        else:
            drawn_card = self.deck.draw()
            turn_data['draw_source'] = 'deck'
            if verbose:
                print(f"{player.name} drew from deck: {drawn_card}")

        if not drawn_card:
            if verbose:
                print("No cards left!")
            return turn_data

        turn_data['drawn_card'] = repr(drawn_card)
        turn_data['drawn_value'] = drawn_card.get_value()

        # ---- Determine action and execute swap/discard ----
        discarded_card = None

        if from_discard:
            # Drew from discard: must swap into hand
            action = player.choose_action(drawn_card)
            pos = action.get('position', 0)
            if action['type'] != 'swap' or pos < 0 or pos >= len(player.hand):
                pos = 0
            turn_data['action'] = 'swap'
            turn_data['swap_position'] = pos
            old_card = player.hand[pos]
            player.hand[pos] = drawn_card
            self.discard.append(old_card)
            player.known[pos] = drawn_card
            discarded_card = old_card
            turn_data['discarded_card'] = repr(old_card)
            turn_data['discarded_value'] = old_card.get_value()
            if verbose:
                print(f"{player.name} swapped position {pos}: {old_card} -> {drawn_card}")
        else:
            # Drew from deck: choose swap or discard
            action = player.choose_action(drawn_card)

            if action['type'] == 'swap':
                pos = action.get('position', 0)
                turn_data['action'] = 'swap'
                turn_data['swap_position'] = pos
                if 0 <= pos < len(player.hand):
                    old_card = player.hand[pos]
                    player.hand[pos] = drawn_card
                    self.discard.append(old_card)
                    player.known[pos] = drawn_card
                    discarded_card = old_card
                    turn_data['discarded_card'] = repr(old_card)
                    turn_data['discarded_value'] = old_card.get_value()
                    if verbose:
                        print(f"{player.name} swapped position {pos}: {old_card} -> {drawn_card}")
                else:
                    self.discard.append(drawn_card)
                    discarded_card = drawn_card
                    turn_data['discarded_card'] = repr(drawn_card)
                    turn_data['discarded_value'] = drawn_card.get_value()
                    if verbose:
                        print(f"{player.name} discarded (invalid position)")

            elif action['type'] == 'discard':
                turn_data['action'] = 'discard'
                self.discard.append(drawn_card)
                discarded_card = drawn_card
                turn_data['discarded_card'] = repr(drawn_card)
                turn_data['discarded_value'] = drawn_card.get_value()
                if verbose:
                    print(f"{player.name} discarded {drawn_card}")

        # ---- POWER: triggered by whatever card just hit the discard pile ----
        if discarded_card and discarded_card.has_power():
            opponents = [p for i, p in enumerate(self.players) if i != self.current_player]
            power_action = None
            if hasattr(player, 'choose_power_action'):
                power_action = player.choose_power_action(discarded_card, self, opponents)

            if not power_action:
                power_action = self._default_power_action(player, discarded_card, opponents)

            if power_action:
                turn_data['action'] = 'power'
                turn_data['power_type'] = power_action['type']
                self._execute_power(player, discarded_card, power_action, turn_data, verbose)

        turn_data['hand_size'] = len(player.hand)
        self._broadcast_and_stick(turn_data, verbose)

        self.advance_turn()
        return turn_data

    def _default_power_action(self, player, discarded_card, opponents):
        """Return a default power action when the agent doesn't choose one (mandatory powers)."""
        if discarded_card.rank in ['7', '8']:
            # Peek own first unknown position
            for i in range(len(player.hand)):
                if i not in player.known:
                    return {'type': 'peek_own', 'position': i}
            # All known — peek position 0
            if player.hand:
                return {'type': 'peek_own', 'position': 0}

        elif discarded_card.rank in ['9', '10']:
            # Peek random opponent at random position
            valid_opps = [o for o in opponents if o.hand]
            if valid_opps:
                opp = random.choice(valid_opps)
                pos = random.randint(0, len(opp.hand) - 1)
                return {'type': 'peek_opponent', 'opponent': opp, 'position': pos}

        elif discarded_card.rank in ['J', 'Q']:
            # Random swap: self position ↔ random opponent position
            if player.hand and opponents:
                valid_opps = [o for o in opponents if o.hand]
                if valid_opps:
                    opp = random.choice(valid_opps)
                    my_pos = random.randint(0, len(player.hand) - 1)
                    opp_pos = random.randint(0, len(opp.hand) - 1)
                    return {
                        'type': 'blind_swap',
                        'my_position': my_pos,
                        'opponent': opp,
                        'opp_position': opp_pos,
                    }

        elif discarded_card.rank == 'K' and discarded_card.suit in ['Spades', 'Clubs']:
            # Black King: peek own first unknown position (no swap)
            for i in range(len(player.hand)):
                if i not in player.known:
                    return {'type': 'king_peek_swap', 'peek_player': player, 'peek_position': i}
            if player.hand:
                return {'type': 'king_peek_swap', 'peek_player': player, 'peek_position': 0}

        return None

    def _execute_power(self, player, drawn_card, power_action, turn_data, verbose):
        """Execute a power card effect. Called after the card is already on the discard pile."""
        if power_action['type'] == 'peek_own':
            pos = power_action['position']
            player.use_card_power(drawn_card, self, my_pos=pos, verbose=verbose)

        elif power_action['type'] == 'peek_opponent':
            opp = power_action['opponent']
            pos = power_action['position']
            player.use_card_power(drawn_card, self, opponent=opp, opp_pos=pos, verbose=verbose)
            turn_data['power_target_player'] = opp.name
            turn_data['power_target_position'] = pos
            if hasattr(player, 'opponent_known'):
                opp_id = self.players.index(opp)
                if opp_id not in player.opponent_known:
                    player.opponent_known[opp_id] = {}
                if 0 <= pos < len(opp.hand):
                    player.opponent_known[opp_id][pos] = opp.hand[pos]

        elif power_action['type'] == 'third_party_swap':
            opp1 = power_action['opponent']
            pos1 = power_action['opp_position']
            opp2 = power_action['player2']
            pos2 = power_action['position2']
            turn_data['power_target_player'] = opp1.name
            turn_data['power_target_position'] = pos1
            turn_data['power_target_player2'] = opp2.name
            turn_data['power_target_position2'] = pos2
            player.use_card_power(drawn_card, self, opponent=opp1, opp_pos=pos1,
                                  player2=opp2, pos2=pos2, verbose=verbose)

        elif power_action['type'] == 'king_peek_swap':
            pk_player = power_action['peek_player']
            pk_pos = power_action['peek_position']
            turn_data['power_peek_player'] = pk_player.name
            turn_data['power_peek_position'] = pk_pos
            swap_info = power_action.get('swap')
            if swap_info:
                s_p1 = swap_info['player1']
                s_pos1 = swap_info['position1']
                s_p2 = swap_info['player2']
                s_pos2 = swap_info['position2']
                turn_data['power_target_player'] = s_p1.name
                turn_data['power_target_position'] = s_pos1
                turn_data['power_target_player2'] = s_p2.name
                turn_data['power_target_position2'] = s_pos2
                if s_p1 == player:
                    turn_data['swap_position'] = s_pos1
                elif s_p2 == player:
                    turn_data['swap_position'] = s_pos2
                player.use_card_power(drawn_card, self, opponent=s_p1, opp_pos=s_pos1,
                                      player2=s_p2, pos2=s_pos2,
                                      peek_player=pk_player, peek_pos=pk_pos,
                                      verbose=verbose)
            else:
                player.use_card_power(drawn_card, self, peek_player=pk_player, peek_pos=pk_pos,
                                      verbose=verbose)

        elif power_action['type'] == 'general_swap':
            p1 = power_action['player1']
            pos1 = power_action['position1']
            p2 = power_action['player2']
            pos2 = power_action['position2']
            if 0 <= pos1 < len(p1.hand) and 0 <= pos2 < len(p2.hand):
                self.swap(p1, p2, pos1, pos2)
                turn_data['power_target_player'] = p1.name
                turn_data['power_target_position'] = pos1
                turn_data['power_target_player2'] = p2.name
                turn_data['power_target_position2'] = pos2
                if verbose:
                    print(f"  {player.name} used {drawn_card} to swap {p1.name}'s position {pos1} with {p2.name}'s position {pos2}")

        elif power_action['type'] in ['blind_swap', 'king_swap']:
            opp = power_action['opponent']
            my_pos = power_action['my_position']
            opp_pos = power_action['opp_position']
            turn_data['swap_position'] = my_pos
            turn_data['power_target_player'] = opp.name
            turn_data['power_target_position'] = opp_pos
            player.use_card_power(drawn_card, self, opponent=opp, my_pos=my_pos, opp_pos=opp_pos, verbose=verbose)
    
    def _handle_cambio(self, turn_number, verbose):
        """Handle a player calling cambio (their entire turn). Returns turn_data."""
        player = self.players[self.current_player]
        self.cambio_called = True
        self.cambio_caller = self.current_player
        self.final_round_active = True
        if verbose:
            print(f"\n {player.name} called CAMBIO!")
        turn_data = {
            'turn_number': turn_number,
            'player': player.name,
            'draw_source': None,
            'drawn_card': None,
            'drawn_value': None,
            'action': 'cambio',
            'power_type': None,
            'swap_position': None,
            'cambio_called': True,
            'hand_size': len(player.hand),
            'discarded_card': None,
            'discarded_value': None,
            'power_target_player': None,
            'power_target_position': None,
            'power_target_player2': None,
            'power_target_position2': None,
            'power_peek_player': None,
            'power_peek_position': None,
        }
        self._broadcast_and_stick(turn_data, verbose)
        self.advance_turn()
        return turn_data

    def _broadcast_and_stick(self, turn_data, verbose):
        """Broadcast turn observation to all players, then offer stick opportunities."""
        for p in self.players:
            p.observe_turn(turn_data, self)
        self._offer_stick_opportunities(verbose)

    def _offer_stick_opportunities(self, verbose):
        """Let ALL players attempt to stick cards matching the discard top."""
        # Iterate starting from the current player, wrapping around
        n = len(self.players)
        for offset in range(n):
            idx = (self.current_player + offset) % n
            player = self.players[idx]
            positions = player.choose_stick(self)
            # Process in descending order so position shifts don't affect earlier indices
            for pos in sorted(positions, reverse=True):
                if pos < len(player.hand):
                    success = self.attempt_stick(player, pos, verbose=verbose)
                    stick_data = {
                        'player': player.name,
                        'position': pos,
                        'success': success,
                    }
                    for obs in self.players:
                        obs.observe_stick(stick_data, self)

    def advance_turn(self):
        self.current_player = (self.current_player + 1) % len(self.players)
        
        if self.final_round_active and self.current_player == self.cambio_caller:
            self.final_round_active = False
    
    def game_over(self):
        return self.cambio_called and not self.final_round_active
    
    def play(self, verbose=True, max_turns=50):
        turn = 0
        turns = []

        while not self.game_over() and turn < max_turns:
            turn_data = self.play_turn(turn_number=turn, verbose=verbose)
            turns.append(turn_data)
            turn += 1

        results = self.compute_results(turn)
        results['turns'] = turns
        results['deck_exhausted'] = self.deck.is_empty()

        if verbose:
            print("\n" + "=" * 50)
            print("GAME OVER!")
            print("=" * 50)
            for p in self.players:
                print(f"{p.name}: {p.hand} = {results['scores'][p.name]} points")
            print(f"\n{results['winner']} wins!")

        return results

    def compute_results(self, total_turns):
        """Compute final scores, apply cambio bonus/penalty, and determine winner."""
        scores = {p.name: self.calculate_score(p) for p in self.players}

        # Apply Cambio caller bonus/penalty
        if self.cambio_caller is not None:
            caller_name = self.players[self.cambio_caller].name
            caller_score = scores[caller_name]
            other_scores = {n: s for n, s in scores.items() if n != caller_name}
            min_other = min(other_scores.values())

            if caller_score < min_other:
                # Caller wins (strictly lowest) — bonus
                scores[caller_name] -= 10
            else:
                # Caller loses or ties — penalty
                scores[caller_name] += 10

        hands = {p.name: [repr(c) for c in p.hand] for p in self.players}
        cambio_caller_name = self.players[self.cambio_caller].name if self.cambio_caller is not None else None
        winner = min(scores, key=lambda n: (scores[n], 1 if n == cambio_caller_name else 0))

        return {
            'winner': winner,
            'scores': scores,
            'hands': hands,
            'total_turns': total_turns,
            'cambio_caller': cambio_caller_name,
        }

def test():
    print("=== TESTING BASIC FUNCTIONS ===\n")
    
    p1, p2 = Player("JIM"), Player("BOB")
    game = CambioGame([p1, p2])
    game.deal()
    
    print(f"P1 hand: {p1.hand}")
    print(f"P2 hand: {p2.hand}")
    print(f"P1 knows: {p1.known}")
    print(f"P2 knows: {p2.known}")
    
    print("\nSwapping P1[0] with P2[2]...")
    game.swap(p1, p2, 0, 2)
    print(f"P1 hand: {p1.hand}")
    print(f"P2 hand: {p2.hand}")
    
    print("\nP1 peeking at position 2...")
    game.peek(p1, 2)
    print(f"P1 knows: {p1.known}")
    
    print(f"\nScores: P1={game.calculate_score(p1)}, P2={game.calculate_score(p2)}")
    print("\nTest successful!")

if __name__ == "__main__":
    test()
    
    print("\n\n=== PLAYING FULL GAME ===\n")
    p1 = Player("Alice")
    p2 = Player("Bob")
    game = CambioGame([p1, p2])
    game.deal()
    game.play()
