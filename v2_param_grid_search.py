"""Grid search over all BayesianV2 tunable parameters.

Searches all 11 parameters independently (one-at-a-time sweep),
tested in both 1v1 and 3-player settings. Parallelized across CPU cores.
"""

import argparse
import os
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed

from simulation import Tournament

POINT_LIMIT = 100

# Parameter sweeps: (param_name, display_name, values, default)
PARAM_SWEEPS = [
    # --- Original 4 ---
    ('stick_ev_threshold', 'Stick EV Threshold',
     [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0], 2.5),
    ('cambio_aggressive_threshold', 'Aggressive Cambio Threshold',
     [2, 3, 4, 5, 6, 7, 8, 9, 10], 8),
    ('cambio_margin', 'Cambio Margin',
     [1, 2, 3, 4, 5, 6], 2),
    ('cambio_knowledge_gap', 'Knowledge Gap',
     [0, 1, 2, 3], 1),
    # --- New 7 ---
    ('disruption_bonus_max', 'Disruption Bonus Max',
     [0, 0.5, 1, 2, 3, 4, 5, 6], 3),
    ('good_hand_threshold', 'Good Hand Threshold',
     [2, 3, 4, 5, 6, 7, 8], 5),
    ('cambio_threshold', 'Cambio Threshold',
     [6, 7, 8, 9, 10, 12, 14], 10),
    ('ev_dominance_margin', 'EV Dominance Margin',
     [4, 5, 6, 7, 8, 10, 12], 8),
    ('info_bonus_max_value', 'Info Bonus Max Value',
     [1, 2, 3, 4, 5], 3),
    ('small_deck_threshold', 'Small Deck Threshold',
     [3, 4, 5, 6, 7, 8, 10], 5),
    ('jq_swap_improvement', 'J/Q Swap Improvement',
     [0, 1, 2, 3, 4, 5], 2),
]

# Scenario configs as serializable dicts (no lambdas — needed for multiprocessing)
SCENARIO_TAGS = ['1v1', '3p', '4p']
SCENARIO_LABELS = {
    '1v1': 'V2 vs Smart (1v1)',
    '3p': 'V2 + Smart + V1 (3p)',
    '4p': 'V2 + Smart + V1 + Base (4p)',
}


def make_configs(tag, kwargs):
    """Build tournament configs for a scenario tag.

    For multiplayer scenarios, uses a mix of opponent types (Smart, V1, Base)
    to avoid overfitting parameters to a single opponent type.
    """
    if tag == '1v1':
        return [
            {'type': 'bayesian_v2', 'name': 'BayesV2', 'kwargs': kwargs},
            {'type': 'smart', 'name': 'Smart'},
        ]
    elif tag == '3p':
        return [
            {'type': 'bayesian_v2', 'name': 'BayesV2', 'kwargs': kwargs},
            {'type': 'smart', 'name': 'Smart'},
            {'type': 'bayesian', 'name': 'BayesV1'},
        ]
    else:  # 4p
        return [
            {'type': 'bayesian_v2', 'name': 'BayesV2', 'kwargs': kwargs},
            {'type': 'smart', 'name': 'Smart'},
            {'type': 'bayesian', 'name': 'BayesV1'},
            {'type': 'base', 'name': 'Base'},
        ]


def run_single(param_name, val, tag, num_matches):
    """Run one tournament. Called in worker process."""
    kwargs = {param_name: val}
    configs = make_configs(tag, kwargs)
    tourney = Tournament(configs, num_matches=num_matches, point_limit=POINT_LIMIT)
    result = tourney.play()
    summary = result['summary']
    win_rate = summary['win_rates'].get('BayesV2', 0)
    avg_score = summary['score_distributions']['BayesV2']['mean']
    return (param_name, val, tag, win_rate, avg_score)


def run_grid_search(num_matches=100, show_charts=True, max_workers=None):
    if max_workers is None:
        max_workers = min(os.cpu_count() or 4, 8)

    # Build all jobs
    jobs = []
    for param_name, _, values, _ in PARAM_SWEEPS:
        for tag in SCENARIO_TAGS:
            for val in values:
                jobs.append((param_name, val, tag, num_matches))

    total = len(jobs)
    print(f"Grid search: {len(PARAM_SWEEPS)} params × 2 scenarios = {total} tournament runs")
    print(f"Using {max_workers} workers, {num_matches} matches each\n")

    # Run in parallel
    results = defaultdict(lambda: defaultdict(list))
    completed = 0

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_single, *job): job for job in jobs}
        for future in as_completed(futures):
            param_name, val, tag, win_rate, avg_score = future.result()
            results[param_name][tag].append((val, win_rate, avg_score))
            completed += 1
            if completed % 10 == 0 or completed == total:
                print(f"  [{completed}/{total}] completed", flush=True)

    # Sort results by value for display
    for param_name in results:
        for tag in results[param_name]:
            results[param_name][tag].sort(key=lambda r: r[0])

    # ---- Summary tables ----
    print(f"\n{'=' * 90}")
    print("PARAMETER GRID SEARCH RESULTS")
    print(f"{'=' * 90}")

    for param_name, display_name, values, default in PARAM_SWEEPS:
        print(f"\n  {display_name} ({param_name})  [default={default}]")

        for tag in SCENARIO_TAGS:
            label = SCENARIO_LABELS[tag]
            rows = results[param_name][tag]

            print(f"\n    {label}")
            print(f"    {'Value':>8} {'Win%':>7} {'Avg Score':>10}")
            print(f"    {'-'*8} {'-'*7} {'-'*10}")

            best = max(rows, key=lambda r: r[1])
            for val, wr, avg_sc in rows:
                marker = ''
                if val == best[0] and val == default:
                    marker = ' ← best=default'
                elif val == best[0]:
                    marker = ' ← best'
                elif val == default:
                    marker = ' ← default'
                print(f"    {val:>8} {wr:>6.0%} {avg_sc:>10.1f}{marker}")

    # ---- Optimal summary ----
    print(f"\n{'=' * 70}")
    print("OPTIMAL PARAMETERS")
    print(f"{'=' * 70}")
    for param_name, display_name, values, default in PARAM_SWEEPS:
        print(f"\n  {display_name}:")
        for tag in SCENARIO_TAGS:
            rows = results[param_name][tag]
            best = max(rows, key=lambda r: r[1])
            default_row = [r for r in rows if r[0] == default][0]
            delta = best[1] - default_row[1]
            print(f"    {tag}: best={best[0]} ({best[1]:.0%})  default={default} ({default_row[1]:.0%})  Δ={delta:+.0%}")

    print()

    # ---- Charts ----
    if show_charts:
        try:
            import matplotlib.pyplot as plt

            n_params = len(PARAM_SWEEPS)
            fig, axes = plt.subplots(n_params, 2, figsize=(14, 4 * n_params))
            fig.suptitle(f'BayesianV2 Parameter Grid Search ({num_matches} matches each)', fontsize=14)

            for p_idx, (param_name, display_name, values, default) in enumerate(PARAM_SWEEPS):
                for s_idx, tag in enumerate(SCENARIO_TAGS):
                    label = SCENARIO_LABELS[tag]
                    rows = results[param_name][tag]

                    ax = axes[p_idx][s_idx]
                    x_vals = [r[0] for r in rows]
                    win_rates = [r[1] for r in rows]

                    ax.plot(x_vals, win_rates, 'o-', color='#4c72b0', linewidth=2)
                    ax.axvline(x=default, color='red', linestyle='--', alpha=0.5, label=f'Default={default}')

                    best = max(rows, key=lambda r: r[1])
                    ax.axvline(x=best[0], color='green', linestyle='--', alpha=0.5, label=f'Best={best[0]}')

                    ax.set_xlabel(param_name)
                    ax.set_ylabel('Win Rate')
                    ax.set_title(f'{display_name} — {label}', fontsize=10)
                    ax.set_ylim(0, 1.05)
                    ax.legend(fontsize=8)
                    ax.grid(True, alpha=0.3)

            fig.tight_layout()
            plt.savefig('v2_param_grid_search.png', dpi=150, bbox_inches='tight')
            print("Chart saved to v2_param_grid_search.png")
            plt.show()

        except ImportError:
            print("\nmatplotlib not installed — skipping charts.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Grid search over BayesianV2 parameters')
    parser.add_argument('--matches', type=int, default=100,
                        help='Matches per configuration (default: 100)')
    parser.add_argument('--workers', type=int, default=None,
                        help='Max parallel workers (default: num CPUs, max 8)')
    parser.add_argument('--no-charts', action='store_true', help='Skip matplotlib charts')
    args = parser.parse_args()
    run_grid_search(num_matches=args.matches, show_charts=not args.no_charts,
                    max_workers=args.workers)
