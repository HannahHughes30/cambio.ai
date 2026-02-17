"""Tests for CardTracker."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from game import Card
from agents.card_tracker import CardTracker, card_to_tuple, tuple_value, full_deck_tuples


class TestFullDeck:
    def test_deck_has_54_cards(self):
        deck = full_deck_tuples()
        assert len(deck) == 54

    def test_deck_has_2_jokers(self):
        deck = full_deck_tuples()
        jokers = [c for c in deck if c[0] == 'Joker']
        assert len(jokers) == 2


class TestTupleValue:
    def test_ace(self):
        assert tuple_value('A', 'Hearts') == 1

    def test_number_card(self):
        assert tuple_value('5', 'Spades') == 5

    def test_face_card(self):
        assert tuple_value('J', 'Hearts') == 10
        assert tuple_value('Q', 'Clubs') == 10

    def test_red_king(self):
        assert tuple_value('K', 'Hearts') == -1
        assert tuple_value('K', 'Diamonds') == -1

    def test_black_king(self):
        assert tuple_value('K', 'Spades') == 10
        assert tuple_value('K', 'Clubs') == 10

    def test_joker(self):
        assert tuple_value('Joker', 'None') == 0


class TestCardTrackerInit:
    def test_initialize(self):
        tracker = CardTracker()
        known = {0: Card('A', 'Hearts'), 1: Card('3', 'Spades')}
        tracker.initialize(known, 4, ['Opp1', 'Opp2'])

        assert tracker.own_hand[0] == ('A', 'Hearts')
        assert tracker.own_hand[1] == ('3', 'Spades')
        assert tracker.own_hand[2] is None
        assert tracker.own_hand[3] is None
        assert 'Opp1' in tracker.opponent_hands
        assert tracker.opponent_hand_sizes['Opp1'] == 4


class TestSyncDiscard:
    def test_sync_adds_new_cards(self):
        tracker = CardTracker()
        tracker.initialize({}, 4, ['Opp'])
        game_discard = [Card('5', 'Hearts'), Card('3', 'Clubs')]
        tracker.sync_discard(game_discard)
        assert len(tracker.discard_pile) == 2

    def test_sync_handles_reshuffle(self):
        """After reshuffle, discard shrinks — tracker should match."""
        tracker = CardTracker()
        tracker.initialize({}, 4, ['Opp'])
        # Simulate many cards in discard
        big_discard = [Card('5', 'Hearts'), Card('3', 'Clubs'), Card('7', 'Diamonds'),
                       Card('Q', 'Spades'), Card('A', 'Hearts')]
        tracker.sync_discard(big_discard)
        assert len(tracker.discard_pile) == 5

        # After reshuffle, only the top card remains
        small_discard = [Card('A', 'Hearts')]
        tracker.sync_discard(small_discard)
        assert len(tracker.discard_pile) == 1
        assert tracker.discard_pile[0] == ('A', 'Hearts')

    def test_unaccounted_correct_after_reshuffle(self):
        """Reshuffle should not corrupt unaccounted card count."""
        tracker = CardTracker()
        known = {0: Card('A', 'Hearts'), 1: Card('3', 'Spades')}
        tracker.initialize(known, 4, ['Opp'])

        # Add cards to discard
        discard_cards = [Card('5', 'Hearts'), Card('7', 'Diamonds'), Card('Q', 'Spades')]
        tracker.sync_discard(discard_cards)
        # 54 - 2 known - 3 discard = 49 unaccounted
        assert len(tracker.unaccounted_cards()) == 49

        # Reshuffle: only top card stays
        tracker.sync_discard([Card('Q', 'Spades')])
        # 54 - 2 known - 1 discard = 51 unaccounted
        assert len(tracker.unaccounted_cards()) == 51


class TestUnaccountedCards:
    def test_starts_with_54_minus_known(self):
        tracker = CardTracker()
        known = {0: Card('A', 'Hearts'), 1: Card('3', 'Spades')}
        tracker.initialize(known, 4, ['Opp'])
        remaining = tracker.unaccounted_cards()
        # 54 total - 2 known own cards = 52 unaccounted
        assert len(remaining) == 52

    def test_discard_reduces_unaccounted(self):
        tracker = CardTracker()
        tracker.initialize({}, 4, ['Opp'])
        initial_count = len(tracker.unaccounted_cards())
        tracker.card_to_discard(('5', 'Hearts'))
        after_count = len(tracker.unaccounted_cards())
        assert after_count == initial_count - 1

    def test_setting_own_card_reduces_unaccounted(self):
        tracker = CardTracker()
        tracker.initialize({}, 4, ['Opp'])
        initial_count = len(tracker.unaccounted_cards())
        tracker.set_own_card(0, ('7', 'Diamonds'))
        after_count = len(tracker.unaccounted_cards())
        assert after_count == initial_count - 1

    def test_setting_opponent_card_reduces_unaccounted(self):
        tracker = CardTracker()
        tracker.initialize({}, 4, ['Opp'])
        initial_count = len(tracker.unaccounted_cards())
        tracker.set_opponent_card('Opp', 0, ('Q', 'Clubs'))
        after_count = len(tracker.unaccounted_cards())
        assert after_count == initial_count - 1


class TestExpectedValues:
    def test_expected_value_changes_as_cards_accounted(self):
        tracker = CardTracker()
        tracker.initialize({}, 4, ['Opp'])
        ev1 = tracker.expected_value_of_unknown()

        # Discard a bunch of low cards
        for suit in ['Hearts', 'Diamonds', 'Clubs']:
            tracker.card_to_discard(('A', suit))

        ev2 = tracker.expected_value_of_unknown()
        # After removing low cards, expected value should increase
        assert ev2 > ev1

    def test_expected_value_at_known_position(self):
        tracker = CardTracker()
        known = {0: Card('A', 'Hearts')}
        tracker.initialize(known, 4, ['Opp'])
        assert tracker.expected_value_at_position(0) == 1

    def test_expected_value_at_unknown_position(self):
        tracker = CardTracker()
        tracker.initialize({}, 4, ['Opp'])
        ev = tracker.expected_value_at_position(0)
        assert ev == tracker.expected_value_of_unknown()

    def test_expected_own_score_mixes_known_and_unknown(self):
        tracker = CardTracker()
        known = {0: Card('A', 'Hearts'), 1: Card('2', 'Spades')}
        tracker.initialize(known, 4, ['Opp'])
        score = tracker.expected_own_score()
        e_unknown = tracker.expected_value_of_unknown()
        expected = 1 + 2 + 2 * e_unknown
        assert abs(score - expected) < 0.01

    def test_expected_opponent_score(self):
        tracker = CardTracker()
        tracker.initialize({}, 4, ['Opp'])
        tracker.set_opponent_card('Opp', 0, ('10', 'Hearts'))
        score = tracker.expected_opponent_score('Opp')
        e_unknown = tracker.expected_value_of_unknown()
        expected = 10 + 3 * e_unknown
        assert abs(score - expected) < 0.01


class TestPositionTracking:
    def test_own_unknown_positions(self):
        tracker = CardTracker()
        known = {0: Card('A', 'Hearts')}
        tracker.initialize(known, 4, ['Opp'])
        unknowns = tracker.own_unknown_positions()
        assert unknowns == [1, 2, 3]

    def test_own_card_swapped_out(self):
        tracker = CardTracker()
        known = {0: Card('A', 'Hearts'), 1: Card('3', 'Spades')}
        tracker.initialize(known, 4, ['Opp'])
        tracker.own_card_swapped_out(0)
        assert tracker.own_hand[0] is None
        assert 0 in tracker.own_unknown_positions()

    def test_worst_own_position(self):
        tracker = CardTracker()
        known = {0: Card('A', 'Hearts'), 1: Card('10', 'Spades'), 2: Card('3', 'Clubs')}
        tracker.initialize(known, 4, ['Opp'])
        pos, val = tracker.worst_own_position()
        assert pos == 1
        assert val == 10

    def test_remove_own_position_shifts(self):
        tracker = CardTracker()
        known = {0: Card('A', 'Hearts'), 1: Card('3', 'Spades'), 2: Card('5', 'Clubs'), 3: Card('7', 'Diamonds')}
        tracker.initialize(known, 4, ['Opp'])
        tracker.remove_own_position(1)
        assert len(tracker.own_hand) == 3
        assert tracker.own_hand[0] == ('A', 'Hearts')
        assert tracker.own_hand[1] == ('5', 'Clubs')
        assert tracker.own_hand[2] == ('7', 'Diamonds')

    def test_opponent_remove_position_shifts(self):
        tracker = CardTracker()
        tracker.initialize({}, 4, ['Opp'])
        tracker.set_opponent_card('Opp', 0, ('A', 'Hearts'))
        tracker.set_opponent_card('Opp', 1, ('3', 'Spades'))
        tracker.set_opponent_card('Opp', 2, ('5', 'Clubs'))
        tracker.set_opponent_card('Opp', 3, ('7', 'Diamonds'))
        tracker.opponent_remove_position('Opp', 1)
        assert len(tracker.opponent_hands['Opp']) == 3
        assert tracker.opponent_hands['Opp'][0] == ('A', 'Hearts')
        assert tracker.opponent_hands['Opp'][1] == ('5', 'Clubs')
        assert tracker.opponent_hands['Opp'][2] == ('7', 'Diamonds')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
