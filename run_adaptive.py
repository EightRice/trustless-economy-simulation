#!/usr/bin/env python3
"""
Run adaptive simulation with learning agents.
Tracks convergence to equilibrium over time.
"""
import sys
import random
from dataclasses import asdict

from .core.parameters import EconomyParameters
from .core.adaptive_economy import AdaptiveEconomy


def run_adaptive_simulation(
    num_ticks: int = 2000,
    num_contractors: int = 40,
    num_backers: int = 80,
    num_arbiters: int = 8,
    seed: int = 42,
    verbose: bool = True
):
    """
    Run adaptive simulation and track convergence.
    """
    if verbose:
        print("\n" + "=" * 70)
        print("ADAPTIVE ECONOMY SIMULATION")
        print("Agents learn and adapt strategies over time")
        print("=" * 70)

    params = EconomyParameters()
    economy = AdaptiveEconomy(params=params)
    economy.initialize(num_contractors, num_backers, num_arbiters, seed)

    if verbose:
        print(f"\nInitialized: {num_contractors} contractors, {num_backers} backers, {num_arbiters} arbiters")
        print(f"Running for {num_ticks} ticks...")
        print("\nPhase 1: Exploration (agents learning)")
        print("-" * 40)

    # Track phases
    phases = [
        (0, 500, "Exploration"),
        (500, 1000, "Adaptation"),
        (1000, 1500, "Convergence"),
        (1500, num_ticks, "Equilibrium")
    ]

    phase_results = {}
    current_phase_idx = 0

    for tick in range(num_ticks):
        economy.tick()

        # Phase transitions
        if current_phase_idx < len(phases) - 1:
            _, phase_end, _ = phases[current_phase_idx]
            if tick >= phase_end:
                # Record phase results
                phase_name = phases[current_phase_idx][2]
                phase_results[phase_name] = economy.get_summary()

                current_phase_idx += 1
                if verbose:
                    new_phase = phases[current_phase_idx][2]
                    print(f"\nPhase {current_phase_idx + 1}: {new_phase}")
                    print("-" * 40)

        # Progress reporting
        if verbose and tick % 200 == 0 and tick > 0:
            summary = economy.get_summary()
            recent = summary["recent_metrics"]
            print(f"  Tick {tick}: Completion={recent['completion_rate']:.1%}, "
                  f"Disputes={recent['dispute_rate']:.1%}, "
                  f"Quality={recent['avg_quality']:.2f}")

            if summary["equilibrium_reached"]:
                print(f"    -> Equilibrium reached at tick {summary['equilibrium_tick']}")

    # Final results
    final_summary = economy.get_summary()
    phase_results["Final"] = final_summary

    if verbose:
        print("\n" + "=" * 70)
        print("RESULTS")
        print("=" * 70)

        print("\n--- Strategy Evolution ---")
        for phase_name, result in phase_results.items():
            recent = result["recent_metrics"]
            strat = result.get("strategy_evolution", {})
            print(f"\n{phase_name}:")
            print(f"  Completion Rate: {recent['completion_rate']:.1%}")
            print(f"  Dispute Rate:    {recent['dispute_rate']:.1%}")
            print(f"  Avg Quality:     {recent['avg_quality']:.2f}")
            print(f"  Contractor Quality Target: {strat.get('contractor_avg_quality', 0):.2f}")
            print(f"  Backer Immediate Offer:    {strat.get('backer_avg_immediate', 0):.1%}")

        print("\n--- Equilibrium Analysis ---")
        if final_summary["equilibrium_reached"]:
            print(f"  Equilibrium reached at tick: {final_summary['equilibrium_tick']}")
            print("  System converged to stable state!")
        else:
            print("  Equilibrium NOT reached within simulation window")
            print("  System may need more time or parameter adjustment")

        print("\n--- Final Statistics ---")
        cumulative = final_summary["cumulative"]
        print(f"  Total Projects:  {cumulative['total_projects']}")
        print(f"  Completed:       {cumulative['completed']}")
        print(f"  Disputed:        {cumulative['disputed']}")
        completion_rate = cumulative['completed'] / max(1, cumulative['completed'] + cumulative['disputed'])
        print(f"  Success Rate:    {completion_rate:.1%}")

        agents = final_summary["agent_stats"]
        print(f"\n  Avg Contractor Rep: {agents['avg_contractor_reputation']:.1f}")
        print(f"  Avg Backer Rep:     {agents['avg_backer_reputation']:.1f}")
        print(f"  Arbiter Accuracy:   {agents['arbiter_accuracy']:.1%}")

        print(f"\n  Treasury Balance:   {final_summary['treasury']:.2f}")

        # Interpretation
        print("\n--- Interpretation ---")
        recent = final_summary["recent_metrics"]

        if recent["completion_rate"] > 0.7:
            print("  [+] High completion rate - market is functioning well")
        elif recent["completion_rate"] > 0.5:
            print("  [o] Moderate completion rate - some friction in market")
        else:
            print("  [-] Low completion rate - significant market issues")

        if recent["dispute_rate"] < 0.15:
            print("  [+] Low dispute rate - incentives well-aligned")
        elif recent["dispute_rate"] < 0.25:
            print("  [o] Moderate disputes - some tension in system")
        else:
            print("  [-] High dispute rate - incentive misalignment")

        if recent["avg_quality"] > 0.7:
            print("  [+] High work quality - contractors motivated")
        elif recent["avg_quality"] > 0.5:
            print("  [o] Moderate quality")
        else:
            print("  [-] Low quality - contractor incentives weak")

        # Check for synergistic behavior
        strat = final_summary["strategy_evolution"]
        if strat.get("quality_convergence", 0) > 0.05:
            print("\n  ** Contractors converging toward HIGHER quality **")
            print("     This suggests incentives reward quality over time")
        elif strat.get("quality_convergence", 0) < -0.05:
            print("\n  ** Contractors converging toward LOWER quality **")
            print("     This suggests incentives may not sufficiently reward quality")

    return economy, phase_results


def run_multiple_seeds(n_runs: int = 10, num_ticks: int = 2000, verbose: bool = True):
    """
    Run multiple simulations with different seeds for statistical analysis.
    """
    if verbose:
        print("\n" + "=" * 70)
        print(f"MONTE CARLO ADAPTIVE SIMULATION ({n_runs} runs)")
        print("=" * 70)

    all_results = []

    for i in range(n_runs):
        if verbose:
            print(f"\n--- Run {i+1}/{n_runs} ---")

        economy, phase_results = run_adaptive_simulation(
            num_ticks=num_ticks,
            seed=42 + i,
            verbose=False
        )

        final = phase_results.get("Final", {})
        all_results.append({
            "seed": 42 + i,
            "equilibrium_reached": final.get("equilibrium_reached", False),
            "equilibrium_tick": final.get("equilibrium_tick"),
            "completion_rate": final.get("recent_metrics", {}).get("completion_rate", 0),
            "dispute_rate": final.get("recent_metrics", {}).get("dispute_rate", 0),
            "avg_quality": final.get("recent_metrics", {}).get("avg_quality", 0),
            "quality_convergence": final.get("strategy_evolution", {}).get("quality_convergence", 0),
        })

        if verbose:
            r = all_results[-1]
            eq = "Yes" if r["equilibrium_reached"] else "No"
            print(f"  Equilibrium: {eq}, Completion: {r['completion_rate']:.1%}, "
                  f"Disputes: {r['dispute_rate']:.1%}, Quality: {r['avg_quality']:.2f}")

    # Aggregate results
    if verbose:
        print("\n" + "=" * 70)
        print("AGGREGATE RESULTS")
        print("=" * 70)

        n_equilibrium = sum(1 for r in all_results if r["equilibrium_reached"])
        avg_completion = sum(r["completion_rate"] for r in all_results) / len(all_results)
        avg_disputes = sum(r["dispute_rate"] for r in all_results) / len(all_results)
        avg_quality = sum(r["avg_quality"] for r in all_results) / len(all_results)
        avg_convergence = sum(r["quality_convergence"] for r in all_results) / len(all_results)

        print(f"\n  Runs reaching equilibrium: {n_equilibrium}/{n_runs} ({n_equilibrium/n_runs:.0%})")
        print(f"  Average completion rate:   {avg_completion:.1%}")
        print(f"  Average dispute rate:      {avg_disputes:.1%}")
        print(f"  Average work quality:      {avg_quality:.2f}")
        print(f"  Average quality convergence: {avg_convergence:+.3f}")

        print("\n--- Interpretation ---")
        if n_equilibrium > n_runs * 0.7:
            print("  [+] Most runs reach equilibrium - system has stable attractor")
        else:
            print("  [-] Many runs don't reach equilibrium - system may be chaotic")

        if avg_convergence > 0.02:
            print("  [+] Quality INCREASING over time - virtuous cycle emerging")
            print("      Agents learn that quality pays off!")
        elif avg_convergence < -0.02:
            print("  [-] Quality DECREASING over time - race to bottom")
            print("      Incentives may need strengthening")
        else:
            print("  [o] Quality stable - no strong evolutionary pressure")

        if avg_completion > 0.7 and avg_disputes < 0.2:
            print("\n  ** SYNERGISTIC EQUILIBRIUM DETECTED **")
            print("     The incentive structure successfully aligns agent behavior")
        elif avg_completion > 0.5:
            print("\n  ** PARTIAL ALIGNMENT **")
            print("     System works but could be improved")
        else:
            print("\n  ** MISALIGNMENT DETECTED **")
            print("     Incentive structure needs revision")

    return all_results


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--monte-carlo":
        n_runs = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        run_multiple_seeds(n_runs=n_runs)
    else:
        run_adaptive_simulation()
