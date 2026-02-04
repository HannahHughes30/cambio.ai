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

class Player:
    def __init__(self, name):
        self.name = name
        self.hand = []
        self.known = {}
    
    def set_hand(self, cards):
        self.hand = cards
    
    def choose_draw(self):
        return 'deck'
    
    def choose_action(self, drawn_card):
        return {'type': 'discard'}
    
    def call_cambio(self):
        return False
    
    def use_card_power(self, card, game, opponent=None, my_pos=None, opp_pos=None):
        """Use special card powers"""
        
        if card.rank in ['7', '8']:
            if my_pos is not None and 0 <= my_pos < len(self.hand):
                game.peek(self, my_pos)
                print(f"  💡 {self.name} used {card} to peek at own position {my_pos}: {self.hand[my_pos]}")
                return True
        
        elif card.rank in ['9', '10']:
            if opponent and opp_pos is not None and 0 <= opp_pos < len(opponent.hand):
                peeked = opponent.hand[opp_pos]
                print(f"  👀 {self.name} used {card} to peek at {opponent.name}'s position {opp_pos}: {peeked}")
                return True
        
        elif card.rank in ['J', 'Q']:
            if opponent and my_pos is not None and opp_pos is not None:
                game.swap(self, opponent, my_pos, opp_pos)
                print(f"  🔄 {self.name} used {card} to blind swap position {my_pos} with {opponent.name}'s position {opp_pos}")
                return True
        
        elif card.rank == 'K' and card.suit in ['Spades', 'Clubs']:
            if opponent and my_pos is not None and opp_pos is not None:
                peeked = opponent.hand[opp_pos]
                print(f"  👑 {self.name} used Black {card} to see {opponent.name}'s position {opp_pos}: {peeked}")
                game.swap(self, opponent, my_pos, opp_pos)
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
    
    def swap(self, p1, p2, i1, i2):
        tmp = p1.hand[i1]
        p1.hand[i1] = p2.hand[i2]
        p2.hand[i2] = tmp
    
    def peek(self, player, index):
        if index < 0 or index >= len(player.hand):
            raise ValueError("Invalid peek index")
        player.known[index] = player.hand[index]
    
    def attempt_stick(self, player, position):
        """Try to stick a matching card"""
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
            
            print(f"  ✅ {player.name} successfully stuck {stuck_card}!")
            return True
        else:
            penalty = self.deck.draw()
            if penalty:
                player.hand.append(penalty)
                print(f"  ❌ {player.name} failed stick! Got penalty card")
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
    
    def play_turn(self):
        player = self.players[self.current_player]
        print(f"\n--- {player.name}'s turn ---")
        
        draw_choice = player.choose_draw()
        
        if draw_choice == 'discard' and len(self.discard) > 0:
            drawn_card = self.discard.pop()
            print(f"{player.name} drew from discard: {drawn_card}")
        else:
            drawn_card = self.deck.draw()
            print(f"{player.name} drew from deck: {drawn_card}")
        
        if not drawn_card:
            print("No cards left!")
            return
        
        action = player.choose_action(drawn_card)
        
        if action['type'] == 'swap':
            pos = action.get('position', 0)
            if 0 <= pos < len(player.hand):
                old_card = player.hand[pos]
                player.hand[pos] = drawn_card
                self.discard.append(old_card)
                player.known[pos] = drawn_card
                print(f"{player.name} swapped position {pos}: {old_card} -> {drawn_card}")
            else:
                self.discard.append(drawn_card)
                print(f"{player.name} discarded (invalid position)")
        
        elif action['type'] == 'discard':
            self.discard.append(drawn_card)
            print(f"{player.name} discarded {drawn_card}")
        
        if player.call_cambio() and not self.cambio_called:
            self.cambio_called = True
            self.cambio_caller = self.current_player
            self.final_round_active = True
            print(f"\n🎯 {player.name} called CAMBIO!")
        
        self.advance_turn()
    
    def advance_turn(self):
        self.current_player = (self.current_player + 1) % len(self.players)
        
        if self.final_round_active and self.current_player == self.cambio_caller:
            self.final_round_active = False
    
    def game_over(self):
        return self.cambio_called and not self.final_round_active
    
    def play(self):
        turn = 0
        max_turns = 50
        
        while not self.game_over() and turn < max_turns:
            self.play_turn()
            turn += 1
        
        print("\n" + "="*50)
        print("GAME OVER!")
        print("="*50)
        
        for p in self.players:
            score = self.calculate_score(p)
            print(f"{p.name}: {p.hand} = {score} points")
        
        print("\n" + self.score_game())
        return self.score_game()

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
    print("\n✅ Test successful!")

if __name__ == "__main__":
    test()
    
    print("\n\n=== PLAYING FULL GAME ===\n")
    p1 = Player("Alice")
    p2 = Player("Bob")
    game = CambioGame([p1, p2])
    game.deal()
    game.play()
