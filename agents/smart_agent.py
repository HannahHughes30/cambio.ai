"""Smart agent that plays Cambio with card powers, opponent modeling, and strategic Cambio calls."""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from game import Player

class SmartAgent(Player):
    """A smarter agent that uses card powers, tracks opponents, and calls Cambio strategically."""

    def __init__(self, name="SmartAgent", discard_threshold=4):
        super().__init__(name)
        self.discard_threshold = discard_threshold
        self.opponent_known = {}
        self.opponent_hand_size = 4

    def choose_draw(self, game):
        if game.discard and game.discard[-1].get_value() < self.discard_threshold:
            return 'discard'
        return 'deck'

    def choose_action(self, drawn_card):
        drawn_value = drawn_card.get_value()
        max_pos = None
        max_value = -2

        for pos, card in self.known.items():
            if pos < len(self.hand):
                card_value = card.get_value()
                if card_value > max_value:
                    max_value = card_value
                    max_pos = pos

        if max_pos is not None and drawn_value < max_value:
            return {'type': 'swap', 'position': max_pos}

        return {'type': 'discard'}

    def call_cambio(self):
        """Call Cambio only when confident and have enough information."""
        # Need to know at least 3 of 4 cards to be confident
        if len(self.known) < 3:
            return False
        
        my_known_score = sum(card.get_value() for card in self.known.values())
        my_unknown_count = len(self.hand) - len(self.known)
        my_estimated_score = my_known_score + (my_unknown_count * 5)
        
        opp_known_total = 0
        opp_cards_known = 0
        for opp_id, opp_cards in self.opponent_known.items():
            for card in opp_cards.values():
                opp_known_total += card.get_value()
                opp_cards_known += 1
        
        opp_unknown_count = self.opponent_hand_size - opp_cards_known
        opp_estimated_score = opp_known_total + (opp_unknown_count * 6)
        # Only call if estimated score is low AND we're beating opponent by good margin
        if my_estimated_score < 10 and my_estimated_score < (opp_estimated_score - 4):
            return True
        
        # If we know ALL cards and score is excellent, definitely call
        if len(self.known) == len(self.hand) and my_known_score < 8:
            return True
            
        return False

    def choose_power_action(self, card, game, opponents):
        if card.rank in ['7', '8']:
            unknown_pos = self._find_unknown_position()
            if unknown_pos is not None:
                return {'type': 'peek_own', 'position': unknown_pos}

        elif card.rank in ['9', '10']:
            if opponents:
                opp = opponents[0]
                if opp.hand:
                    pos = random.randint(0, len(opp.hand) - 1)
                    return {'type': 'peek_opponent', 'opponent': opp, 'position': pos}

        elif card.rank in ['J', 'Q']:
            worst_pos = self._find_worst_known_position()
            if worst_pos is not None and opponents and opponents[0].hand:
                return {
                    'type': 'blind_swap',
                    'my_position': worst_pos,
                    'opponent': opponents[0],
                    'opp_position': random.randint(0, len(opponents[0].hand) - 1)
                }

        # King Swap: Swap your worst known card with opponent's best known card
        elif card.rank == 'K' and card.suit in ['Spades', 'Clubs']:
            worst_pos = self._find_worst_known_position()
            best_opp_card_pos, target_opp = self._find_best_opp_card_pos(opponents)
            if worst_pos is not None and opponents and opponents[0].hand and best_opp_card_pos is not None:
                return {
                    'type': 'king_swap',
                    'my_position': worst_pos,
                    'opponent': target_opp,
                    'opp_position': best_opp_card_pos
                }

        return None

    def _find_unknown_position(self):
        for i in range(len(self.hand)):
            if i not in self.known:
                return i
        return None

    def _find_worst_known_position(self):
        worst_pos = None
        worst_value = -2

        for pos, card in self.known.items():
            if pos < len(self.hand):
                val = card.get_value()
                if val > worst_value:
                    worst_value = val
                    worst_pos = pos

        return worst_pos
    
    def _find_best_opp_card_pos(self, opponents):
        best_pos = None
        best_value = 1000
        target_opp = None
        for opp in opponents:
            for pos, card in opp.known.items():
                val = card.get_value()
                if val < best_value:
                    best_value = val
                    best_pos = pos
                    target_opp = opp
        return best_pos, target_opp
