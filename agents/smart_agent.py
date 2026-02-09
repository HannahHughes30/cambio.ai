"""Smart agent that plays Cambio that uses card powers intelligently, 
makes probabilistic decisions, and calls Cambio when expected hand value 
is below a threshold."""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from game import Player

class SmartAgent(Player):



    def __init__(self, name="SmartAgent", discard_threshold=4):
        super().__init__(name)
        self.discard_threshold = discard_threshold
        self._last_discard_top = None

    def set_discard_top(self, card):
        """Called by game to inform agent of discard pile top."""
        self._last_discard_top = card

    def choose_draw(self):
        """Draw from discard if value < discard_threshold, otherwise draw from deck."""
        if self._last_discard_top and self._last_discard_top.get_value() < self.discard_threshold:
            return 'discard'
        return 'deck'

    def choose_action(self, drawn_card):
        """Swap if drawn_card < max(known hand), else discard.

        This ensures we keep min(max(known hand), drawn_card).
        """
        drawn_value = drawn_card.get_value()

        # Find max value card among known positions
        max_pos = None
        max_value = -2  # Start below red King (-1)

        for pos, card in self.known.items():
            if pos < len(self.hand):
                card_value = card.get_value()
                if card_value > max_value:
                    max_value = card_value
                    max_pos = pos

        # Swap if drawn card is lower than our max known card
        if max_pos is not None and drawn_value < max_value:
            return {'type': 'swap', 'position': max_pos}

        return {'type': 'discard'}

    def call_cambio(self):
        """
        Will call Cambio if expected hand value is at or below threshold, 
        assuming unknown cards are between -1 and 10.
        """
        total = 0
        for card in range(len(self.hand)):
            # assume unknown cards have value is -1 to 10 with equal probability
            expected_unknown = random.randint(-1, 10)

            if self.hand[card] != self.known.get(card):
                total += expected_unknown
            else:
                total += self.known[card].get_value()

        # Call Cambio if expected total is 10 or less
        return total <= 10

    def choose_power_action(self, card, game, opponents):
        """Choose how to use a power card.

        Returns dict with action details or None to skip.
        """
        if card.rank in ['7', '8']:
            # Peek at own unknown card
            unknown_pos = self._find_unknown_position()
            if unknown_pos is not None:
                return {'type': 'peek_own', 'position': unknown_pos}

        elif card.rank in ['9', '10']:
            # Peek at random opponent's card
            if opponents:
                opp = opponents[0]
                if opp.hand:
                    return {'type': 'peek_opponent', 'opponent': opp, 'position': 0}

        elif card.rank in ['J', 'Q']:
            # Blind swap: trade our worst known card for opponent's random card
            worst_pos = self._find_worst_known_position()
            if worst_pos is not None and opponents and opponents[0].hand:
                return {
                    'type': 'blind_swap',
                    'my_position': worst_pos,
                    'opponent': opponents[0],
                    'opp_position': 0
                }

        elif card.rank == 'K' and card.suit in ['Spades', 'Clubs']:
            # Black King: see then swap
            worst_pos = self._find_worst_known_position()
            if worst_pos is not None and opponents and opponents[0].hand:
                return {
                    'type': 'king_swap',
                    'my_position': worst_pos,
                    'opponent': opponents[0],
                    'opp_position': 0
                }

        return None  # Skip power

    def _find_unknown_position(self):
        """Find a hand position we don't know."""
        for i in range(len(self.hand)):
            if i not in self.known:
                return i
        return None

    def _find_worst_known_position(self):
        """Find position of highest value known card."""
        worst_pos = None
        worst_value = -2  # Lower than red King (-1)

        for pos, card in self.known.items():
            if pos < len(self.hand):
                val = card.get_value()
                if val > worst_value:
                    worst_value = val
                    worst_pos = pos

        return worst_pos
