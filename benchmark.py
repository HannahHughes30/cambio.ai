"""Benchmark BayesianAgent against SmartAgent and BaseAgent across various matchups."""

import argparse

from simulation import Tournament


MATCHUPS = [
    # --- 1v1 (2 players) ---
    {
        'name': 'Bayesian vs Smart (1v1)',
        'configs': [
            {'type': 'bayesian', 'name': 'Bayesian'},
            {'type': 'smart', 'name': 'Smart'},
        ],
    },
    {
        'name': 'Bayesian vs Base (1v1)',
        'configs': [
            {'type': 'bayesian', 'name': 'Bayesian'},
            {'type': 'base', 'name': 'Base'},
        ],
    },
    {
        'name': 'Smart vs Base (1v1 control)',
        'configs': [
            {'type': 'smart', 'name': 'Smart'},
            {'type': 'base', 'name': 'Base'},
        ],
    },
    {
        'name': 'BayesianV2 vs BayesianV1 (1v1)',
        'configs': [
            {'type': 'bayesian_v2', 'name': 'BayesV2'},
            {'type': 'bayesian', 'name': 'BayesV1'},
        ],
    },
    {
        'name': 'BayesianV2 vs Smart (1v1)',
        'configs': [
            {'type': 'bayesian_v2', 'name': 'BayesV2'},
            {'type': 'smart', 'name': 'Smart'},
        ],
    },
    # --- 3 players ---
    {
        'name': '2xSmart + Bayesian (3p)',
        'configs': [
            {'type': 'smart', 'name': 'Smart-1'},
            {'type': 'smart', 'name': 'Smart-2'},
            {'type': 'bayesian', 'name': 'Bayesian'},
        ],
    },
    {
        'name': 'Smart + Base + Bayesian (3p)',
        'configs': [
            {'type': 'smart', 'name': 'Smart'},
            {'type': 'base', 'name': 'Base'},
            {'type': 'bayesian', 'name': 'Bayesian'},
        ],
    },
    {
        'name': '2xSmart + BayesianV2 (3p)',
        'configs': [
            {'type': 'smart', 'name': 'Smart-1'},
            {'type': 'smart', 'name': 'Smart-2'},
            {'type': 'bayesian_v2', 'name': 'BayesV2'},
        ],
    },
    {
        'name': 'BayesV1 + BayesV2 + Smart (3p)',
        'configs': [
            {'type': 'bayesian', 'name': 'BayesV1'},
            {'type': 'bayesian_v2', 'name': 'BayesV2'},
            {'type': 'smart', 'name': 'Smart'},
        ],
    },
    # --- 6 players ---
    {
        'name': '5xSmart + Bayesian (6p)',
        'configs': [
            {'type': 'smart', 'name': 'Smart-1'},
            {'type': 'smart', 'name': 'Smart-2'},
            {'type': 'smart', 'name': 'Smart-3'},
            {'type': 'smart', 'name': 'Smart-4'},
            {'type': 'smart', 'name': 'Smart-5'},
            {'type': 'bayesian', 'name': 'Bayesian'},
        ],
    },
    {
        'name': '3xSmart + 2xBase + Bayesian (6p)',
        'configs': [
            {'type': 'smart', 'name': 'Smart-1'},
            {'type': 'smart', 'name': 'Smart-2'},
            {'type': 'smart', 'name': 'Smart-3'},
            {'type': 'base', 'name': 'Base-1'},
            {'type': 'base', 'name': 'Base-2'},
            {'type': 'bayesian', 'name': 'Bayesian'},
        ],
    },
    {
        'name': '2xSmart + 2xBase + 2xBayesian (6p)',
        'configs': [
            {'type': 'smart', 'name': 'Smart-1'},
            {'type': 'smart', 'name': 'Smart-2'},
            {'type': 'base', 'name': 'Base-1'},
            {'type': 'base', 'name': 'Base-2'},
            {'type': 'bayesian', 'name': 'Bayesian-1'},
            {'type': 'bayesian', 'name': 'Bayesian-2'},
        ],
    },
    {
        'name': '5xSmart + BayesianV2 (6p)',
        'configs': [
            {'type': 'smart', 'name': 'Smart-1'},
            {'type': 'smart', 'name': 'Smart-2'},
            {'type': 'smart', 'name': 'Smart-3'},
            {'type': 'smart', 'name': 'Smart-4'},
            {'type': 'smart', 'name': 'Smart-5'},
            {'type': 'bayesian_v2', 'name': 'BayesV2'},
        ],
    },
    {
        'name': '3xSmart + 2xBase + BayesianV2 (6p)',
        'configs': [
            {'type': 'smart', 'name': 'Smart-1'},
            {'type': 'smart', 'name': 'Smart-2'},
            {'type': 'smart', 'name': 'Smart-3'},
            {'type': 'base', 'name': 'Base-1'},
            {'type': 'base', 'name': 'Base-2'},
            {'type': 'bayesian_v2', 'name': 'BayesV2'},
        ],
    },
    # --- V1 vs V2 multi-player ---
    {
        'name': '2xBayesV2 + BayesV1 (3p)',
        'configs': [
            {'type': 'bayesian_v2', 'name': 'BayesV2-1'},
            {'type': 'bayesian_v2', 'name': 'BayesV2-2'},
            {'type': 'bayesian', 'name': 'BayesV1'},
        ],
    },
    {
        'name': '5xBayesV2 + BayesV1 (6p)',
        'configs': [
            {'type': 'bayesian_v2', 'name': 'BayesV2-1'},
            {'type': 'bayesian_v2', 'name': 'BayesV2-2'},
            {'type': 'bayesian_v2', 'name': 'BayesV2-3'},
            {'type': 'bayesian_v2', 'name': 'BayesV2-4'},
            {'type': 'bayesian_v2', 'name': 'BayesV2-5'},
            {'type': 'bayesian', 'name': 'BayesV1'},
        ],
    },
    {
        'name': '5xBayesV1 + BayesV2 (6p)',
        'configs': [
            {'type': 'bayesian', 'name': 'BayesV1-1'},
            {'type': 'bayesian', 'name': 'BayesV1-2'},
            {'type': 'bayesian', 'name': 'BayesV1-3'},
            {'type': 'bayesian', 'name': 'BayesV1-4'},
            {'type': 'bayesian', 'name': 'BayesV1-5'},
            {'type': 'bayesian_v2', 'name': 'BayesV2'},
        ],
    },
]

NUM_MATCHES = 100
POINT_LIMIT = 100


def run_benchmarks(show_charts=True):
    results = []

    for matchup in MATCHUPS:
        name = matchup['name']
        configs = matchup['configs']
        print(f"\nRunning: {name} ({NUM_MATCHES} matches) ...")

        tourney = Tournament(configs, num_matches=NUM_MATCHES, point_limit=POINT_LIMIT)
        result = tourney.play()
        summary = result['summary']
        sample_match = result['match_results'][0]
        results.append((name, configs, summary, result, sample_match))

        # Progress: show win rates inline
        rates = ', '.join(
            f"{n}: {summary['win_rates'].get(n, 0):.0%}"
            for n in [c['name'] for c in configs]
        )
        print(f"  -> {rates}")

    # --- Summary table ---
    print("\n" + "=" * 80)
    print("BENCHMARK RESULTS")
    print("=" * 80)

    for name, configs, summary, full_result, _sample in results:
        print(f"\n--- {name} ---")
        print(f"  {'Agent':<15} {'Wins':>5} {'Win%':>6} {'Avg Score':>10} {'Stdev':>8}  {'Cambio':>6} {'CallerWin%':>10}")
        print(f"  {'-'*15} {'-'*5} {'-'*6} {'-'*10} {'-'*8}  {'-'*6} {'-'*10}")

        # Compute cambio caller stats per agent across all rounds
        cambio_calls = {}   # {agent_name: total times they called cambio}
        cambio_wins = {}    # {agent_name: times they called AND won the round}
        for match in full_result['match_results']:
            for rnd in match['round_results']:
                caller = rnd.get('cambio_caller')
                winner = rnd.get('winner')
                if caller:
                    cambio_calls[caller] = cambio_calls.get(caller, 0) + 1
                    if caller == winner:
                        cambio_wins[caller] = cambio_wins.get(caller, 0) + 1

        for cfg in configs:
            n = cfg['name']
            wins = summary['win_counts'].get(n, 0)
            rate = summary['win_rates'].get(n, 0)
            dist = summary['score_distributions'][n]
            calls = cambio_calls.get(n, 0)
            cwins = cambio_wins.get(n, 0)
            cwin_rate = f"{cwins/calls:.0%}" if calls > 0 else "n/a"
            print(f"  {n:<15} {wins:>5} {rate:>5.0%} {dist['mean']:>10.1f} {dist['stdev']:>8.1f}  {calls:>6} {cwin_rate:>10}")
        print(f"  Avg rounds/match: {summary['avg_rounds']:.1f}")

    print("\n" + "=" * 80)
    print("Done.")

    # --- Charts ---
    if show_charts:
        try:
            import matplotlib.pyplot as plt

            matchup_names = [name for name, *_ in results]
            n_matchups = len(matchup_names)

            # --- Fig 1: Win rates per agent across all matchups ---
            n_cols = 4
            n_rows = (n_matchups + n_cols - 1) // n_cols
            fig1, axes1 = plt.subplots(n_rows, n_cols, figsize=(18, 4 * n_rows))
            fig1.suptitle(f'Win Rates by Matchup (n={NUM_MATCHES} matches, first to {POINT_LIMIT}pts loses)', fontsize=16)
            colors = ['#4c72b0', '#dd8452', '#55a868', '#c44e52', '#8172b3', '#937860']
            axes1 = axes1.flatten() if hasattr(axes1, 'flatten') else [axes1]
            for idx, (name, configs, summary, *_) in enumerate(results):
                ax = axes1[idx]
                names = [c['name'] for c in configs]
                rates = [summary['win_rates'].get(n, 0) for n in names]
                bars = ax.bar(names, rates, color=colors[:len(names)])
                ax.set_ylim(0, 1.1)
                ax.set_title(name, fontsize=9)
                ax.tick_params(axis='x', labelsize=7, rotation=45)
                for bar, rate in zip(bars, rates):
                    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                            f'{rate:.0%}', ha='center', va='bottom', fontsize=7)
            fig1.tight_layout()

            # --- Fig 2: Score distributions (box plots) across all matchups ---
            fig2, axes2 = plt.subplots(n_rows, n_cols, figsize=(18, 4 * n_rows))
            fig2.suptitle('Score Distributions by Matchup', fontsize=16)
            axes2 = axes2.flatten() if hasattr(axes2, 'flatten') else [axes2]
            for idx, (name, configs, summary, *_) in enumerate(results):
                ax = axes2[idx]
                names = [c['name'] for c in configs]
                data = [summary['score_distributions'][n]['values'] for n in names]
                ax.boxplot(data, labels=names)
                ax.set_title(name, fontsize=9)
                ax.tick_params(axis='x', labelsize=7, rotation=45)
                ax.set_ylabel('Final Score', fontsize=8)
            fig2.tight_layout()

            # --- Fig 3: Avg rounds per match + sample match progression ---
            fig3, axes3 = plt.subplots(1, 2, figsize=(14, 5))
            fig3.suptitle('Match Length & Sample Game', fontsize=16)

            # Left: avg rounds bar chart
            ax = axes3[0]
            avg_rounds = [s for _, _, s, *_ in results]
            avg_vals = [s['avg_rounds'] for s in avg_rounds]
            short_names = [n.split('(')[0].strip() for n in matchup_names]
            ax.barh(short_names, avg_vals, color='#4c72b0')
            ax.set_xlabel('Avg Rounds per Match')
            ax.set_title('Match Length')
            for i, v in enumerate(avg_vals):
                ax.text(v + 0.1, i, f'{v:.1f}', va='center', fontsize=8)

            # Right: sample match score progression (first matchup)
            ax = axes3[1]
            sample = results[0][4]  # sample_match from first matchup
            names = list(sample['round_results'][0]['scores'].keys())
            running = {n: 0 for n in names}
            cumulative = {n: [] for n in names}
            for rnd in sample['round_results']:
                for n in names:
                    running[n] += rnd['scores'][n]
                    cumulative[n].append(running[n])
            for n in names:
                ax.plot(range(1, len(cumulative[n]) + 1), cumulative[n], marker='o', label=n)
            ax.set_xlabel('Round')
            ax.set_ylabel('Cumulative Score')
            ax.set_title(f'Sample Match: {matchup_names[0]}')
            ax.legend()
            ax.grid(True, alpha=0.3)

            fig3.tight_layout()
            plt.show()
        except ImportError:
            print("\nmatplotlib not installed — skipping charts.")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Benchmark Cambio agents across matchups')
    parser.add_argument('--no-charts', action='store_true', help='Skip matplotlib charts')
    args = parser.parse_args()
    run_benchmarks(show_charts=not args.no_charts)
