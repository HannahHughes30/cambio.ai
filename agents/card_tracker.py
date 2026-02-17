"""Tracks all 54 cards in a Cambio game across known locations."""

from game import Card


# Full deck: 4 suits x 13 ranks + 2 jokers = 54 cards
SUITS = ['Hearts', 'Diamonds', 'Clubs', 'Spades']
RANKS = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
TOTAL_JOKERS = 2


def card_value(rank):
    """Get numeric value for a rank string."""
    if rank == 'A':
        return 1
    elif rank in ['2', '3', '4', '5', '6', '7', '8', '9', '10']:
        return int(rank)
    elif rank in ['J', 'Q']:
        return 10
    elif rank == 'K':
        return 10  # Conservative: don't know suit, assume worst case
    elif rank == 'Joker':
        return 0
    return 0


def full_deck_tuples():
    """Return the full 54-card deck as (rank, suit) tuples."""
    cards = []
    for suit in SUITS:
        for rank in RANKS:
            cards.append((rank, suit))
    cards.append(('Joker', 'None'))
    cards.append(('Joker', 'None'))
    return cards


def card_to_tuple(card):
    """Convert a Card object to a (rank, suit) tuple."""
    return (card.rank, card.suit)


def tuple_value(rank, suit):
    """Get numeric value for a (rank, suit) tuple."""
    if rank == 'K':
        if suit in ['Hearts', 'Diamonds']:
            return -1
        else:
            return 10
    return card_value(rank)


class CardTracker:
    """Tracks all 54 cards across locations: discard pile, own hand, opponent hands."""

    def __init__(self):
        self.discard_pile = []  # list of (rank, suit) in order
        self.own_hand = {}  # {pos: (rank, suit) or None} — None means unknown
        self.opponent_hands = {}  # {name: {pos: (rank, suit) or None}}
        self.opponent_hand_sizes = {}  # {name: int}
        self.opponent_self_knowledge = {}  # {name: set of positions they likely know}
        self._full_deck = full_deck_tuples()

    def initialize(self, own_known, hand_size, opponent_names, opponent_hand_size=4):
        """Set up tracking after deal.

        own_known: dict {pos: Card} of initially known own cards
        hand_size: number of cards in own hand
        opponent_names: list of opponent name strings
        """
        self.own_hand = {}
        for pos in range(hand_size):
            if pos in own_known:
                self.own_hand[pos] = card_to_tuple(own_known[pos])
            else:
                self.own_hand[pos] = None

        for name in opponent_names:
            self.opponent_hands[name] = {pos: None for pos in range(opponent_hand_size)}
            self.opponent_hand_sizes[name] = opponent_hand_size

    def card_to_discard(self, card_tuple):
        """Record a card entering the discard pile."""
        self.discard_pile.append(card_tuple)

    def sync_discard(self, game_discard):
        """Sync tracker discard pile with the game's discard pile.

        Always replaces the tracker's list with the game state so that
        reshuffles (which shrink the discard pile) are handled correctly.
        """
        self.discard_pile = [card_to_tuple(c) for c in game_discard]

    def set_own_card(self, pos, card_tuple):
        """Record a known card at own position (from peek or swap)."""
        self.own_hand[pos] = card_tuple

    def set_opponent_card(self, name, pos, card_tuple):
        """Record a known card at opponent position."""
        if name not in self.opponent_hands:
            self.opponent_hands[name] = {}
        self.opponent_hands[name][pos] = card_tuple

    def own_card_swapped_out(self, pos):
        """Mark own position as unknown (opponent blind-swapped us)."""
        if pos in self.own_hand:
            self.own_hand[pos] = None

    def clear_opponent_position(self, name, pos):
        """Mark an opponent position as unknown."""
        if name in self.opponent_hands and pos in self.opponent_hands[name]:
            self.opponent_hands[name][pos] = None

    def opponent_remove_position(self, name, pos):
        """Remove a position from an opponent's hand and shift higher positions down."""
        if name not in self.opponent_hands:
            return
        hand = self.opponent_hands[name]
        if pos in hand:
            del hand[pos]
        new_hand = {}
        for p, card in sorted(hand.items()):
            if p > pos:
                new_hand[p - 1] = card
            else:
                new_hand[p] = card
        self.opponent_hands[name] = new_hand

    def update_own_hand_size(self, new_size):
        """Update own hand tracking when hand size changes (e.g., stick or penalty)."""
        current_size = len(self.own_hand)
        if new_size > current_size:
            # Added cards (penalty) — new positions are unknown
            for pos in range(current_size, new_size):
                self.own_hand[pos] = None
        elif new_size < current_size:
            # Removed cards (stick) — handled by caller who knows which pos was removed
            pass

    def remove_own_position(self, pos):
        """Remove a position from own hand and shift higher positions down."""
        if pos in self.own_hand:
            del self.own_hand[pos]
        new_hand = {}
        for p, card in sorted(self.own_hand.items()):
            if p > pos:
                new_hand[p - 1] = card
            else:
                new_hand[p] = card
        self.own_hand = new_hand

    def update_opponent_hand_size(self, name, new_size):
        """Update opponent hand size tracking."""
        self.opponent_hand_sizes[name] = new_size
        if name not in self.opponent_hands:
            self.opponent_hands[name] = {}
        # Add unknown positions if hand grew
        current_known = self.opponent_hands[name]
        for pos in range(new_size):
            if pos not in current_known:
                current_known[pos] = None
        # Remove positions if hand shrank
        to_remove = [p for p in current_known if p >= new_size]
        for p in to_remove:
            del current_known[p]

    def unaccounted_cards(self):
        """Cards not in discard and not in any known position.

        Returns a list of (rank, suit) tuples (may contain duplicates for jokers).
        """
        accounted = list(self.discard_pile)

        for pos, card in self.own_hand.items():
            if card is not None:
                accounted.append(card)

        for name, positions in self.opponent_hands.items():
            for pos, card in positions.items():
                if card is not None:
                    accounted.append(card)

        # Remove accounted cards from full deck
        remaining = list(self._full_deck)
        for card in accounted:
            if card in remaining:
                remaining.remove(card)

        return remaining

    def expected_value_of_unknown(self):
        """Mean value of unaccounted cards."""
        remaining = self.unaccounted_cards()
        if not remaining:
            return 5.0  # Fallback
        return sum(tuple_value(r, s) for r, s in remaining) / len(remaining)

    def expected_value_at_position(self, pos):
        """Exact value if known, E[unknown] otherwise."""
        card = self.own_hand.get(pos)
        if card is not None:
            return tuple_value(card[0], card[1])
        return self.expected_value_of_unknown()

    def expected_own_score(self):
        """Sum of expected values across all own hand positions."""
        return sum(self.expected_value_at_position(pos) for pos in self.own_hand)

    def expected_opponent_score(self, name):
        """Sum of expected values across all opponent hand positions."""
        if name not in self.opponent_hands:
            hand_size = self.opponent_hand_sizes.get(name, 4)
            return hand_size * self.expected_value_of_unknown()

        e_unknown = self.expected_value_of_unknown()
        total = 0.0
        hand_size = self.opponent_hand_sizes.get(name, 4)
        positions = self.opponent_hands[name]
        for pos in range(hand_size):
            card = positions.get(pos)
            if card is not None:
                total += tuple_value(card[0], card[1])
            else:
                total += e_unknown
        return total

    def own_unknown_positions(self):
        """Return list of own positions that are unknown."""
        return [pos for pos, card in self.own_hand.items() if card is None]

    def own_known_count(self):
        """Number of own positions that are known."""
        return sum(1 for card in self.own_hand.values() if card is not None)

    def opponent_unknown_positions(self, name):
        """Return list of unknown positions for a given opponent."""
        if name not in self.opponent_hands:
            hand_size = self.opponent_hand_sizes.get(name, 4)
            return list(range(hand_size))
        return [pos for pos, card in self.opponent_hands[name].items() if card is None]

    def worst_own_position(self):
        """Return (pos, value) of the highest-value known own card, or None."""
        worst_pos = None
        worst_val = -2
        for pos, card in self.own_hand.items():
            if card is not None:
                val = tuple_value(card[0], card[1])
                if val > worst_val:
                    worst_val = val
                    worst_pos = pos
        if worst_pos is None:
            return None
        return worst_pos, worst_val

    # ------------------------------------------------------------------
    # Opponent self-knowledge tracking
    # ------------------------------------------------------------------

    def init_opponent_self_knowledge(self, name):
        """Initialize: every player knows positions 0 and 1 after deal."""
        self.opponent_self_knowledge[name] = {0, 1}

    def opponent_gains_knowledge(self, name, pos):
        """Record that an opponent now knows a position in their own hand."""
        if name not in self.opponent_self_knowledge:
            self.opponent_self_knowledge[name] = set()
        self.opponent_self_knowledge[name].add(pos)

    def opponent_loses_knowledge(self, name, pos):
        """Record that an opponent no longer knows a position in their own hand."""
        if name in self.opponent_self_knowledge:
            self.opponent_self_knowledge[name].discard(pos)

    def get_opponent_self_knowledge(self, name):
        """Return the set of positions an opponent likely knows."""
        return self.opponent_self_knowledge.get(name, set())
