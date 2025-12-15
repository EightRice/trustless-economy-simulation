"""
Visualization and reporting tools for simulation results.
Generates text-based reports and data for plotting.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import json

from .statistics import (
    SimulationAnalysis,
    EfficacyMetrics,
    DescriptiveStats,
    ConfidenceInterval,
)


def format_percentage(value: float, decimals: int = 1) -> str:
    """Format a decimal as a percentage string."""
    return f"{value * 100:.{decimals}f}%"


def format_ci(ci: ConfidenceInterval, as_percentage: bool = False) -> str:
    """Format a confidence interval."""
    if as_percentage:
        return f"{format_percentage(ci.estimate)} [{format_percentage(ci.lower)}, {format_percentage(ci.upper)}]"
    return f"{ci.estimate:.3f} [{ci.lower:.3f}, {ci.upper:.3f}]"


def format_stat(stat: DescriptiveStats, decimals: int = 2) -> str:
    """Format descriptive statistics."""
    return f"mean={stat.mean:.{decimals}f}, std={stat.std:.{decimals}f}, range=[{stat.min:.{decimals}f}, {stat.max:.{decimals}f}]"


class TextReporter:
    """Generate text-based reports from simulation results."""

    def __init__(self, width: int = 80):
        self.width = width

    def section(self, title: str) -> str:
        """Create a section header."""
        return f"\n{'=' * self.width}\n{title.upper().center(self.width)}\n{'=' * self.width}\n"

    def subsection(self, title: str) -> str:
        """Create a subsection header."""
        return f"\n{'-' * len(title)}\n{title}\n{'-' * len(title)}\n"

    def bullet(self, text: str) -> str:
        """Create a bullet point."""
        return f"  - {text}"

    def generate_summary_report(
        self,
        analysis: SimulationAnalysis,
        config_name: str = "Default"
    ) -> str:
        """Generate a summary report from simulation analysis."""
        lines = []

        lines.append(self.section(f"Simulation Results: {config_name}"))

        # Overview
        lines.append(self.subsection("Overview"))
        lines.append(self.bullet(f"Number of simulation runs: {len(analysis.runs)}"))

        summary = analysis.summary()
        lines.append(self.bullet(f"Total value transacted: {summary['total_value']:.2f}"))
        lines.append(self.bullet(f"Treasury balance: {summary['treasury']:.2f}"))

        # Project Outcomes
        lines.append(self.subsection("Project Outcomes"))

        if analysis.ci_completion_rate:
            lines.append(self.bullet(
                f"Completion rate: {format_ci(analysis.ci_completion_rate, as_percentage=True)} (95% CI)"
            ))

        if analysis.ci_dispute_rate:
            lines.append(self.bullet(
                f"Dispute rate: {format_ci(analysis.ci_dispute_rate, as_percentage=True)} (95% CI)"
            ))

        if analysis.appeal_rate:
            lines.append(self.bullet(
                f"Appeal rate: {format_percentage(analysis.appeal_rate.mean)}"
            ))

        # Quality Metrics
        lines.append(self.subsection("Quality Metrics"))

        if analysis.ci_avg_quality:
            lines.append(self.bullet(
                f"Average work quality: {format_ci(analysis.ci_avg_quality)} (95% CI)"
            ))

        # Interpretation
        lines.append(self.subsection("Interpretation"))

        completion_rate = analysis.ci_completion_rate.estimate if analysis.ci_completion_rate else 0
        dispute_rate = analysis.ci_dispute_rate.estimate if analysis.ci_dispute_rate else 0
        quality = analysis.ci_avg_quality.estimate if analysis.ci_avg_quality else 0

        if completion_rate > 0.8:
            lines.append(self.bullet("[+] High project completion rate indicates healthy marketplace"))
        elif completion_rate > 0.6:
            lines.append(self.bullet("[o] Moderate completion rate - room for improvement"))
        else:
            lines.append(self.bullet("[-] Low completion rate - system may need adjustment"))

        if dispute_rate < 0.15:
            lines.append(self.bullet("[+] Low dispute rate indicates well-aligned incentives"))
        elif dispute_rate < 0.3:
            lines.append(self.bullet("[o] Moderate dispute rate - consider fee adjustments"))
        else:
            lines.append(self.bullet("[-] High dispute rate - incentive structure may be flawed"))

        if quality > 0.7:
            lines.append(self.bullet("[+] High average work quality"))
        elif quality > 0.5:
            lines.append(self.bullet("[o] Moderate work quality"))
        else:
            lines.append(self.bullet("[-] Low work quality - contractor incentives need review"))

        return "\n".join(lines)

    def generate_efficacy_report(
        self,
        efficacy: EfficacyMetrics,
        config_name: str = "Default"
    ) -> str:
        """Generate efficacy metrics report."""
        lines = []

        lines.append(self.section(f"Efficacy Analysis: {config_name}"))

        # Market Efficiency
        lines.append(self.subsection("Market Efficiency"))
        lines.append(self.bullet(
            f"Transaction completion rate: {format_percentage(efficacy.transaction_completion_rate)}"
        ))
        lines.append(self.bullet(
            f"Market liquidity (value/agent): {efficacy.market_liquidity:.2f}"
        ))

        # Incentive Alignment
        lines.append(self.subsection("Incentive Alignment"))
        lines.append(self.bullet(
            f"Honest contractor earnings premium: {format_percentage(efficacy.honest_contractor_premium)}"
        ))
        lines.append(self.bullet(
            f"Dispute deterrence score: {format_percentage(efficacy.dispute_deterrence)}"
        ))

        # Fairness
        lines.append(self.subsection("Fairness"))
        lines.append(self.bullet(
            f"Gini coefficient (earnings inequality): {efficacy.gini_coefficient:.3f}"
        ))
        lines.append(self.bullet(
            f"Arbiter accuracy: {format_percentage(efficacy.arbiter_accuracy)}"
        ))
        lines.append(self.bullet(
            f"Appeal overturn rate: {format_percentage(efficacy.appeal_overturn_rate)}"
        ))

        # Sustainability
        lines.append(self.subsection("Sustainability"))
        lines.append(self.bullet(
            f"Treasury growth rate: {format_percentage(efficacy.treasury_growth_rate)}"
        ))

        # Overall Assessment
        lines.append(self.subsection("Overall Assessment"))

        # Effectiveness score (simple weighted average)
        effectiveness_score = (
            0.25 * efficacy.transaction_completion_rate +
            0.25 * efficacy.dispute_deterrence +
            0.20 * (1 - abs(efficacy.gini_coefficient - 0.3)) +  # Target Gini of 0.3
            0.15 * efficacy.arbiter_accuracy +
            0.15 * min(1, efficacy.treasury_growth_rate + 0.5)  # Cap at 150%
        )

        lines.append(self.bullet(f"Composite effectiveness score: {effectiveness_score:.2f}/1.00"))

        if effectiveness_score > 0.75:
            lines.append(self.bullet("*** HIGHLY EFFECTIVE - System performs well"))
        elif effectiveness_score > 0.5:
            lines.append(self.bullet("**- MODERATELY EFFECTIVE - Some improvements possible"))
        else:
            lines.append(self.bullet("*-- NEEDS IMPROVEMENT - Significant issues detected"))

        return "\n".join(lines)

    def generate_comparison_report(
        self,
        baseline_name: str,
        baseline_analysis: SimulationAnalysis,
        comparison_name: str,
        comparison_analysis: SimulationAnalysis,
        test_results: Dict[str, Any]
    ) -> str:
        """Generate comparison report between two scenarios."""
        lines = []

        lines.append(self.section(f"Comparison: {baseline_name} vs {comparison_name}"))

        # Side by side metrics
        lines.append(self.subsection("Key Metrics Comparison"))

        baseline_summary = baseline_analysis.summary()
        comparison_summary = comparison_analysis.summary()

        headers = ["Metric", baseline_name, comparison_name, "Difference"]

        metrics = [
            ("Completion Rate",
             baseline_summary["completion_rate"]["mean"],
             comparison_summary["completion_rate"]["mean"]),
            ("Dispute Rate",
             baseline_summary["dispute_rate"]["mean"],
             comparison_summary["dispute_rate"]["mean"]),
            ("Avg Quality",
             baseline_summary["avg_quality"]["mean"],
             comparison_summary["avg_quality"]["mean"]),
            ("Total Value",
             baseline_summary["total_value"],
             comparison_summary["total_value"]),
        ]

        for metric_name, baseline_val, comparison_val in metrics:
            diff = comparison_val - baseline_val
            diff_str = f"+{diff:.3f}" if diff > 0 else f"{diff:.3f}"
            lines.append(f"  {metric_name:20s}: {baseline_val:.3f}  |  {comparison_val:.3f}  |  {diff_str}")

        # Statistical significance
        lines.append(self.subsection("Statistical Tests"))

        for metric_name, results in test_results.items():
            sig_marker = "***" if results["significant"] else ""
            lines.append(self.bullet(
                f"{metric_name}: p={results['p_value']:.4f} {sig_marker}, "
                f"effect size={results['effect_size']:.2f} ({results.get('effect_interpretation', '')})"
            ))

        return "\n".join(lines)


class DataExporter:
    """Export simulation data for external visualization tools."""

    def __init__(self, output_dir: Path = Path("results")):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_time_series(
        self,
        time_series: Dict[str, List[float]],
        filename: str
    ) -> Path:
        """Export time series data as JSON."""
        filepath = self.output_dir / f"{filename}_timeseries.json"

        data = {
            "tick": list(range(len(time_series.get("projects_per_tick", [])))),
            **time_series
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        return filepath

    def export_agent_distributions(
        self,
        contractor_data: List[dict],
        backer_data: List[dict],
        arbiter_data: List[dict],
        filename: str
    ) -> Path:
        """Export agent data for distribution analysis."""
        filepath = self.output_dir / f"{filename}_agents.json"

        data = {
            "contractors": contractor_data,
            "backers": backer_data,
            "arbiters": arbiter_data,
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        return filepath

    def export_csv(
        self,
        runs: List[dict],
        filename: str
    ) -> Path:
        """Export run summaries as CSV."""
        filepath = self.output_dir / f"{filename}.csv"

        if not runs:
            return filepath

        # Get all keys from first run
        keys = []
        sample = runs[0]

        def flatten_dict(d: dict, prefix: str = "") -> Dict[str, Any]:
            result = {}
            for k, v in d.items():
                new_key = f"{prefix}{k}" if prefix else k
                if isinstance(v, dict):
                    result.update(flatten_dict(v, f"{new_key}_"))
                else:
                    result[new_key] = v
            return result

        flat_runs = [flatten_dict(r) for r in runs]
        keys = list(flat_runs[0].keys())

        lines = [",".join(keys)]
        for run in flat_runs:
            values = [str(run.get(k, "")) for k in keys]
            lines.append(",".join(values))

        with open(filepath, "w") as f:
            f.write("\n".join(lines))

        return filepath

    def export_parameter_sweep(
        self,
        parameter_name: str,
        values: List[Any],
        results: Dict[Any, SimulationAnalysis],
        filename: str
    ) -> Path:
        """Export parameter sweep results."""
        filepath = self.output_dir / f"{filename}_sweep.json"

        data = {
            "parameter": parameter_name,
            "values": [str(v) for v in values],
            "results": {
                str(k): v.summary() for k, v in results.items()
            }
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

        return filepath


def generate_ascii_histogram(
    data: List[float],
    bins: int = 10,
    width: int = 50,
    title: str = ""
) -> str:
    """Generate ASCII histogram for terminal display."""
    if not data:
        return "No data available"

    min_val = min(data)
    max_val = max(data)

    if min_val == max_val:
        return f"All values = {min_val}"

    bin_width = (max_val - min_val) / bins
    counts = [0] * bins

    for value in data:
        bin_idx = min(int((value - min_val) / bin_width), bins - 1)
        counts[bin_idx] += 1

    max_count = max(counts)
    if max_count == 0:
        return "No data in bins"

    lines = []
    if title:
        lines.append(title)
        lines.append("-" * len(title))

    for i, count in enumerate(counts):
        bin_start = min_val + i * bin_width
        bin_end = bin_start + bin_width
        bar_len = int(count / max_count * width)
        bar = "#" * bar_len
        lines.append(f"{bin_start:6.2f}-{bin_end:6.2f} | {bar} ({count})")

    return "\n".join(lines)


def generate_ascii_bar_chart(
    labels: List[str],
    values: List[float],
    width: int = 40,
    title: str = ""
) -> str:
    """Generate ASCII bar chart for terminal display."""
    if not labels or not values:
        return "No data available"

    max_val = max(values)
    if max_val == 0:
        max_val = 1

    max_label_len = max(len(l) for l in labels)

    lines = []
    if title:
        lines.append(title)
        lines.append("-" * len(title))

    for label, value in zip(labels, values):
        bar_len = int(value / max_val * width)
        bar = "#" * bar_len
        lines.append(f"{label:{max_label_len}s} | {bar} {value:.2f}")

    return "\n".join(lines)


def generate_summary_table(
    scenario_results: Dict[str, SimulationAnalysis],
    metrics: List[str] = None
) -> str:
    """Generate summary table comparing multiple scenarios."""
    if not scenario_results:
        return "No scenarios to compare"

    if metrics is None:
        metrics = ["completion_rate", "dispute_rate", "avg_quality", "total_value"]

    # Build table
    scenarios = list(scenario_results.keys())
    col_width = max(15, max(len(s) for s in scenarios) + 2)

    # Header
    header = f"{'Metric':<20}" + "".join(f"{s:>{col_width}}" for s in scenarios)
    lines = [header, "-" * len(header)]

    # Data rows
    for metric in metrics:
        row = f"{metric:<20}"
        for scenario in scenarios:
            analysis = scenario_results[scenario]
            summary = analysis.summary()

            # Navigate to metric value
            if metric in summary:
                if isinstance(summary[metric], dict) and "mean" in summary[metric]:
                    value = summary[metric]["mean"]
                else:
                    value = summary[metric]
            else:
                value = 0

            row += f"{value:>{col_width}.3f}"

        lines.append(row)

    return "\n".join(lines)
