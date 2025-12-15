#!/usr/bin/env python3
"""
Compare Trustless Economy vs Traditional Economy with Legal Enforcement.

Key hypothesis: Traditional economies have lower dispute rates because:
1. External penalties (lawsuits, asset seizure) beyond contract scope
2. Credit scores affect ALL future dealings (not just platform reputation)
3. Professional licensing creates barriers and accountability
4. Higher immediate release possible due to legal recourse as backstop
"""
import sys
import random

from .core.parameters import EconomyParameters
from .core.adaptive_economy import AdaptiveEconomy
from .core.traditional_economy import TraditionalEconomy


def run_comparison(
    num_ticks: int = 1500,
    num_contractors: int = 40,
    num_backers: int = 80,
    num_arbiters: int = 8,
    seed: int = 42,
    verbose: bool = True
):
    """
    Run both economies side-by-side and compare results.
    """
    if verbose:
        print("\n" + "=" * 70)
        print("TRUSTLESS vs TRADITIONAL ECONOMY COMPARISON")
        print("=" * 70)
        print("\nKey Differences Modeled:")
        print("  Traditional Economy:")
        print("    - External penalties (lawsuits can exceed contract value)")
        print("    - Credit scores affect all future financial dealings")
        print("    - Professional licensing requirements")
        print("    - Higher immediate release (legal backstop)")
        print("  Trustless Economy:")
        print("    - Penalties limited to stake within contract")
        print("    - Reputation only affects platform dealings")
        print("    - No licensing barriers")
        print("    - Lower immediate release (reputation-based trust)")

    params = EconomyParameters()

    # Initialize both economies with same seed
    trustless = AdaptiveEconomy(params=params)
    trustless.initialize(num_contractors, num_backers, num_arbiters, seed)

    traditional = TraditionalEconomy(params=params)
    traditional.initialize(num_contractors, num_backers, num_arbiters, seed)

    if verbose:
        print(f"\nRunning {num_ticks} ticks for each economy...")
        print("-" * 70)

    # Track metrics over time
    trustless_history = {"completion": [], "disputes": [], "quality": []}
    traditional_history = {"completion": [], "disputes": [], "quality": []}

    checkpoint_ticks = [250, 500, 750, 1000, 1250, 1500]

    for tick in range(num_ticks):
        trustless.tick()
        traditional.tick()

        # Record periodic snapshots
        if tick > 0 and tick % 100 == 0:
            t_sum = trustless.get_summary()
            tr_sum = traditional.get_summary()

            trustless_history["completion"].append(t_sum["recent_metrics"]["completion_rate"])
            trustless_history["disputes"].append(t_sum["recent_metrics"]["dispute_rate"])
            trustless_history["quality"].append(t_sum["recent_metrics"]["avg_quality"])

            traditional_history["completion"].append(tr_sum["recent_metrics"]["completion_rate"])
            traditional_history["disputes"].append(tr_sum["recent_metrics"]["dispute_rate"])
            traditional_history["quality"].append(tr_sum["recent_metrics"]["avg_quality"])

        # Print checkpoints
        if verbose and tick in checkpoint_ticks:
            t_sum = trustless.get_summary()
            tr_sum = traditional.get_summary()

            print(f"\nTick {tick}:")
            print(f"  {'Metric':<20} {'Trustless':>12} {'Traditional':>12} {'Delta':>10}")
            print(f"  {'-'*54}")

            t_comp = t_sum["recent_metrics"]["completion_rate"]
            tr_comp = tr_sum["recent_metrics"]["completion_rate"]
            print(f"  {'Completion Rate':<20} {t_comp:>11.1%} {tr_comp:>11.1%} {tr_comp-t_comp:>+10.1%}")

            t_disp = t_sum["recent_metrics"]["dispute_rate"]
            tr_disp = tr_sum["recent_metrics"]["dispute_rate"]
            print(f"  {'Dispute Rate':<20} {t_disp:>11.1%} {tr_disp:>11.1%} {tr_disp-t_disp:>+10.1%}")

            t_qual = t_sum["recent_metrics"]["avg_quality"]
            tr_qual = tr_sum["recent_metrics"]["avg_quality"]
            print(f"  {'Avg Quality':<20} {t_qual:>11.2f} {tr_qual:>11.2f} {tr_qual-t_qual:>+10.2f}")

    # Final comparison
    t_final = trustless.get_summary()
    tr_final = traditional.get_summary()

    if verbose:
        print("\n" + "=" * 70)
        print("FINAL RESULTS")
        print("=" * 70)

        print("\n--- Core Metrics ---")
        print(f"  {'Metric':<25} {'Trustless':>12} {'Traditional':>12} {'Delta':>10}")
        print(f"  {'-'*59}")

        metrics = [
            ("Completion Rate", "completion_rate", True),
            ("Dispute Rate", "dispute_rate", True),
            ("Avg Quality", "avg_quality", False),
        ]

        for label, key, is_pct in metrics:
            t_val = t_final["recent_metrics"][key]
            tr_val = tr_final["recent_metrics"][key]
            delta = tr_val - t_val

            if is_pct:
                print(f"  {label:<25} {t_val:>11.1%} {tr_val:>11.1%} {delta:>+10.1%}")
            else:
                print(f"  {label:<25} {t_val:>11.2f} {tr_val:>11.2f} {delta:>+10.2f}")

        print("\n--- Quality Evolution ---")
        t_conv = t_final["strategy_evolution"]["quality_convergence"]
        tr_conv = tr_final["strategy_evolution"]["quality_convergence"]
        print(f"  Trustless Quality Trend:    {t_conv:+.3f}")
        print(f"  Traditional Quality Trend:  {tr_conv:+.3f}")

        print("\n--- Volume ---")
        print(f"  {'Metric':<25} {'Trustless':>12} {'Traditional':>12}")
        print(f"  {'-'*49}")
        print(f"  {'Total Projects':<25} {t_final['cumulative']['total_projects']:>12} {tr_final['cumulative']['total_projects']:>12}")
        print(f"  {'Completed':<25} {t_final['cumulative']['completed']:>12} {tr_final['cumulative']['completed']:>12}")
        print(f"  {'Disputed':<25} {t_final['cumulative']['disputed']:>12} {tr_final['cumulative']['disputed']:>12}")

        # Traditional-specific
        if "traditional_metrics" in tr_final:
            print("\n--- Traditional Economy Specific ---")
            print(f"  Avg Credit Score:    {tr_final['traditional_metrics']['avg_credit_score']:.0f}")
            print(f"  Licensed Contractors: {tr_final['traditional_metrics']['licensed_contractors']:.0%}")

        # Analysis
        print("\n" + "=" * 70)
        print("ANALYSIS: WHY TRADITIONAL HAS LOWER DISPUTES")
        print("=" * 70)

        dispute_diff = t_final["recent_metrics"]["dispute_rate"] - tr_final["recent_metrics"]["dispute_rate"]

        print(f"\n  Dispute Rate Difference: {dispute_diff:+.1%}")
        print(f"  (Trustless {t_final['recent_metrics']['dispute_rate']:.1%} vs Traditional {tr_final['recent_metrics']['dispute_rate']:.1%})")

        print("\n  Contributing Factors:")

        if dispute_diff > 0.05:
            print("\n  1. EXTERNAL PENALTIES")
            print("     Traditional contractors face lawsuits, credit damage, license loss")
            print("     -> Creates stronger deterrent against low-quality work")
            print("     -> Penalties can EXCEED contract value")

            print("\n  2. CREDIT SCORE SYSTEM")
            print("     Traditional: Credit affects ALL financial dealings")
            print("     Trustless: Reputation only affects platform dealings")
            print("     -> Traditional has stronger cross-domain accountability")

            print("\n  3. HIGHER IMMEDIATE RELEASE")
            print("     Traditional backers offer more upfront (legal recourse as backstop)")
            print("     -> Contractors have less 'locked' funds to fight over")
            print("     -> Fewer disputes triggered by escrow disagreements")

            print("\n  4. PROFESSIONAL LICENSING")
            print("     Traditional: Bad actors can lose license (market exit)")
            print("     Trustless: No formal barriers to re-entry")
            print("     -> Traditional has stronger selection/filtering")

        print("\n  IMPLICATIONS FOR TRUSTLESS ECONOMY:")
        if dispute_diff > 0.1:
            print("  [-] Significant gap - trustless may need additional mechanisms")
            print("      Suggestions:")
            print("      - Increase reputation impact on future opportunities")
            print("      - Add staking requirements that scale with project size")
            print("      - Implement cross-platform reputation sharing")
        elif dispute_diff > 0.05:
            print("  [o] Moderate gap - trustless performs reasonably")
            print("      The gap reflects inherent tradeoff:")
            print("      - Trustless: Permissionless, global, no external dependencies")
            print("      - Traditional: Stronger enforcement, but restricted access")
        else:
            print("  [+] Small gap - trustless incentives nearly match traditional!")
            print("      The reputation/escrow system effectively substitutes")
            print("      for external enforcement mechanisms")

    return {
        "trustless": t_final,
        "traditional": tr_final,
        "history": {
            "trustless": trustless_history,
            "traditional": traditional_history,
        }
    }


def run_monte_carlo_comparison(n_runs: int = 10, num_ticks: int = 1500, verbose: bool = True):
    """
    Run multiple comparisons with different seeds for statistical significance.
    """
    if verbose:
        print("\n" + "=" * 70)
        print(f"MONTE CARLO COMPARISON ({n_runs} runs)")
        print("=" * 70)

    trustless_results = []
    traditional_results = []

    for i in range(n_runs):
        if verbose:
            print(f"\n--- Run {i+1}/{n_runs} ---")

        results = run_comparison(
            num_ticks=num_ticks,
            seed=42 + i,
            verbose=False
        )

        trustless_results.append({
            "completion": results["trustless"]["recent_metrics"]["completion_rate"],
            "disputes": results["trustless"]["recent_metrics"]["dispute_rate"],
            "quality": results["trustless"]["recent_metrics"]["avg_quality"],
            "quality_conv": results["trustless"]["strategy_evolution"]["quality_convergence"],
        })

        traditional_results.append({
            "completion": results["traditional"]["recent_metrics"]["completion_rate"],
            "disputes": results["traditional"]["recent_metrics"]["dispute_rate"],
            "quality": results["traditional"]["recent_metrics"]["avg_quality"],
            "quality_conv": results["traditional"]["strategy_evolution"]["quality_convergence"],
        })

        if verbose:
            t = trustless_results[-1]
            tr = traditional_results[-1]
            print(f"  Trustless:    Comp={t['completion']:.1%}, Disp={t['disputes']:.1%}, Qual={t['quality']:.2f}")
            print(f"  Traditional:  Comp={tr['completion']:.1%}, Disp={tr['disputes']:.1%}, Qual={tr['quality']:.2f}")

    # Aggregate
    if verbose:
        print("\n" + "=" * 70)
        print("AGGREGATE COMPARISON")
        print("=" * 70)

        def avg(lst):
            return sum(lst) / len(lst)

        def std(lst):
            m = avg(lst)
            return (sum((x - m) ** 2 for x in lst) / len(lst)) ** 0.5

        print(f"\n  {'Metric':<20} {'Trustless':>15} {'Traditional':>15} {'p-value':>10}")
        print(f"  {'-'*60}")

        metrics = [
            ("Completion Rate", "completion"),
            ("Dispute Rate", "disputes"),
            ("Avg Quality", "quality"),
            ("Quality Trend", "quality_conv"),
        ]

        try:
            from scipy import stats as scipy_stats
            has_scipy = True
        except ImportError:
            has_scipy = False

        for label, key in metrics:
            t_vals = [r[key] for r in trustless_results]
            tr_vals = [r[key] for r in traditional_results]

            t_mean = avg(t_vals)
            tr_mean = avg(tr_vals)

            # Calculate p-value if scipy available
            if has_scipy:
                _, p_val = scipy_stats.ttest_ind(t_vals, tr_vals)
                p_str = f"{p_val:.4f}" + ("***" if p_val < 0.01 else "**" if p_val < 0.05 else "")
            else:
                p_str = "N/A"

            if key in ["completion", "disputes"]:
                print(f"  {label:<20} {t_mean:>14.1%} {tr_mean:>14.1%} {p_str:>10}")
            else:
                print(f"  {label:<20} {t_mean:>14.3f} {tr_mean:>14.3f} {p_str:>10}")

        # Calculate dispute rate difference
        t_disputes = avg([r["disputes"] for r in trustless_results])
        tr_disputes = avg([r["disputes"] for r in traditional_results])
        diff = t_disputes - tr_disputes

        print("\n--- KEY FINDING ---")
        print(f"  Dispute Rate Gap: {diff:+.1%}")
        print(f"  (Trustless higher by {diff:.1%})")

        if diff > 0.1:
            print("\n  CONCLUSION: External enforcement mechanisms account for")
            print(f"  approximately {diff:.1%} of the dispute rate difference.")
            print("  This confirms that penalties beyond contract scope")
            print("  significantly deter bad behavior in traditional economies.")
        elif diff > 0.05:
            print("\n  CONCLUSION: External enforcement provides moderate benefit.")
            print("  Trustless economy's reputation system partially compensates")
            print("  but cannot fully match external penalty deterrence.")
        else:
            print("\n  CONCLUSION: Trustless economy performs comparably!")
            print("  Reputation and escrow mechanisms effectively substitute")
            print("  for external legal enforcement.")

    return {
        "trustless": trustless_results,
        "traditional": traditional_results,
    }


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--monte-carlo":
        n_runs = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        run_monte_carlo_comparison(n_runs=n_runs)
    else:
        run_comparison()
