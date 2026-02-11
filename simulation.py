"""Simulation system for running Cambio matches and tournaments between agents."""

import argparse
import statistics
from collections import defaultdict

from game import CambioGame
from agents import BaseAgent, SmartAgent

# ---------------------------------------------------------------------------
# Agent Registry
# ---------------------------------------------------------------------------

AGENT_REGISTRY = {
    'base': BaseAgent,
    'smart': SmartAgent,
}


def create_agent(agent_type, name, **kwargs):
    """Factory: create an agent by type string."""
    cls = AGENT_REGISTRY[agent_type]
    return cls(name=name, **kwargs)


# ---------------------------------------------------------------------------
# Match — first to point_limit loses
# ---------------------------------------------------------------------------

class Match:
    """Plays rounds until one player reaches *point_limit* (that player LOSES)."""

    def __init__(self, agent_configs, point_limit=100, verbose=False):
        """
        agent_configs: list of dicts, e.g.
            [{'type': 'base', 'name': 'Base'}, {'type': 'smart', 'name': 'Smart'}]
        """
        self.agent_configs = agent_configs
        self.point_limit = point_limit
        self.verbose = verbose

    def play(self):
        cumulative_scores = {cfg['name']: 0 for cfg in self.agent_configs}
        round_results = []
        rounds_played = 0

        while True:
            # Fresh agents each round
            agents = [
                create_agent(cfg['type'], cfg['name'], **cfg.get('kwargs', {}))
                for cfg in self.agent_configs
            ]

            game = CambioGame(agents)
            game.deal()
            result = game.play(verbose=self.verbose)

            for name, score in result['scores'].items():
                cumulative_scores[name] += score

            round_results.append(result)
            rounds_played += 1

            if self.verbose:
                print(f"  [Round {rounds_played}] Scores: {cumulative_scores}")

            # Check if anyone has reached the point limit (they lose)
            losers = [n for n, s in cumulative_scores.items() if s >= self.point_limit]
            if losers:
                loser = max(losers, key=lambda n: cumulative_scores[n])
                winner = min(cumulative_scores, key=cumulative_scores.get)
                return {
                    'winner': winner,
                    'loser': loser,
                    'final_scores': dict(cumulative_scores),
                    'rounds_played': rounds_played,
                    'round_results': round_results,
                }


# ---------------------------------------------------------------------------
# Tournament — run M matches
# ---------------------------------------------------------------------------

class Tournament:
    """Runs *num_matches* Match instances and aggregates stats."""

    def __init__(self, agent_configs, num_matches=10, point_limit=100, verbose=False):
        self.agent_configs = agent_configs
        self.num_matches = num_matches
        self.point_limit = point_limit
        self.verbose = verbose

    def play(self):
        match_results = []
        win_counts = defaultdict(int)
        final_scores_by_name = defaultdict(list)
        rounds_list = []

        for i in range(self.num_matches):
            if self.verbose:
                print(f"\n{'='*40} Match {i+1}/{self.num_matches} {'='*40}")

            match = Match(
                self.agent_configs,
                point_limit=self.point_limit,
                verbose=self.verbose,
            )
            result = match.play()
            match_results.append(result)

            win_counts[result['winner']] += 1
            rounds_list.append(result['rounds_played'])
            for name, score in result['final_scores'].items():
                final_scores_by_name[name].append(score)

        names = [cfg['name'] for cfg in self.agent_configs]
        win_rates = {n: win_counts[n] / self.num_matches for n in names}

        summary = {
            'win_counts': dict(win_counts),
            'win_rates': win_rates,
            'avg_rounds': statistics.mean(rounds_list),
            'median_rounds': statistics.median(rounds_list),
            'score_distributions': {
                n: {
                    'mean': statistics.mean(final_scores_by_name[n]),
                    'median': statistics.median(final_scores_by_name[n]),
                    'stdev': statistics.stdev(final_scores_by_name[n]) if len(final_scores_by_name[n]) > 1 else 0,
                    'min': min(final_scores_by_name[n]),
                    'max': max(final_scores_by_name[n]),
                    'values': final_scores_by_name[n],
                }
                for n in names
            },
            'rounds_per_match': rounds_list,
        }

        return {
            'match_results': match_results,
            'summary': summary,
        }


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------

def _import_matplotlib():
    import matplotlib.pyplot as plt
    return plt


def plot_score_progression(match_result, title=None):
    """Cumulative score line chart for a single match."""
    plt = _import_matplotlib()
    names = list(match_result['round_results'][0]['scores'].keys())
    cumulative = {n: [] for n in names}
    running = {n: 0 for n in names}

    for rnd in match_result['round_results']:
        for n in names:
            running[n] += rnd['scores'][n]
            cumulative[n].append(running[n])

    fig, ax = plt.subplots()
    for n in names:
        ax.plot(range(1, len(cumulative[n]) + 1), cumulative[n], marker='o', label=n)
    ax.set_xlabel('Round')
    ax.set_ylabel('Cumulative Score')
    ax.set_title(title or 'Score Progression')
    ax.legend()
    ax.grid(True, alpha=0.3)
    return fig


def plot_win_rates(tournament_result):
    """Bar chart of win rates."""
    plt = _import_matplotlib()
    summary = tournament_result['summary']
    names = list(summary['win_rates'].keys())
    rates = [summary['win_rates'][n] for n in names]

    fig, ax = plt.subplots()
    bars = ax.bar(names, rates, color=['#4c72b0', '#dd8452', '#55a868', '#c44e52'][:len(names)])
    ax.set_ylabel('Win Rate')
    ax.set_title('Win Rates')
    ax.set_ylim(0, 1)
    for bar, rate in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                f'{rate:.0%}', ha='center', va='bottom')
    return fig


def plot_score_distributions(tournament_result):
    """Histograms + box plots of final scores."""
    plt = _import_matplotlib()
    summary = tournament_result['summary']
    names = list(summary['score_distributions'].keys())

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Histograms
    for n in names:
        axes[0].hist(summary['score_distributions'][n]['values'],
                     alpha=0.6, label=n, bins=15)
    axes[0].set_xlabel('Final Score')
    axes[0].set_ylabel('Frequency')
    axes[0].set_title('Final Score Distribution')
    axes[0].legend()

    # Box plots
    data = [summary['score_distributions'][n]['values'] for n in names]
    axes[1].boxplot(data, labels=names)
    axes[1].set_ylabel('Final Score')
    axes[1].set_title('Final Score Box Plot')

    fig.tight_layout()
    return fig


def plot_rounds_per_match(tournament_result):
    """Match length distribution."""
    plt = _import_matplotlib()
    rounds = tournament_result['summary']['rounds_per_match']

    fig, ax = plt.subplots()
    ax.hist(rounds, bins=max(5, len(set(rounds))), edgecolor='black', alpha=0.7)
    ax.set_xlabel('Rounds per Match')
    ax.set_ylabel('Frequency')
    ax.set_title('Match Length Distribution')
    ax.axvline(statistics.mean(rounds), color='red', linestyle='--',
               label=f'Mean: {statistics.mean(rounds):.1f}')
    ax.legend()
    return fig


def plot_round_score_deltas(match_result):
    """Per-round score earned for each player (useful for RL reward shaping)."""
    plt = _import_matplotlib()
    names = list(match_result['round_results'][0]['scores'].keys())

    fig, ax = plt.subplots()
    x = range(1, len(match_result['round_results']) + 1)
    for n in names:
        deltas = [rnd['scores'][n] for rnd in match_result['round_results']]
        ax.bar([xi + 0.2 * names.index(n) for xi in x], deltas,
               width=0.2, label=n, alpha=0.8)
    ax.set_xlabel('Round')
    ax.set_ylabel('Score Earned')
    ax.set_title('Per-Round Score Deltas')
    ax.legend()
    return fig


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description='Cambio Agent Simulation')
    parser.add_argument('--matches', type=int, default=20, help='Number of matches in tournament')
    parser.add_argument('--point-limit', type=int, default=100, help='Point limit per match')
    parser.add_argument('--verbose', action='store_true', help='Print every turn')
    parser.add_argument('--no-charts', action='store_true', help='Skip matplotlib charts')
    args = parser.parse_args()

    agent_configs = [
        {'type': 'base', 'name': 'BaseAgent'},
        {'type': 'smart', 'name': 'SmartAgent'},
    ]

    # --- Single demo match ---
    print("=" * 60)
    print("DEMO MATCH  (first to", args.point_limit, "loses)")
    print("=" * 60)
    demo = Match(agent_configs, point_limit=args.point_limit, verbose=args.verbose)
    demo_result = demo.play()
    print(f"\nWinner: {demo_result['winner']}")
    print(f"Final scores: {demo_result['final_scores']}")
    print(f"Rounds played: {demo_result['rounds_played']}")

    # --- Tournament ---
    print("\n" + "=" * 60)
    print(f"TOURNAMENT  ({args.matches} matches)")
    print("=" * 60)
    tourney = Tournament(
        agent_configs,
        num_matches=args.matches,
        point_limit=args.point_limit,
        verbose=args.verbose,
    )
    tourney_result = tourney.play()
    s = tourney_result['summary']

    print(f"\nWin counts: {s['win_counts']}")
    print(f"Win rates:  {s['win_rates']}")
    print(f"Avg rounds/match: {s['avg_rounds']:.1f}")
    for name, dist in s['score_distributions'].items():
        print(f"  {name}: mean={dist['mean']:.1f}  median={dist['median']:.1f}  "
              f"stdev={dist['stdev']:.1f}  range=[{dist['min']}, {dist['max']}]")

    # --- Charts ---
    if not args.no_charts:
        try:
            plt = _import_matplotlib()
            plot_score_progression(demo_result, title='Demo Match Score Progression')
            plot_win_rates(tourney_result)
            plot_score_distributions(tourney_result)
            plot_rounds_per_match(tourney_result)
            plot_round_score_deltas(demo_result)
            plt.show()
        except ImportError:
            print("\nmatplotlib not installed — skipping charts.")


if __name__ == '__main__':
    main()
