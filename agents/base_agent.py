"""Base agent that plays Cambio with simple heuristics but never calls Cambio."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from game import Player


class BaseAgent(Player):
    """A simple agent that makes reasonable decisions but never calls Cambio.

    Strategy:
    - Draw from discard if card value < discard_threshold, otherwise draw from deck
    - If drawn_card < max(known hand), swap with that max card
    - Result: hand keeps min(max(known hand), drawn_card)
    - Never call Cambio
    """

    def __init__(self, name="BaseAgent", discard_threshold=4):
        super().__init__(name)
        self.discard_threshold = discard_threshold

    def choose_draw(self, game):
        """Draw from discard if top card value < discard_threshold, otherwise draw from deck."""
        if game.discard and game.discard[-1].get_value() < self.discard_threshold:
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
        """Never call Cambio."""
        return False

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
