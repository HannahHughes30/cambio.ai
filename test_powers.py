from game import Card, CambioGame, Player

def test_card_powers():
    print("=== TESTING CARD POWERS ===\n")
    
    p1 = Player("Alice")
    p2 = Player("Bob")
    game = CambioGame([p1, p2])
    
    p1.hand = [Card('7', 'Hearts'), Card('9', 'Clubs'), Card('J', 'Spades'), Card('K', 'Spades')]
    p2.hand = [Card('2', 'Hearts'), Card('5', 'Diamonds'), Card('8', 'Clubs'), Card('Q', 'Hearts')]
    
    p1.known = {0: p1.hand[0], 1: p1.hand[1]}
    p2.known = {0: p2.hand[0], 1: p2.hand[1]}
    
    print("Initial hands:")
    print(f"Alice: {p1.hand}")
    print(f"Bob: {p2.hand}\n")
    
    print("TEST 1: Alice uses 7 to peek at own card (position 2)")
    card_7 = Card('7', 'Hearts')
    success = p1.use_card_power(card_7, game, my_pos=2)
    print(f"Success: {success}")
    print(f"Alice now knows: {p1.known}\n")
    
    print("TEST 2: Alice uses 9 to peek at Bob's card (position 3)")
    card_9 = Card('9', 'Clubs')
    success = p1.use_card_power(card_9, game, opponent=p2, opp_pos=3)
    print(f"Success: {success}\n")
    
    print("TEST 3: Alice uses Jack to blind swap with Bob")
    print(f"Before swap - Alice pos 0: {p1.hand[0]}, Bob pos 1: {p2.hand[1]}")
    card_j = Card('J', 'Spades')
    success = p1.use_card_power(card_j, game, opponent=p2, my_pos=0, opp_pos=1)
    print(f"After swap - Alice pos 0: {p1.hand[0]}, Bob pos 1: {p2.hand[1]}")
    print(f"Success: {success}\n")
    
    print("TEST 4: Alice uses Black King to see and swap with Bob")
    print(f"Before - Alice pos 2: {p1.hand[2]}, Bob pos 2: {p2.hand[2]}")
    card_k = Card('K', 'Spades')
    success = p1.use_card_power(card_k, game, opponent=p2, my_pos=2, opp_pos=2)
    print(f"After - Alice pos 2: {p1.hand[2]}, Bob pos 2: {p2.hand[2]}")
    print(f"Success: {success}\n")
    
    print("✅ All power tests completed!")

def test_sticking():
    print("\n\n=== TESTING STICKING MECHANIC ===\n")
    
    p1 = Player("Alice")
    p2 = Player("Bob")
    game = CambioGame([p1, p2])
    
    p1.hand = [Card('7', 'Hearts'), Card('9', 'Clubs'), Card('J', 'Spades'), Card('2', 'Diamonds')]
    p2.hand = [Card('2', 'Hearts'), Card('5', 'Diamonds'), Card('7', 'Clubs'), Card('Q', 'Hearts')]
    
    game.discard = [Card('A', 'Spades'), Card('7', 'Diamonds')]
    
    print(f"Alice hand: {p1.hand}")
    print(f"Bob hand: {p2.hand}")
    print(f"Top of discard: {game.discard[-1]}\n")
    
    print("TEST 1: Alice tries to stick a 7 (should succeed)")
    success = game.attempt_stick(p1, 0)
    print(f"Success: {success}")
    print(f"Alice hand now: {p1.hand}")
    print(f"Discard pile: {game.discard[-3:]}\n")
    
    print("TEST 2: Bob tries to stick wrong card (should fail)")
    print(f"Top of discard: {game.discard[-1]}")
    success = game.attempt_stick(p2, 0)
    print(f"Success: {success}")
    print(f"Bob hand now: {p2.hand}\n")
    
    print("TEST 3: Bob tries to stick a 7 (should succeed)")
    game.discard.append(Card('7', 'Spades'))
    print(f"Top of discard: {game.discard[-1]}")
    success = game.attempt_stick(p2, 2)
    print(f"Success: {success}")
    print(f"Bob hand now: {p2.hand}\n")
    
    print("✅ All sticking tests completed!")

if __name__ == "__main__":
    test_card_powers()
    test_sticking()
