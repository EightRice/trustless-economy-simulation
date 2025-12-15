#!/usr/bin/env python3
"""
Main entry point for the Trustless Economy simulation.

Usage:
    python -m simulation                    # Run quick analysis
    python -m simulation --full             # Run full analysis
    python -m simulation --compare          # Compare all scenarios
    python -m simulation --sweep fee        # Parameter sweep
    python -m simulation --help             # Show help
"""
import argparse
import sys
import json
from pathlib import Path
from datetime import datetime

from .core.parameters import SimulationConfig, EconomyParameters, SCENARIOS
from .runner import (
    MonteCarloRunner,
    run_efficacy_analysis,
    compare_economic_parameters,
)
from .analysis.visualization import TextReporter, DataExporter, generate_summary_table
from .analysis.statistics import SimulationAnalysis


def print_header():
    """Print simulation header."""
    print("""
======================================================================
     TRUSTLESS ECONOMY GAME-THEORY SIMULATION
     Statistical Analysis of Incentive Mechanisms
======================================================================
    """)


def run_quick_demo():
    """Run a quick demonstration with minimal resources."""
    print("\n> Running Quick Demo (10 runs, 500 ticks)...")
    print("  This provides a fast overview, not statistically significant results.\n")

    config = SimulationConfig(
        num_ticks=500,
        num_contractors=30,
        num_backers=60,
        num_arbiters=5,
    )

    results = run_efficacy_analysis(config, n_runs=10, seed=42)

    reporter = TextReporter()

    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    print(f"\nStatistical Summary:")
    summary = results["statistical_summary"]
    print(f"  - Completion Rate: {summary['completion_rate']['mean']:.1%} "
          f"(95% CI: [{summary['completion_rate']['95% CI'][0]:.1%}, {summary['completion_rate']['95% CI'][1]:.1%}])")
    print(f"  - Dispute Rate: {summary['dispute_rate']['mean']:.1%} "
          f"(95% CI: [{summary['dispute_rate']['95% CI'][0]:.1%}, {summary['dispute_rate']['95% CI'][1]:.1%}])")
    print(f"  - Average Quality: {summary['avg_quality']['mean']:.2f}")
    print(f"  - Total Value Transacted: {summary['total_value']:.0f}")

    print(f"\nEfficacy Metrics:")
    efficacy = results["efficacy_metrics"]
    print(f"  - Transaction Completion Rate: {efficacy['transaction_completion_rate']:.1%}")
    print(f"  - Market Liquidity: {efficacy['market_liquidity']:.2f} per agent")
    print(f"  - Honest Contractor Premium: {efficacy['honest_contractor_premium']:.1%}")
    print(f"  - Dispute Deterrence: {efficacy['dispute_deterrence']:.1%}")
    print(f"  - Gini Coefficient: {efficacy['gini_coefficient']:.3f}")

    print(f"\nInterpretation:")
    interpretation = results["interpretation"]
    status = "[Y]" if interpretation["system_effective"] else "[N]"
    print(f"  {status} System Effective: {interpretation['system_effective']}")
    status = "[Y]" if interpretation["market_healthy"] else "[N]"
    print(f"  {status} Market Healthy: {interpretation['market_healthy']}")
    status = "[Y]" if interpretation["incentives_aligned"] else "[N]"
    print(f"  {status} Incentives Aligned: {interpretation['incentives_aligned']}")

    return results


def run_full_analysis(n_runs: int = 30, save: bool = True):
    """Run full statistical analysis."""
    print(f"\n> Running Full Analysis ({n_runs} runs, 1000 ticks)...")
    print("  This provides statistically significant results.\n")

    config = SimulationConfig(
        num_ticks=1000,
        num_contractors=50,
        num_backers=100,
        num_arbiters=10,
    )

    runner = MonteCarloRunner(
        base_config=config,
        n_runs=n_runs,
        base_seed=42,
    )

    def progress(done, total, name):
        pct = done / total * 100
        bar_len = int(pct / 2)
        bar = "#" * bar_len + "-" * (50 - bar_len)
        print(f"\r  [{bar}] {done}/{total} runs", end="", flush=True)

    analysis = runner.run("full_analysis", progress)
    print()  # New line after progress bar

    # Generate report
    reporter = TextReporter()
    report = reporter.generate_summary_report(analysis, "Full Analysis")
    print(report)

    if save:
        # Save results
        results_path = runner.save_results("full_analysis.json")
        print(f"\nResults saved to: {results_path}")

    return analysis


def run_scenario_comparison(scenarios: list = None, n_runs: int = 20, save: bool = True):
    """Compare multiple scenarios."""
    if scenarios is None:
        scenarios = ["baseline", "high_fees", "low_trust", "high_trust", "adversarial"]

    print(f"\n> Comparing Scenarios: {', '.join(scenarios)}")
    print(f"  Running {n_runs} simulations per scenario...\n")

    runner = MonteCarloRunner(
        base_config=SimulationConfig(),
        n_runs=n_runs,
        base_seed=42,
    )

    def progress(name, done, total):
        print(f"  [{done}/{total}] Completed: {name}")

    results = runner.compare_scenarios(scenarios, progress)

    # Generate comparison table
    print("\n" + "=" * 70)
    print("SCENARIO COMPARISON")
    print("=" * 70)

    analyses = {name: data["analysis"] for name, data in results.items()}
    table = generate_summary_table(analyses)
    print("\n" + table)

    # Detailed findings
    print("\n\nKey Findings:")

    baseline = results.get("baseline", {}).get("analysis")
    if baseline:
        baseline_dispute = baseline.summary()["dispute_rate"]["mean"]

        for name, data in results.items():
            if name == "baseline":
                continue
            analysis = data["analysis"]
            dispute_rate = analysis.summary()["dispute_rate"]["mean"]
            diff = (dispute_rate - baseline_dispute) / baseline_dispute * 100 if baseline_dispute > 0 else 0
            direction = "higher" if diff > 0 else "lower"
            print(f"  - {name}: Dispute rate {abs(diff):.1f}% {direction} than baseline")

    if save:
        # Save results
        output_dir = Path("results")
        output_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = output_dir / f"scenario_comparison_{timestamp}.json"

        save_data = {
            "scenarios": scenarios,
            "n_runs": n_runs,
            "results": {
                name: data["analysis"].summary()
                for name, data in results.items()
            }
        }

        with open(filepath, "w") as f:
            json.dump(save_data, f, indent=2)

        print(f"\nResults saved to: {filepath}")

    return results


def run_parameter_sweep(parameter: str, n_runs: int = 15):
    """Run parameter sensitivity analysis."""
    print(f"\n> Running Parameter Sweep: {parameter}")

    # Define sweep ranges for common parameters
    sweep_configs = {
        "fee": {
            "name": "economy_params.platform_fee_bps",
            "values": [50, 100, 200, 300, 500],
            "labels": ["0.5%", "1%", "2%", "3%", "5%"],
        },
        "arbitration_fee": {
            "name": "economy_params.arbitration_fee_bps",
            "values": [200, 500, 1000, 1500],
            "labels": ["2%", "5%", "10%", "15%"],
        },
        "immediate": {
            "name": "economy_params.max_immediate_bps",
            "values": [1000, 2000, 3000, 4000],
            "labels": ["10%", "20%", "30%", "40%"],
        },
        "quorum": {
            "name": "economy_params.backers_vote_quorum_bps",
            "values": [5000, 6000, 7000, 8000, 9000],
            "labels": ["50%", "60%", "70%", "80%", "90%"],
        },
        "contractors": {
            "name": "num_contractors",
            "values": [20, 50, 100, 200],
            "labels": ["20", "50", "100", "200"],
        },
    }

    if parameter not in sweep_configs:
        print(f"  Unknown parameter: {parameter}")
        print(f"  Available parameters: {', '.join(sweep_configs.keys())}")
        return None

    sweep = sweep_configs[parameter]
    print(f"  Testing values: {sweep['labels']}")

    base_config = SimulationConfig(
        num_ticks=500,
        num_contractors=30,
        num_backers=60,
        num_arbiters=5,
    )

    runner = MonteCarloRunner(
        base_config=base_config,
        n_runs=n_runs,
        base_seed=42,
    )

    results = runner.run_parameter_sweep(
        sweep["name"],
        sweep["values"],
        progress_callback=lambda p, i, n: print(f"  [{i}/{n}] Testing {p}={sweep['labels'][i-1]}")
    )

    # Display results
    print("\n" + "=" * 70)
    print(f"PARAMETER SWEEP: {parameter}")
    print("=" * 70)

    print("\nValue      | Completion | Disputes | Quality  | Treasury")
    print("-" * 60)

    for value, label in zip(sweep["values"], sweep["labels"]):
        if value in results:
            summary = results[value].summary()
            completion = summary["completion_rate"]["mean"]
            disputes = summary["dispute_rate"]["mean"]
            quality = summary["avg_quality"]["mean"]
            treasury = summary["treasury"]

            print(f"{label:10s} | {completion:9.1%} | {disputes:8.1%} | {quality:8.2f} | {treasury:8.0f}")

    # Find optimal value
    best_value = None
    best_score = -1

    for value in sweep["values"]:
        if value in results:
            summary = results[value].summary()
            # Simple scoring: high completion, low disputes, high quality
            score = (
                summary["completion_rate"]["mean"] * 0.4 +
                (1 - summary["dispute_rate"]["mean"]) * 0.4 +
                summary["avg_quality"]["mean"] * 0.2
            )
            if score > best_score:
                best_score = score
                best_value = value

    if best_value is not None:
        idx = sweep["values"].index(best_value)
        print(f"\n  Optimal value: {sweep['labels'][idx]} (score: {best_score:.3f})")

    return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Trustless Economy Game-Theory Simulation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m simulation                    Run quick demo
  python -m simulation --full             Run full statistical analysis
  python -m simulation --compare          Compare all predefined scenarios
  python -m simulation --sweep fee        Test sensitivity to platform fees
  python -m simulation --sweep immediate  Test sensitivity to immediate release cap
        """
    )

    parser.add_argument("--full", action="store_true",
                       help="Run full statistical analysis (30 runs)")
    parser.add_argument("--compare", action="store_true",
                       help="Compare predefined scenarios")
    parser.add_argument("--sweep", metavar="PARAM",
                       help="Run parameter sweep (fee, arbitration_fee, immediate, quorum, contractors)")
    parser.add_argument("--runs", type=int, default=None,
                       help="Number of simulation runs")
    parser.add_argument("--no-save", action="store_true",
                       help="Don't save results to file")
    parser.add_argument("--seed", type=int, default=42,
                       help="Random seed for reproducibility")

    args = parser.parse_args()

    print_header()

    try:
        if args.full:
            n_runs = args.runs or 30
            run_full_analysis(n_runs=n_runs, save=not args.no_save)

        elif args.compare:
            n_runs = args.runs or 20
            run_scenario_comparison(n_runs=n_runs, save=not args.no_save)

        elif args.sweep:
            n_runs = args.runs or 15
            run_parameter_sweep(args.sweep, n_runs=n_runs)

        else:
            # Default: quick demo
            run_quick_demo()

        print("\n[OK] Simulation complete!")

    except KeyboardInterrupt:
        print("\n\n[!] Simulation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[X] Error: {e}")
        raise


if __name__ == "__main__":
    main()
