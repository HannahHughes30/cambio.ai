"""Ablation study for BayesianV2 features.

Measures the contribution of each V2 feature by disabling it one at a time
and comparing in both 1v1 and 3-player settings.
"""

import argparse
from collections import defaultdict

from scenarios.simulation import Tournament

NUM_MATCHES = 100
POINT_LIMIT = 100

# Each ablation: (flag_name, display_name, kwargs to disable it)
ABLATIONS = [
    ('use_disruption_scoring', 'Disruption Scoring', {'use_disruption_scoring': False}),
    ('use_probabilistic_stick', 'Probabilistic Stick', {'use_probabilistic_stick': False}),
    ('use_preemptive_cambio', 'Preemptive Cambio', {'use_preemptive_cambio': False}),
    ('use_third_party_swaps', 'Third-Party Swaps', {'use_third_party_swaps': False}),
    ('use_smart_peek', 'Smart Peek (9/10)', {'use_smart_peek': False}),
    ('use_aggressive_cambio', 'Aggressive Cambio', {'use_aggressive_cambio': False}),
    ('use_final_round_mode', 'Final-Round Mode', {'use_final_round_mode': False}),
    ('use_opponent_inference', 'Opponent Inference', {'use_opponent_inference': False}),
    ('use_deck_awareness', 'Deck Awareness', {'use_deck_awareness': False}),
]

# Scenarios to test each ablation in
SCENARIOS = [
    {
        'tag': '1v1',
        'label': 'V2 vs Smart (1v1)',
        'baseline_configs': [
            {'type': 'bayesian_v2', 'name': 'V2-Full'},
            {'type': 'smart', 'name': 'Smart'},
        ],
        'ablated_fn': lambda label, kwargs: [
            {'type': 'bayesian_v2', 'name': label, 'kwargs': kwargs},
            {'type': 'smart', 'name': 'Smart'},
        ],
        'h2h_fn': lambda label, kwargs: [
            {'type': 'bayesian_v2', 'name': 'V2-Full'},
            {'type': 'bayesian_v2', 'name': label, 'kwargs': kwargs},
        ],
        'agent_name': 'V2-Full',
    },
    {
        'tag': '3p',
        'label': 'V2 + 2×Smart (3-player)',
        'baseline_configs': [
            {'type': 'bayesian_v2', 'name': 'V2-Full'},
            {'type': 'smart', 'name': 'Smart-1'},
            {'type': 'smart', 'name': 'Smart-2'},
        ],
        'ablated_fn': lambda label, kwargs: [
            {'type': 'bayesian_v2', 'name': label, 'kwargs': kwargs},
            {'type': 'smart', 'name': 'Smart-1'},
            {'type': 'smart', 'name': 'Smart-2'},
        ],
        'h2h_fn': lambda label, kwargs: [
            {'type': 'bayesian_v2', 'name': 'V2-Full'},
            {'type': 'bayesian_v2', 'name': label, 'kwargs': kwargs},
            {'type': 'smart', 'name': 'Smart'},
        ],
        'agent_name': 'V2-Full',
    },
]


def run_tournament(configs, num_matches):
    """Run a tournament and return (win_rates, score_distributions)."""
    tourney = Tournament(configs, num_matches=num_matches, point_limit=POINT_LIMIT)
    result = tourney.play()
    summary = result['summary']
    return summary['win_rates'], summary['score_distributions']


def run_ablation(num_matches=NUM_MATCHES, show_charts=True):
    # results[scenario_tag][feature_display] = {vs_smart_wr, vs_smart_score, vs_full_wr, ...}
    all_results = {}

    for scenario in SCENARIOS:
        tag = scenario['tag']
        label = scenario['label']
        agent = scenario['agent_name']
        results = {}
        all_results[tag] = results

        # ---- Baseline ----
        print(f"\n{'=' * 70}")
        print(f"  BASELINE: {label}")
        print("=" * 70)
        win_rates, score_dists = run_tournament(scenario['baseline_configs'], num_matches)
        baseline_wr = win_rates.get(agent, 0)
        baseline_score = score_dists[agent]['mean']
        results['_baseline_wr'] = baseline_wr
        results['_baseline_score'] = baseline_score
        print(f"  {agent} win rate: {baseline_wr:.0%}  avg score: {baseline_score:.1f}")

        # ---- Feature removal (V2-minus-feature vs Smart(s)) ----
        print(f"\n{'=' * 70}")
        print(f"  FEATURE REMOVAL ({tag}): V2-minus-feature vs Smart")
        print("=" * 70)

        total = len(ABLATIONS)
        for i, (flag, display, kwargs) in enumerate(ABLATIONS):
            ablated_label = f"V2-no-{flag}"
            print(f"\n  [{i+1}/{total}] {display} disabled — {num_matches} matches ...", end=' ', flush=True)
            configs = scenario['ablated_fn'](ablated_label, kwargs)
            win_rates, score_dists = run_tournament(configs, num_matches)
            wr = win_rates.get(ablated_label, 0)
            score = score_dists[ablated_label]['mean']
            results[display] = {
                'vs_smart_wr': wr,
                'vs_smart_score': score,
                'vs_full_wr': None,
                'vs_full_score': None,
            }
            print(f"win={wr:.0%}  avg_score={score:.1f}")

        # ---- Head-to-head (full V2 vs V2-minus-feature) ----
        print(f"\n{'=' * 70}")
        print(f"  HEAD-TO-HEAD ({tag}): Full V2 vs V2-minus-feature")
        print("=" * 70)

        for i, (flag, display, kwargs) in enumerate(ABLATIONS):
            ablated_label = f"V2-no-{flag}"
            print(f"\n  [{i+1}/{total}] {display} disabled — {num_matches} matches ...", end=' ', flush=True)
            configs = scenario['h2h_fn'](ablated_label, kwargs)
            win_rates, score_dists = run_tournament(configs, num_matches)
            full_wr = win_rates.get('V2-Full', 0)
            ablated_wr = win_rates.get(ablated_label, 0)
            results[display]['vs_full_wr'] = ablated_wr
            results[display]['vs_full_score'] = score_dists[ablated_label]['mean']
            print(f"full_win={full_wr:.0%}  ablated_win={ablated_wr:.0%}")

    # ---- Summary tables ----
    print(f"\n{'=' * 100}")
    print("ABLATION STUDY RESULTS")
    print(f"{'=' * 100}")

    for scenario in SCENARIOS:
        tag = scenario['tag']
        label = scenario['label']
        results = all_results[tag]
        baseline_wr = results['_baseline_wr']
        baseline_score = results['_baseline_score']

        print(f"\n  --- {label} ---")
        print(f"  {'Feature':<25} {'vs Smart':>10} {'Δ vs Base':>10} {'vs Full V2':>12} {'Score/Rd':>10}")
        print(f"  {'-'*25} {'-'*10} {'-'*10} {'-'*12} {'-'*10}")
        print(f"  {'Full V2 (baseline)':<25} {baseline_wr:>9.0%} {'—':>10} {'—':>12} {baseline_score:>10.1f}")

        for flag, display, kwargs in ABLATIONS:
            r = results[display]
            delta = r['vs_smart_wr'] - baseline_wr
            h2h = f"{r['vs_full_wr']:.0%}" if r['vs_full_wr'] is not None else "—"
            print(f"  {'− ' + display:<25} {r['vs_smart_wr']:>9.0%} {delta:>+9.0%} {h2h:>12} {r['vs_smart_score']:>10.1f}")

    print()

    # ---- Charts ----
    if show_charts:
        try:
            import matplotlib.pyplot as plt

            n_scenarios = len(SCENARIOS)
            fig, axes = plt.subplots(n_scenarios, 3, figsize=(18, 6 * n_scenarios))
            if n_scenarios == 1:
                axes = [axes]
            fig.suptitle(f'BayesianV2 Ablation Study ({num_matches} matches each)', fontsize=14)

            for s_idx, scenario in enumerate(SCENARIOS):
                tag = scenario['tag']
                label = scenario['label']
                results = all_results[tag]
                baseline_wr = results['_baseline_wr']

                feature_names = [display for _, display, _ in ABLATIONS]
                vs_smart_wrs = [results[d]['vs_smart_wr'] for d in feature_names]
                deltas = [results[d]['vs_smart_wr'] - baseline_wr for d in feature_names]
                h2h_wrs = [results[d]['vs_full_wr'] or 0 for d in feature_names]

                # Panel 1: vs Smart win rates
                ax = axes[s_idx][0]
                bars = ax.bar(feature_names, vs_smart_wrs, color='#4c72b0', alpha=0.8)
                ax.axhline(y=baseline_wr, color='red', linestyle='--', label=f'Full V2: {baseline_wr:.0%}')
                ax.set_ylabel('Win Rate vs Smart')
                ax.set_title(f'{label}\nFeature Removal: Win Rate vs Smart')
                ax.set_ylim(0, 1.1)
                ax.legend(fontsize=8)
                ax.tick_params(axis='x', rotation=30, labelsize=7)
                for bar, wr in zip(bars, vs_smart_wrs):
                    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                            f'{wr:.0%}', ha='center', va='bottom', fontsize=8)

                # Panel 2: Win rate delta
                ax = axes[s_idx][1]
                colors = ['#c44e52' if d < 0 else '#55a868' for d in deltas]
                ax.bar(feature_names, deltas, color=colors, alpha=0.8)
                ax.axhline(y=0, color='black', linewidth=0.5)
                ax.set_ylabel('Win Rate Delta')
                ax.set_title(f'{label}\nImpact of Removing Feature')
                ax.tick_params(axis='x', rotation=30, labelsize=7)
                for i, d in enumerate(deltas):
                    ax.text(i, d + (0.01 if d >= 0 else -0.03), f'{d:+.0%}',
                            ha='center', va='bottom' if d >= 0 else 'top', fontsize=8)

                # Panel 3: Head-to-head vs full V2
                ax = axes[s_idx][2]
                bars = ax.bar(feature_names, h2h_wrs, color='#dd8452', alpha=0.8)
                ax.axhline(y=0.5, color='red', linestyle='--', label='Even (50%)')
                ax.set_ylabel('Win Rate (ablated agent)')
                ax.set_title(f'{label}\nHead-to-Head: Ablated vs Full V2')
                ax.set_ylim(0, 1.1)
                ax.legend(fontsize=8)
                ax.tick_params(axis='x', rotation=30, labelsize=7)
                for bar, wr in zip(bars, h2h_wrs):
                    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                            f'{wr:.0%}', ha='center', va='bottom', fontsize=8)

            fig.tight_layout()
            plt.savefig('ablation_results.png', dpi=150, bbox_inches='tight')
            print("Chart saved to ablation_results.png")
            plt.show()

        except ImportError:
            print("\nmatplotlib not installed — skipping charts.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='BayesianV2 ablation study')
    parser.add_argument('--matches', type=int, default=NUM_MATCHES,
                        help=f'Matches per configuration (default: {NUM_MATCHES})')
    parser.add_argument('--no-charts', action='store_true', help='Skip matplotlib charts')
    args = parser.parse_args()
    run_ablation(num_matches=args.matches, show_charts=not args.no_charts)
