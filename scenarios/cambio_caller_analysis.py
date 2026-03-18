"""Analyze cambio caller win rates across agent configurations and knowledge gap settings."""

import argparse
from collections import defaultdict

from simulation import Tournament

# --- Configurations to test ---
# Each entry: (label, agent_configs)
# We test the default (gap=1, ev_dom=8) vs strict (gap=0, ev_dom=8)

SCENARIOS = [
    # 1v1
    {
        'name': 'V2 vs Smart (1v1)',
        'configs': {
            'default': [
                {'type': 'bayesian_v2', 'name': 'BayesV2'},
                {'type': 'smart', 'name': 'Smart'},
            ],
            'strict': [
                {'type': 'bayesian_v2', 'name': 'BayesV2', 'kwargs': {'cambio_knowledge_gap': 0}},
                {'type': 'smart', 'name': 'Smart'},
            ],
        },
    },
    {
        'name': 'V2 vs V1 (1v1)',
        'configs': {
            'default': [
                {'type': 'bayesian_v2', 'name': 'BayesV2'},
                {'type': 'bayesian', 'name': 'BayesV1'},
            ],
            'strict': [
                {'type': 'bayesian_v2', 'name': 'BayesV2', 'kwargs': {'cambio_knowledge_gap': 0}},
                {'type': 'bayesian', 'name': 'BayesV1'},
            ],
        },
    },
    # 3p
    {
        'name': 'V1 + V2 + Smart (3p)',
        'configs': {
            'default': [
                {'type': 'bayesian', 'name': 'BayesV1'},
                {'type': 'bayesian_v2', 'name': 'BayesV2'},
                {'type': 'smart', 'name': 'Smart'},
            ],
            'strict': [
                {'type': 'bayesian', 'name': 'BayesV1'},
                {'type': 'bayesian_v2', 'name': 'BayesV2', 'kwargs': {'cambio_knowledge_gap': 0}},
                {'type': 'smart', 'name': 'Smart'},
            ],
        },
    },
    # 6p
    {
        'name': '5xSmart + V2 (6p)',
        'configs': {
            'default': [
                {'type': 'smart', 'name': 'Smart-1'},
                {'type': 'smart', 'name': 'Smart-2'},
                {'type': 'smart', 'name': 'Smart-3'},
                {'type': 'smart', 'name': 'Smart-4'},
                {'type': 'smart', 'name': 'Smart-5'},
                {'type': 'bayesian_v2', 'name': 'BayesV2'},
            ],
            'strict': [
                {'type': 'smart', 'name': 'Smart-1'},
                {'type': 'smart', 'name': 'Smart-2'},
                {'type': 'smart', 'name': 'Smart-3'},
                {'type': 'smart', 'name': 'Smart-4'},
                {'type': 'smart', 'name': 'Smart-5'},
                {'type': 'bayesian_v2', 'name': 'BayesV2', 'kwargs': {'cambio_knowledge_gap': 0}},
            ],
        },
    },
    {
        'name': '5xV1 + V2 (6p)',
        'configs': {
            'default': [
                {'type': 'bayesian', 'name': 'BayesV1-1'},
                {'type': 'bayesian', 'name': 'BayesV1-2'},
                {'type': 'bayesian', 'name': 'BayesV1-3'},
                {'type': 'bayesian', 'name': 'BayesV1-4'},
                {'type': 'bayesian', 'name': 'BayesV1-5'},
                {'type': 'bayesian_v2', 'name': 'BayesV2'},
            ],
            'strict': [
                {'type': 'bayesian', 'name': 'BayesV1-1'},
                {'type': 'bayesian', 'name': 'BayesV1-2'},
                {'type': 'bayesian', 'name': 'BayesV1-3'},
                {'type': 'bayesian', 'name': 'BayesV1-4'},
                {'type': 'bayesian', 'name': 'BayesV1-5'},
                {'type': 'bayesian_v2', 'name': 'BayesV2', 'kwargs': {'cambio_knowledge_gap': 0}},
            ],
        },
    },
]

NUM_MATCHES = 100
POINT_LIMIT = 100


def compute_cambio_stats(full_result, agent_name):
    """Compute cambio caller stats for a specific agent across all rounds."""
    calls = 0
    wins = 0
    for match in full_result['match_results']:
        for rnd in match['round_results']:
            caller = rnd.get('cambio_caller')
            winner = rnd.get('winner')
            if caller == agent_name:
                calls += 1
                if caller == winner:
                    wins += 1
    return calls, wins


def run_analysis(show_charts=True):
    all_results = []  # (scenario_name, variant, agent_name, win_rate, calls, caller_win_rate, avg_rounds)

    for scenario in SCENARIOS:
        name = scenario['name']
        print(f"\n{'='*60}")
        print(f"  {name}")
        print(f"{'='*60}")

        for variant in ['default', 'strict']:
            configs = scenario['configs'][variant]
            label = f"gap=1" if variant == 'default' else "gap=0"
            print(f"\n  [{label}] Running {NUM_MATCHES} matches ...")

            tourney = Tournament(configs, num_matches=NUM_MATCHES, point_limit=POINT_LIMIT)
            result = tourney.play()
            summary = result['summary']

            # Find the BayesV2 agent
            v2_name = None
            for cfg in configs:
                if 'bayesian_v2' in cfg['type']:
                    v2_name = cfg['name']
                    break

            if v2_name:
                win_rate = summary['win_rates'].get(v2_name, 0)
                calls, wins = compute_cambio_stats(result, v2_name)
                caller_wr = wins / calls if calls > 0 else 0
                avg_rounds = summary['avg_rounds']

                all_results.append((name, variant, v2_name, win_rate, calls, caller_wr, avg_rounds))
                print(f"    V2 win rate: {win_rate:.0%}")
                print(f"    V2 cambio calls: {calls}, caller win%: {caller_wr:.0%}")

    # --- Summary table ---
    print("\n" + "=" * 95)
    print("CAMBIO CALLER ANALYSIS — V2 with gap=1 (default) vs gap=0 (strict)")
    print("=" * 95)
    print(f"  {'Scenario':<25} {'Variant':<10} {'Win%':>6} {'Cambio Calls':>13} {'Caller Win%':>12} {'Avg Rounds':>11}")
    print(f"  {'-'*25} {'-'*10} {'-'*6} {'-'*13} {'-'*12} {'-'*11}")

    for name, variant, agent, wr, calls, cwr, avg_rnd in all_results:
        label = "gap=1" if variant == 'default' else "gap=0"
        print(f"  {name:<25} {label:<10} {wr:>5.0%} {calls:>13} {cwr:>11.0%} {avg_rnd:>11.1f}")

    print()

    # --- Charts ---
    if show_charts:
        try:
            import matplotlib.pyplot as plt

            scenario_names = list(dict.fromkeys(r[0] for r in all_results))
            n_scenarios = len(scenario_names)

            fig, axes = plt.subplots(1, 3, figsize=(18, 6))
            fig.suptitle('Cambio Caller Analysis: gap=1 (default) vs gap=0 (all cards known)', fontsize=14)

            x = range(n_scenarios)
            width = 0.35

            # Extract data per variant
            def get_vals(metric_idx, variant):
                return [next(r[metric_idx] for r in all_results if r[0] == s and r[1] == variant)
                        for s in scenario_names]

            # Chart 1: Win Rate
            ax = axes[0]
            default_wr = get_vals(3, 'default')
            strict_wr = get_vals(3, 'strict')
            bars1 = ax.bar([i - width/2 for i in x], default_wr, width, label='gap=1 (default)', color='#4c72b0')
            bars2 = ax.bar([i + width/2 for i in x], strict_wr, width, label='gap=0 (strict)', color='#dd8452')
            ax.set_ylabel('V2 Win Rate')
            ax.set_title('Match Win Rate')
            ax.set_xticks(list(x))
            ax.set_xticklabels([s.replace(' ', '\n') for s in scenario_names], fontsize=7)
            ax.set_ylim(0, 1.1)
            ax.legend(fontsize=8)
            for bar in bars1:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                        f'{bar.get_height():.0%}', ha='center', va='bottom', fontsize=7)
            for bar in bars2:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                        f'{bar.get_height():.0%}', ha='center', va='bottom', fontsize=7)

            # Chart 2: Caller Win Rate
            ax = axes[1]
            default_cwr = get_vals(5, 'default')
            strict_cwr = get_vals(5, 'strict')
            bars1 = ax.bar([i - width/2 for i in x], default_cwr, width, label='gap=1 (default)', color='#4c72b0')
            bars2 = ax.bar([i + width/2 for i in x], strict_cwr, width, label='gap=0 (strict)', color='#dd8452')
            ax.set_ylabel('Caller Win Rate')
            ax.set_title('Cambio Caller Win Rate (how often caller wins the round)')
            ax.set_xticks(list(x))
            ax.set_xticklabels([s.replace(' ', '\n') for s in scenario_names], fontsize=7)
            ax.set_ylim(0, 1.1)
            ax.axhline(y=0.5, color='red', linestyle='--', alpha=0.5, label='50% line')
            ax.legend(fontsize=8)
            for bar in bars1:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                        f'{bar.get_height():.0%}', ha='center', va='bottom', fontsize=7)
            for bar in bars2:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                        f'{bar.get_height():.0%}', ha='center', va='bottom', fontsize=7)

            # Chart 3: Cambio Call Count
            ax = axes[2]
            default_calls = get_vals(4, 'default')
            strict_calls = get_vals(4, 'strict')
            bars1 = ax.bar([i - width/2 for i in x], default_calls, width, label='gap=1 (default)', color='#4c72b0')
            bars2 = ax.bar([i + width/2 for i in x], strict_calls, width, label='gap=0 (strict)', color='#dd8452')
            ax.set_ylabel('Total Cambio Calls')
            ax.set_title('Cambio Call Frequency (across all rounds)')
            ax.set_xticks(list(x))
            ax.set_xticklabels([s.replace(' ', '\n') for s in scenario_names], fontsize=7)
            ax.legend(fontsize=8)
            for bar in bars1:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                        f'{int(bar.get_height())}', ha='center', va='bottom', fontsize=7)
            for bar in bars2:
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                        f'{int(bar.get_height())}', ha='center', va='bottom', fontsize=7)

            fig.tight_layout()
            plt.show()

        except ImportError:
            print("\nmatplotlib not installed — skipping charts.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Cambio caller win rate analysis')
    parser.add_argument('--no-charts', action='store_true', help='Skip matplotlib charts')
    args = parser.parse_args()
    run_analysis(show_charts=not args.no_charts)
