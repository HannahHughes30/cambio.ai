"""Loss analysis and A/B testing framework for BayesianV2 vs BayesianV1.

Usage:
    python3 analysis.py                  # Full loss analysis
    python3 analysis.py --ab             # A/B test: V2 vs V2-no-disruption vs V1
    python3 analysis.py --matches 500    # More matches for statistical significance
"""

import argparse
import statistics
from collections import Counter, defaultdict

from simulation import Tournament, Match, compute_round_stats, create_agent, AGENT_REGISTRY


# ---------------------------------------------------------------------------
# Loss analysis
# ---------------------------------------------------------------------------

def run_loss_analysis(num_matches=200, point_limit=100):
    """Run V2 vs V1 matches and categorize V2 losses."""
    v2_config = {'type': 'bayesian_v2', 'name': 'V2'}
    v1_config = {'type': 'bayesian', 'name': 'V1'}
    configs = [v2_config, v1_config]

    tourney = Tournament(configs, num_matches=num_matches, point_limit=point_limit)
    result = tourney.play()

    summary = result['summary']
    match_results = result['match_results']

    # Collect per-round stats across all matches
    all_round_stats = []
    for mr in match_results:
        for rr in mr['round_results']:
            all_round_stats.append(compute_round_stats(rr))

    # --- Basic win rates ---
    v2_wins = summary['win_counts'].get('V2', 0)
    v1_wins = summary['win_counts'].get('V1', 0)
    v2_wr = summary['win_rates'].get('V2', 0)
    v1_wr = summary['win_rates'].get('V1', 0)
    avg_rounds = summary['avg_rounds']

    print(f"\n{'='*60}")
    print(f" V2 vs V1 LOSS ANALYSIS ({num_matches} matches)")
    print(f"{'='*60}")
    print(f"Overall: V2 {v2_wr:.0%} ({v2_wins}W), V1 {v1_wr:.0%} ({v1_wins}W)")
    print(f"Avg rounds/match: {avg_rounds:.1f}")

    # --- Cambio calling stats ---
    v2_calls = 0
    v1_calls = 0
    v2_caller_wins = 0
    v1_caller_wins = 0

    for rs in all_round_stats:
        caller = rs['cambio_caller']
        winner = rs['winner']
        if caller == 'V2':
            v2_calls += 1
            if winner == 'V2':
                v2_caller_wins += 1
        elif caller == 'V1':
            v1_calls += 1
            if winner == 'V1':
                v1_caller_wins += 1

    total_rounds = len(all_round_stats)
    print(f"\n--- CAMBIO CALLING ---")
    print(f"{'':15s} {'V2':>8s} {'V1':>8s}")
    print(f"{'Calls':15s} {v2_calls/total_rounds if total_rounds else 0:>7.0%} {v1_calls/total_rounds if total_rounds else 0:>7.0%}")
    print(f"{'Caller wins':15s} {v2_caller_wins/v2_calls if v2_calls else 0:>7.0%} {v1_caller_wins/v1_calls if v1_calls else 0:>7.0%}")

    # --- Power usage ---
    power_types = ['peek_own', 'peek_opponent', 'blind_swap', 'king_swap',
                   'third_party_swap', 'king_peek_swap']
    v2_power = Counter()
    v1_power = Counter()
    v2_discard_draws = 0
    v1_discard_draws = 0
    v2_swaps = 0
    v1_swaps = 0

    for rs in all_round_stats:
        for pt, cnt in rs['power_usage'].get('V2', {}).items():
            v2_power[pt] += cnt
        for pt, cnt in rs['power_usage'].get('V1', {}).items():
            v1_power[pt] += cnt
        v2_discard_draws += rs['cards_drawn_from_discard'].get('V2', 0)
        v1_discard_draws += rs['cards_drawn_from_discard'].get('V1', 0)
        v2_swaps += rs['cards_swapped'].get('V2', 0)
        v1_swaps += rs['cards_swapped'].get('V1', 0)

    print(f"\n--- POWER USAGE (total across {total_rounds} rounds) ---")
    print(f"{'':20s} {'V2':>8s} {'V1':>8s}")
    for pt in power_types:
        v2c = v2_power.get(pt, 0)
        v1c = v1_power.get(pt, 0)
        if v2c > 0 or v1c > 0:
            print(f"{pt:20s} {v2c:>8d} {v1c:>8d}")
    print(f"{'Discard draws':20s} {v2_discard_draws:>8d} {v1_discard_draws:>8d}")
    print(f"{'Card swaps':20s} {v2_swaps:>8d} {v1_swaps:>8d}")

    # --- Score distributions ---
    v2_scores = summary['score_distributions']['V2']
    v1_scores = summary['score_distributions']['V1']
    print(f"\n--- SCORE DISTRIBUTIONS (final match scores) ---")
    print(f"{'':15s} {'V2':>10s} {'V1':>10s}")
    print(f"{'Mean':15s} {v2_scores['mean']:>10.1f} {v1_scores['mean']:>10.1f}")
    print(f"{'Median':15s} {v2_scores['median']:>10.1f} {v1_scores['median']:>10.1f}")
    print(f"{'Stdev':15s} {v2_scores['stdev']:>10.1f} {v1_scores['stdev']:>10.1f}")
    print(f"{'Range':15s} {v2_scores['min']:>4d}-{v2_scores['max']:<5d} {v1_scores['min']:>4d}-{v1_scores['max']:<5d}")

    # --- Loss categorization ---
    categorize_losses(all_round_stats, match_results)

    return result


def categorize_losses(all_round_stats, match_results):
    """Categorize V2's round losses."""
    bad_cambio = 0       # V2 called but lost
    opp_better_call = 0  # V1 called and won
    card_luck = 0        # No cambio involved, V2 just had worse score
    total_v2_round_losses = 0

    for rs in all_round_stats:
        if rs['winner'] == 'V1':
            total_v2_round_losses += 1
            caller = rs['cambio_caller']
            if caller == 'V2':
                bad_cambio += 1
            elif caller == 'V1':
                opp_better_call += 1
            else:
                card_luck += 1

    if total_v2_round_losses == 0:
        print(f"\n--- LOSS CATEGORIES ---")
        print("V2 never lost a round!")
        return

    print(f"\n--- LOSS CATEGORIES (V2 round losses: {total_v2_round_losses}) ---")
    print(f"Bad cambio timing:    {bad_cambio:>4d} ({bad_cambio/total_v2_round_losses:.0%})")
    print(f"Opponent better call: {opp_better_call:>4d} ({opp_better_call/total_v2_round_losses:.0%})")
    print(f"Card luck / other:    {card_luck:>4d} ({card_luck/total_v2_round_losses:.0%})")


# ---------------------------------------------------------------------------
# A/B Testing Framework
# ---------------------------------------------------------------------------

class ABTest:
    """Run two agent variants against a common opponent and compare."""

    def __init__(self, variant_a_config, variant_b_config, opponent_config,
                 num_matches=200, point_limit=100):
        self.variant_a = variant_a_config
        self.variant_b = variant_b_config
        self.opponent = opponent_config
        self.num_matches = num_matches
        self.point_limit = point_limit

    def run(self):
        """Run both variants against opponent, return comparison dict."""
        print(f"\n--- A/B Test: {self.variant_a['name']} vs {self.variant_b['name']} "
              f"(opponent: {self.opponent['name']}, {self.num_matches} matches each) ---")

        result_a = self._run_variant(self.variant_a)
        result_b = self._run_variant(self.variant_b)

        return self._compare(result_a, result_b)

    def _run_variant(self, variant_config):
        """Run a single variant against the opponent."""
        configs = [variant_config, self.opponent]
        tourney = Tournament(configs, num_matches=self.num_matches,
                             point_limit=self.point_limit)
        return tourney.play()

    def _compare(self, result_a, result_b):
        """Compare win rates and scores between two variant results."""
        name_a = self.variant_a['name']
        name_b = self.variant_b['name']

        wr_a = result_a['summary']['win_rates'].get(name_a, 0)
        wr_b = result_b['summary']['win_rates'].get(name_b, 0)
        delta = wr_a - wr_b

        # Score distributions
        scores_a = result_a['summary']['score_distributions'][name_a]
        scores_b = result_b['summary']['score_distributions'][name_b]

        comparison = {
            'variant_a': name_a,
            'variant_b': name_b,
            'win_rate_a': wr_a,
            'win_rate_b': wr_b,
            'delta': delta,
            'avg_score_a': scores_a['mean'],
            'avg_score_b': scores_b['mean'],
        }

        print(f"\n  {name_a:20s} win rate: {wr_a:.1%}  avg score: {scores_a['mean']:.1f}")
        print(f"  {name_b:20s} win rate: {wr_b:.1%}  avg score: {scores_b['mean']:.1f}")
        print(f"  Delta (A - B):      {delta:+.1%}")

        return comparison


def run_ab_tests(num_matches=200):
    """Run A/B tests to isolate impact of V2 improvements."""
    opponent = {'type': 'bayesian', 'name': 'V1'}

    print(f"\n{'='*60}")
    print(f" A/B TESTS ({num_matches} matches each)")
    print(f"{'='*60}")

    # Test 1: Current V2 vs V1
    test1 = ABTest(
        variant_a_config={'type': 'bayesian_v2', 'name': 'V2'},
        variant_b_config={'type': 'bayesian', 'name': 'V1-baseline'},
        opponent_config=opponent,
        num_matches=num_matches,
    )
    r1 = test1.run()

    # Test 2: V2 vs V2 (sanity check — should be ~50/50)
    test2 = ABTest(
        variant_a_config={'type': 'bayesian_v2', 'name': 'V2-A'},
        variant_b_config={'type': 'bayesian_v2', 'name': 'V2-B'},
        opponent_config={'type': 'bayesian_v2', 'name': 'V2-opp'},
        num_matches=num_matches,
    )
    # For sanity check, compare V2-A vs V2-opp directly
    print(f"\n--- Sanity check: V2 vs V2 ---")
    configs_sanity = [
        {'type': 'bayesian_v2', 'name': 'V2-A'},
        {'type': 'bayesian_v2', 'name': 'V2-B'},
    ]
    tourney_sanity = Tournament(configs_sanity, num_matches=num_matches)
    sanity_result = tourney_sanity.play()
    s = sanity_result['summary']
    print(f"  V2-A: {s['win_rates'].get('V2-A', 0):.1%}  V2-B: {s['win_rates'].get('V2-B', 0):.1%}")

    # Test 3: V2 vs Smart (regression check)
    print(f"\n--- Regression check: V2 vs Smart ---")
    configs_regression = [
        {'type': 'bayesian_v2', 'name': 'V2'},
        {'type': 'smart', 'name': 'Smart'},
    ]
    tourney_reg = Tournament(configs_regression, num_matches=num_matches)
    reg_result = tourney_reg.play()
    s = reg_result['summary']
    print(f"  V2: {s['win_rates'].get('V2', 0):.1%}  Smart: {s['win_rates'].get('Smart', 0):.1%}")

    # Test 4: V2 vs Base (regression check)
    print(f"\n--- Regression check: V2 vs Base ---")
    configs_base = [
        {'type': 'bayesian_v2', 'name': 'V2'},
        {'type': 'base', 'name': 'Base'},
    ]
    tourney_base = Tournament(configs_base, num_matches=num_matches)
    base_result = tourney_base.play()
    s = base_result['summary']
    print(f"  V2: {s['win_rates'].get('V2', 0):.1%}  Base: {s['win_rates'].get('Base', 0):.1%}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='V2 Loss Analysis & A/B Testing')
    parser.add_argument('--matches', type=int, default=200,
                        help='Number of matches per test')
    parser.add_argument('--ab', action='store_true',
                        help='Run A/B tests instead of loss analysis')
    parser.add_argument('--all', action='store_true',
                        help='Run both loss analysis and A/B tests')
    args = parser.parse_args()

    if args.ab:
        run_ab_tests(args.matches)
    elif args.all:
        run_loss_analysis(args.matches)
        run_ab_tests(args.matches)
    else:
        run_loss_analysis(args.matches)


if __name__ == '__main__':
    main()
