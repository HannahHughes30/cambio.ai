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
        return self.rank in ['7','8','9','10','J','Q','K']
    
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
    
    def use_card_power(self, card, game, opponent=None, my_pos=None, opp_pos=None, verbose=True):
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
            if opponent and my_pos is not None and opp_pos is not None:
                game.swap(self, opponent, my_pos, opp_pos)
                if verbose:
                    print(f"  {self.name} used {card} to blind swap position {my_pos} with {opponent.name}'s position {opp_pos}")
                return True

        elif card.rank == 'K' and card.suit in ['Spades', 'Clubs']:
            if opponent and my_pos is not None and opp_pos is not None:
                peeked = opponent.hand[opp_pos]
                if verbose:
                    print(f"  {self.name} used Black {card} to see {opponent.name}'s position {opp_pos}: {peeked}")
                game.swap(self, opponent, my_pos, opp_pos)
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

        if self.deck.is_empty():
            self.reshuffle_deck()

        draw_choice = player.choose_draw(self)

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
        }

        if draw_choice == 'discard' and len(self.discard) > 0:
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

        # Check if card has power and agent wants to use it
        if drawn_card.has_power() and hasattr(player, 'choose_power_action'):
            opponents = [p for i, p in enumerate(self.players) if i != self.current_player]
            power_action = player.choose_power_action(drawn_card, self, opponents)

            if power_action:
                turn_data['action'] = 'power'
                turn_data['power_type'] = power_action['type']

                if power_action['type'] == 'peek_own':
                    pos = power_action['position']
                    player.use_card_power(drawn_card, self, my_pos=pos, verbose=verbose)

                elif power_action['type'] == 'peek_opponent':
                    opp = power_action['opponent']
                    pos = power_action['position']
                    player.use_card_power(drawn_card, self, opponent=opp, opp_pos=pos, verbose=verbose)
                    if hasattr(player, 'opponent_known'):
                        opp_id = self.players.index(opp)
                        if opp_id not in player.opponent_known:
                            player.opponent_known[opp_id] = {}
                        player.opponent_known[opp_id][pos] = opp.hand[pos]

                elif power_action['type'] in ['blind_swap', 'king_swap']:
                    opp = power_action['opponent']
                    my_pos = power_action['my_position']
                    opp_pos = power_action['opp_position']
                    turn_data['swap_position'] = my_pos
                    player.use_card_power(drawn_card, self, opponent=opp, my_pos=my_pos, opp_pos=opp_pos, verbose=verbose)

                self.discard.append(drawn_card)

                if player.call_cambio() and not self.cambio_called:
                    self.cambio_called = True
                    self.cambio_caller = self.current_player
                    self.final_round_active = True
                    turn_data['cambio_called'] = True
                    if verbose:
                        print(f"\n {player.name} called CAMBIO!")

                turn_data['hand_size'] = len(player.hand)
                self.advance_turn()
                return turn_data

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
                if verbose:
                    print(f"{player.name} swapped position {pos}: {old_card} -> {drawn_card}")
            else:
                self.discard.append(drawn_card)
                if verbose:
                    print(f"{player.name} discarded (invalid position)")

        elif action['type'] == 'discard':
            turn_data['action'] = 'discard'
            self.discard.append(drawn_card)
            if verbose:
                print(f"{player.name} discarded {drawn_card}")

        if player.call_cambio() and not self.cambio_called:
            self.cambio_called = True
            self.cambio_caller = self.current_player
            self.final_round_active = True
            turn_data['cambio_called'] = True
            if verbose:
                print(f"\n {player.name} called CAMBIO!")

        turn_data['hand_size'] = len(player.hand)
        self.advance_turn()
        return turn_data
    
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

        scores = {p.name: self.calculate_score(p) for p in self.players}
        hands = {p.name: [repr(c) for c in p.hand] for p in self.players}
        winner = min(scores, key=scores.get)
        cambio_caller = self.players[self.cambio_caller].name if self.cambio_caller is not None else None

        if verbose:
            print("\n" + "=" * 50)
            print("GAME OVER!")
            print("=" * 50)
            for p in self.players:
                print(f"{p.name}: {p.hand} = {scores[p.name]} points")
            print(f"\n{winner} wins!")

        return {
            'winner': winner,
            'scores': scores,
            'hands': hands,
            'total_turns': turn,
            'turns': turns,
            'cambio_caller': cambio_caller,
            'deck_exhausted': self.deck.is_empty(),
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
