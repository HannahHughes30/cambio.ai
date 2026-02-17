"""Tests for BayesianAgent."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from game import Card, CambioGame, Player
from agents.bayesian_agent import BayesianAgent
from agents.smart_agent import SmartAgent


def make_game(agent, opponent):
    """Create a simple 2-player game and deal."""
    game = CambioGame([agent, opponent])
    game.deal()
    return game


class TestObserveTurn:
    def test_updates_tracker_from_discard(self):
        agent = BayesianAgent("Bayes")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        initial_discard_len = len(agent.tracker.discard_pile)
        # Simulate a turn where opponent discards
        turn_data = {
            'player': 'Opp',
            'draw_source': 'deck',
            'action': 'discard',
            'power_type': None,
            'power_target_player': None,
            'power_target_position': None,
            'discarded_card': '5H',
            'discarded_value': 5,
            'hand_size': 4,
            'swap_position': None,
        }
        # Add a card to game discard to simulate
        game.discard.append(Card('5', 'Hearts'))
        agent.observe_turn(turn_data, game)

        assert len(agent.tracker.discard_pile) > initial_discard_len

    def test_blind_swap_clears_own_known(self):
        agent = BayesianAgent("Bayes")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        # Agent knows position 0
        assert 0 in agent.known

        turn_data = {
            'player': 'Opp',
            'draw_source': 'deck',
            'action': 'power',
            'power_type': 'blind_swap',
            'power_target_player': 'Bayes',
            'power_target_position': 0,
            'discarded_card': 'JH',
            'discarded_value': 10,
            'hand_size': 4,
            'swap_position': 1,
        }
        agent.observe_turn(turn_data, game)

        assert 0 not in agent.known
        assert agent.tracker.own_hand[0] is None

    def test_self_blind_swap_clears_own_position(self):
        """Bug fix C: own blind/king swap should mark own position as unknown."""
        agent = BayesianAgent("Bayes")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        # Agent knows position 0
        assert 0 in agent.known
        old_card = agent.tracker.own_hand[0]
        assert old_card is not None

        turn_data = {
            'player': 'Bayes',
            'draw_source': 'deck',
            'action': 'power',
            'power_type': 'blind_swap',
            'power_target_player': 'Opp',
            'power_target_position': 2,
            'discarded_card': 'JH',
            'discarded_value': 10,
            'hand_size': 4,
            'swap_position': 0,
        }
        agent.observe_turn(turn_data, game)

        # Position 0 should now be unknown
        assert 0 not in agent.known
        assert agent.tracker.own_hand[0] is None

    def test_opponent_discard_swap_tracked(self):
        """When opponent draws from discard and swaps, we know what they placed."""
        agent = BayesianAgent("Bayes")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        # Set up a known discard top
        game.discard.append(Card('3', 'Hearts'))
        agent.tracker.sync_discard(game.discard)
        agent._prev_discard_top = ('3', 'Hearts')

        # Opponent draws from discard and swaps into position 1
        # After this, game discard top changes (the old card from pos 1 goes to discard)
        game.discard.pop()  # opponent took the 3H
        game.discard.append(Card('K', 'Spades'))  # old card from pos 1

        turn_data = {
            'player': 'Opp',
            'draw_source': 'discard',
            'action': 'swap',
            'power_type': None,
            'power_target_player': None,
            'power_target_position': None,
            'discarded_card': 'KS',
            'discarded_value': 10,
            'hand_size': 4,
            'swap_position': 1,
        }
        agent.observe_turn(turn_data, game)

        # Agent should know opponent's position 1 is the 3 of Hearts
        assert agent.tracker.opponent_hands['Opp'][1] == ('3', 'Hearts')

    def test_opponent_deck_swap_clears_position(self):
        """When opponent draws from deck and swaps, their position becomes unknown."""
        agent = BayesianAgent("Bayes")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        # First set a known card at opponent position 0
        agent.tracker.set_opponent_card('Opp', 0, ('5', 'Hearts'))

        game.discard.append(Card('5', 'Hearts'))  # old card discarded

        turn_data = {
            'player': 'Opp',
            'draw_source': 'deck',
            'action': 'swap',
            'power_type': None,
            'power_target_player': None,
            'power_target_position': None,
            'discarded_card': '5H',
            'discarded_value': 5,
            'hand_size': 4,
            'swap_position': 0,
        }
        agent.observe_turn(turn_data, game)

        # Position should now be unknown
        assert agent.tracker.opponent_hands['Opp'][0] is None

    def test_opponent_peek_data_synced(self):
        """Bug fix A: opponent peek results stored in opponent_known get synced to tracker."""
        agent = BayesianAgent("Bayes")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        # Simulate the game engine storing peek data
        opp_index = game.players.index(opp)
        agent.opponent_known[opp_index] = {2: Card('7', 'Diamonds')}

        turn_data = {
            'player': 'Bayes',
            'draw_source': 'deck',
            'action': 'power',
            'power_type': 'peek_opponent',
            'power_target_player': 'Opp',
            'power_target_position': 2,
            'discarded_card': '9H',
            'discarded_value': 9,
            'hand_size': 4,
            'swap_position': None,
        }
        agent.observe_turn(turn_data, game)

        assert agent.tracker.opponent_hands['Opp'][2] == ('7', 'Diamonds')


class TestChooseDraw:
    def test_takes_joker_from_discard(self):
        agent = BayesianAgent("Bayes")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        game.discard.append(Card('Joker', 'None'))
        choice = agent.choose_draw(game)
        assert choice == 'discard'

    def test_takes_red_king_from_discard(self):
        agent = BayesianAgent("Bayes")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        game.discard.append(Card('K', 'Hearts'))
        choice = agent.choose_draw(game)
        assert choice == 'discard'

    def test_skips_moderate_discard(self):
        """Tighter threshold: value=1 (Ace) no longer auto-taken from discard."""
        agent = BayesianAgent("Bayes")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        # Give agent all low cards so improvement isn't >= 3
        agent.hand = [Card('A', 'Hearts'), Card('2', 'Spades'), Card('3', 'Clubs'), Card('A', 'Diamonds')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1], 2: agent.hand[2], 3: agent.hand[3]}
        for pos, card in agent.known.items():
            agent.tracker.set_own_card(pos, (card.rank, card.suit))

        game.discard.append(Card('A', 'Spades'))  # value 1, small improvement
        choice = agent.choose_draw(game)
        assert choice == 'deck'

    def test_skips_high_discard(self):
        agent = BayesianAgent("Bayes")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        # Ensure agent has low known cards so high discard isn't useful
        agent.hand = [Card('A', 'Hearts'), Card('2', 'Spades'), Card('3', 'Clubs'), Card('A', 'Diamonds')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1], 2: agent.hand[2], 3: agent.hand[3]}
        for pos, card in agent.known.items():
            agent.tracker.set_own_card(pos, (card.rank, card.suit))

        game.discard.append(Card('K', 'Spades'))  # value 10
        choice = agent.choose_draw(game)
        assert choice == 'deck'

    def test_takes_discard_with_big_improvement(self):
        agent = BayesianAgent("Bayes")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        # Give agent a high card so a low discard gives >= 3 improvement
        agent.hand = [Card('A', 'Hearts'), Card('Q', 'Spades'), Card('3', 'Clubs'), Card('A', 'Diamonds')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1], 2: agent.hand[2], 3: agent.hand[3]}
        for pos, card in agent.known.items():
            agent.tracker.set_own_card(pos, (card.rank, card.suit))

        game.discard.append(Card('3', 'Hearts'))  # value 3, improvement = 10-3 = 7
        choice = agent.choose_draw(game)
        assert choice == 'discard'


class TestChooseAction:
    def test_swaps_into_worst_position(self):
        agent = BayesianAgent("Bayes")
        agent.hand = [Card('A', 'Hearts'), Card('10', 'Spades'), Card('3', 'Clubs'), Card('2', 'Diamonds')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1], 2: agent.hand[2], 3: agent.hand[3]}
        agent.tracker.initialize(agent.known, 4, [])

        drawn = Card('2', 'Hearts')  # value 2
        action = agent.choose_action(drawn)
        assert action['type'] == 'swap'
        assert action['position'] == 1  # 10-value position

    def test_discards_when_no_improvement(self):
        agent = BayesianAgent("Bayes")
        agent.hand = [Card('A', 'Hearts'), Card('2', 'Spades'), Card('3', 'Clubs'), Card('A', 'Diamonds')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1], 2: agent.hand[2], 3: agent.hand[3]}
        agent.tracker.initialize(agent.known, 4, [])

        drawn = Card('Q', 'Hearts')  # value 10
        action = agent.choose_action(drawn)
        assert action['type'] == 'discard'

    def test_info_bonus_prefers_unknown_slot(self):
        """Low drawn card should prefer unknown position over known-medium for info gain."""
        agent = BayesianAgent("Bayes")
        agent.hand = [Card('A', 'Hearts'), Card('4', 'Spades'), Card('5', 'Clubs'), Card('6', 'Diamonds')]
        # Only know positions 0 and 1
        agent.known = {0: agent.hand[0], 1: agent.hand[1]}
        agent.tracker.initialize(agent.known, 4, [])

        drawn = Card('3', 'Hearts')  # value 3
        action = agent.choose_action(drawn)
        assert action['type'] == 'swap'
        # Should pick an unknown position (2 or 3) due to info bonus,
        # since improvement at pos 1 is only 4-3=1 but unknown positions get +1 info bonus
        # E[unknown] ~5.4 so improvement ~5.4-3=2.4 + 1 info bonus = 3.4 vs pos 1 improvement = 1
        assert action['position'] in [2, 3]


class TestChoosePowerAction:
    def test_peeks_unknown_own_position(self):
        agent = BayesianAgent("Bayes")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        # Agent knows positions 0, 1 by default
        card = Card('7', 'Hearts')
        result = agent.choose_power_action(card, game, [opp])
        assert result is not None
        assert result['type'] == 'peek_own'
        assert result['position'] in [2, 3]

    def test_peeks_opponent_unknown_position(self):
        agent = BayesianAgent("Bayes")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        card = Card('9', 'Hearts')
        result = agent.choose_power_action(card, game, [opp])
        assert result is not None
        assert result['type'] == 'peek_opponent'
        assert result['opponent'] == opp

    def test_blind_swap_only_when_ev_positive(self):
        agent = BayesianAgent("Bayes")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        # Give agent all low cards — worst known is still low
        agent.hand = [Card('A', 'Hearts'), Card('2', 'Spades'), Card('3', 'Clubs'), Card('A', 'Diamonds')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1], 2: agent.hand[2], 3: agent.hand[3]}
        for pos, card in agent.known.items():
            agent.tracker.set_own_card(pos, (card.rank, card.suit))

        card = Card('J', 'Hearts')
        result = agent.choose_power_action(card, game, [opp])
        # Worst known = 3 which is NOT > E[unknown] + 1 (~6.4), so should skip
        assert result is None

    def test_blind_swap_when_worst_card_is_bad(self):
        agent = BayesianAgent("Bayes")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        # Give agent a very bad card
        agent.hand = [Card('A', 'Hearts'), Card('K', 'Spades'), Card('3', 'Clubs'), Card('A', 'Diamonds')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1], 2: agent.hand[2], 3: agent.hand[3]}
        for pos, card in agent.known.items():
            agent.tracker.set_own_card(pos, (card.rank, card.suit))

        card = Card('J', 'Hearts')
        result = agent.choose_power_action(card, game, [opp])
        # Worst known = K of Spades (10) which IS > E[unknown] + 1, so should swap
        assert result is not None
        assert result['type'] == 'blind_swap'
        assert result['my_position'] == 1

    def test_blind_swap_targets_known_low_opponent_card(self):
        """Smart targeting: blind swap should prefer known-low opponent positions."""
        agent = BayesianAgent("Bayes")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        # Give agent a bad card
        agent.hand = [Card('A', 'Hearts'), Card('Q', 'Spades'), Card('3', 'Clubs'), Card('A', 'Diamonds')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1], 2: agent.hand[2], 3: agent.hand[3]}
        for pos, card in agent.known.items():
            agent.tracker.set_own_card(pos, (card.rank, card.suit))

        # Set known opponent cards: position 2 has an Ace (low = good target)
        agent.tracker.set_opponent_card('Opp', 2, ('A', 'Clubs'))

        card = Card('J', 'Hearts')
        result = agent.choose_power_action(card, game, [opp])
        assert result is not None
        assert result['type'] == 'blind_swap'
        assert result['opp_position'] == 2  # Should target the known-low position

    def test_black_king_more_aggressive_threshold(self):
        """Black King should be used more aggressively since we peek before swapping."""
        agent = BayesianAgent("Bayes")
        opp = SmartAgent("Opp")
        game = make_game(agent, opp)
        agent._ensure_initialized(game)

        # Give agent a mediocre card (value 5) — not bad enough for blind swap threshold
        agent.hand = [Card('A', 'Hearts'), Card('5', 'Spades'), Card('3', 'Clubs'), Card('A', 'Diamonds')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1], 2: agent.hand[2], 3: agent.hand[3]}
        for pos, card in agent.known.items():
            agent.tracker.set_own_card(pos, (card.rank, card.suit))

        # With J/Q this wouldn't trigger (5 < E[unknown] + 1 ~= 6.4)
        # But Black King should trigger with lower threshold
        card = Card('K', 'Spades')
        result = agent.choose_power_action(card, game, [opp])
        assert result is not None
        assert result['type'] == 'king_swap'


class TestBlackKingConditionalSwap:
    def test_swaps_when_opponent_card_better(self):
        """Black King should swap when opponent's card is lower than ours."""
        agent = BayesianAgent("Bayes")
        opp = Player("Opp")
        opp.hand = [Card('A', 'Hearts'), Card('2', 'Spades'), Card('3', 'Clubs'), Card('A', 'Diamonds')]

        agent.hand = [Card('Q', 'Hearts'), Card('2', 'Clubs'), Card('3', 'Diamonds'), Card('A', 'Spades')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1]}
        agent.tracker.initialize(agent.known, 4, ['Opp'])

        game = CambioGame([agent, opp])
        game.discard = [Card('5', 'Hearts')]

        card = Card('K', 'Spades')
        # my_pos=0 (Q, value 10), opp_pos=0 (A, value 1)
        result = agent.use_card_power(card, game, opponent=opp, my_pos=0, opp_pos=0, verbose=False)

        assert result is True
        # Swap should have happened: agent gets the Ace
        assert agent.hand[0].rank == 'A'
        assert agent.hand[0].suit == 'Hearts'

    def test_no_swap_when_opponent_card_worse(self):
        """Black King should NOT swap when opponent's card is higher than ours."""
        agent = BayesianAgent("Bayes")
        opp = Player("Opp")
        opp.hand = [Card('Q', 'Hearts'), Card('2', 'Spades'), Card('3', 'Clubs'), Card('A', 'Diamonds')]

        agent.hand = [Card('A', 'Hearts'), Card('2', 'Clubs'), Card('3', 'Diamonds'), Card('A', 'Spades')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1]}
        agent.tracker.initialize(agent.known, 4, ['Opp'])

        game = CambioGame([agent, opp])
        game.discard = [Card('5', 'Hearts')]

        card = Card('K', 'Spades')
        # my_pos=0 (A, value 1), opp_pos=0 (Q, value 10)
        result = agent.use_card_power(card, game, opponent=opp, my_pos=0, opp_pos=0, verbose=False)

        assert result is True
        # Swap should NOT have happened: agent still has Ace
        assert agent.hand[0].rank == 'A'
        assert agent.hand[0].suit == 'Hearts'

    def test_records_peeked_card_even_without_swap(self):
        """Black King peek should be recorded in tracker even when not swapping."""
        agent = BayesianAgent("Bayes")
        opp = Player("Opp")
        opp.hand = [Card('Q', 'Hearts'), Card('2', 'Spades'), Card('3', 'Clubs'), Card('A', 'Diamonds')]

        agent.hand = [Card('A', 'Hearts'), Card('2', 'Clubs'), Card('3', 'Diamonds'), Card('A', 'Spades')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1]}
        agent.tracker.initialize(agent.known, 4, ['Opp'])

        game = CambioGame([agent, opp])
        game.discard = [Card('5', 'Hearts')]

        card = Card('K', 'Spades')
        agent.use_card_power(card, game, opponent=opp, my_pos=0, opp_pos=0, verbose=False)

        # Tracker should know opponent's position 0
        assert agent.tracker.opponent_hands['Opp'][0] == ('Q', 'Hearts')


class TestCallCambio:
    def test_requires_knowledge(self):
        """Low knowledge + no EV dominance should block cambio."""
        agent = BayesianAgent("Bayes")
        agent.hand = [Card('5', 'Hearts'), Card('6', 'Spades'), Card('3', 'Clubs'), Card('4', 'Diamonds')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1]}  # Only know 2 of 4
        agent.tracker.initialize(agent.known, 4, ['Opp'])
        # Known score = 5+6=11, unknowns ~5.4 each, total ~21.8
        # Opponent expected ~21.6 — no margin, so neither path triggers
        assert agent.call_cambio() is False

    def test_calls_with_low_score_and_margin(self):
        agent = BayesianAgent("Bayes")
        agent.hand = [Card('A', 'Hearts'), Card('A', 'Spades'), Card('A', 'Diamonds'), Card('A', 'Clubs')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1], 2: agent.hand[2], 3: agent.hand[3]}
        agent.tracker.initialize(agent.known, 4, ['Opp'])
        # Score = 4, E[opp] ~= 4 * E[unknown] which should be much higher
        assert agent.call_cambio() is True

    def test_wont_call_without_margin(self):
        agent = BayesianAgent("Bayes")
        agent.hand = [Card('A', 'Hearts'), Card('2', 'Spades'), Card('3', 'Clubs'), Card('2', 'Diamonds')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1], 2: agent.hand[2], 3: agent.hand[3]}
        agent.tracker.initialize(agent.known, 4, ['Opp'])
        # Score = 8. Set opponent known cards to be low too
        agent.tracker.set_opponent_card('Opp', 0, ('A', 'Clubs'))
        agent.tracker.set_opponent_card('Opp', 1, ('2', 'Hearts'))
        agent.tracker.set_opponent_card('Opp', 2, ('A', 'Spades'))
        agent.tracker.set_opponent_card('Opp', 3, ('2', 'Clubs'))
        # Opp score = 6, our score = 8, no margin => won't call
        assert agent.call_cambio() is False

    def test_adaptive_margin_reduces_with_knowledge(self):
        """When we know all opponent cards, margin should be reduced."""
        agent = BayesianAgent("Bayes")
        agent.hand = [Card('A', 'Hearts'), Card('A', 'Spades'), Card('2', 'Diamonds'), Card('2', 'Clubs')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1], 2: agent.hand[2], 3: agent.hand[3]}
        agent.tracker.initialize(agent.known, 4, ['Opp'])
        # Score = 6
        # Set all opponent cards known (high values)
        agent.tracker.set_opponent_card('Opp', 0, ('8', 'Hearts'))
        agent.tracker.set_opponent_card('Opp', 1, ('8', 'Spades'))
        agent.tracker.set_opponent_card('Opp', 2, ('8', 'Diamonds'))
        agent.tracker.set_opponent_card('Opp', 3, ('8', 'Clubs'))
        # Opp score = 32, our score = 6, large margin even with reduced adaptive_margin
        assert agent.call_cambio() is True


class TestChooseStick:
    def test_matches_discard_top(self):
        agent = BayesianAgent("Bayes")
        agent.hand = [Card('5', 'Hearts'), Card('5', 'Spades'), Card('3', 'Clubs'), Card('A', 'Diamonds')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1], 2: agent.hand[2], 3: agent.hand[3]}
        agent.tracker.initialize(agent.known, 4, ['Opp'])

        # Make a mock game with 5 on top of discard
        game = type('Game', (), {'discard': [Card('5', 'Clubs')]})()
        positions = agent.choose_stick(game)
        assert 0 in positions
        assert 1 in positions
        assert 2 not in positions

    def test_no_match_returns_empty(self):
        agent = BayesianAgent("Bayes")
        agent.hand = [Card('A', 'Hearts'), Card('2', 'Spades'), Card('3', 'Clubs'), Card('4', 'Diamonds')]
        agent.known = {0: agent.hand[0], 1: agent.hand[1], 2: agent.hand[2], 3: agent.hand[3]}
        agent.tracker.initialize(agent.known, 4, ['Opp'])

        game = type('Game', (), {'discard': [Card('K', 'Clubs')]})()
        positions = agent.choose_stick(game)
        assert positions == []


class TestIntegration:
    def test_bayesian_vs_smart_completes(self):
        """Full game between BayesianAgent and SmartAgent completes without error."""
        agent = BayesianAgent("Bayes")
        opp = SmartAgent("Smart")
        game = CambioGame([agent, opp])
        game.deal()
        result = game.play(verbose=False, max_turns=100)
        assert 'winner' in result
        assert result['total_turns'] > 0

    def test_bayesian_vs_bayesian_completes(self):
        """Full game between two BayesianAgents completes without error."""
        a1 = BayesianAgent("Bayes1")
        a2 = BayesianAgent("Bayes2")
        game = CambioGame([a1, a2])
        game.deal()
        result = game.play(verbose=False, max_turns=100)
        assert 'winner' in result

    def test_tracker_ev_changes_during_game(self):
        """Verify E[unknown] is not stuck at a fixed value during a game."""
        agent = BayesianAgent("Bayes")
        opp = SmartAgent("Smart")
        game = CambioGame([agent, opp])
        game.deal()
        agent._ensure_initialized(game)

        ev_values = set()
        for _ in range(20):
            if game.game_over():
                break
            game.play_turn(verbose=False)
            if agent._initialized:
                ev_values.add(round(agent.tracker.expected_value_of_unknown(), 4))

        # EV should change as cards are revealed/discarded
        assert len(ev_values) > 1, f"E[unknown] stayed fixed at {ev_values}"

    def test_many_games_no_crash(self):
        """Run many games to catch edge cases (reshuffles, etc)."""
        for _ in range(50):
            agent = BayesianAgent("Bayes")
            opp = SmartAgent("Smart")
            game = CambioGame([agent, opp])
            game.deal()
            result = game.play(verbose=False, max_turns=100)
            assert 'winner' in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
