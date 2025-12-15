"""
Statistical analysis tools for simulation results.
Provides rigorous statistical measures to evaluate system efficacy.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import math
import statistics
from collections import defaultdict


@dataclass
class DescriptiveStats:
    """Descriptive statistics for a dataset."""
    n: int
    mean: float
    std: float
    min: float
    max: float
    median: float
    q1: float  # 25th percentile
    q3: float  # 75th percentile

    @classmethod
    def from_data(cls, data: List[float]) -> "DescriptiveStats":
        """Calculate descriptive statistics from data."""
        if not data:
            return cls(0, 0, 0, 0, 0, 0, 0, 0)

        n = len(data)
        sorted_data = sorted(data)

        return cls(
            n=n,
            mean=statistics.mean(data),
            std=statistics.stdev(data) if n > 1 else 0,
            min=min(data),
            max=max(data),
            median=statistics.median(data),
            q1=sorted_data[n // 4] if n >= 4 else sorted_data[0],
            q3=sorted_data[3 * n // 4] if n >= 4 else sorted_data[-1],
        )


@dataclass
class ConfidenceInterval:
    """Confidence interval for a statistic."""
    estimate: float
    lower: float
    upper: float
    confidence_level: float

    @property
    def margin_of_error(self) -> float:
        return (self.upper - self.lower) / 2

    def contains(self, value: float) -> bool:
        return self.lower <= value <= self.upper


def calculate_confidence_interval(
    data: List[float],
    confidence: float = 0.95
) -> ConfidenceInterval:
    """
    Calculate confidence interval for the mean using t-distribution.
    """
    if len(data) < 2:
        mean = data[0] if data else 0
        return ConfidenceInterval(mean, mean, mean, confidence)

    n = len(data)
    mean = statistics.mean(data)
    std = statistics.stdev(data)
    se = std / math.sqrt(n)

    # Use normal approximation for large n, otherwise t-distribution approximation
    if n >= 30:
        # Z-scores for common confidence levels
        z_scores = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
        z = z_scores.get(confidence, 1.96)
    else:
        # Approximate t-distribution with wider interval
        z = 2.0 + (30 - n) * 0.05  # Gets larger as n decreases

    margin = z * se
    return ConfidenceInterval(
        estimate=mean,
        lower=mean - margin,
        upper=mean + margin,
        confidence_level=confidence
    )


def calculate_effect_size(
    group1: List[float],
    group2: List[float]
) -> Tuple[float, str]:
    """
    Calculate Cohen's d effect size between two groups.
    Returns (effect_size, interpretation).
    """
    if not group1 or not group2:
        return 0.0, "undefined"

    mean1 = statistics.mean(group1)
    mean2 = statistics.mean(group2)

    n1, n2 = len(group1), len(group2)

    # Pooled standard deviation
    if n1 > 1 and n2 > 1:
        var1 = statistics.variance(group1)
        var2 = statistics.variance(group2)
        pooled_std = math.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    else:
        pooled_std = 1.0

    if pooled_std == 0:
        return 0.0, "undefined"

    d = (mean1 - mean2) / pooled_std

    # Interpretation (Cohen's conventions)
    abs_d = abs(d)
    if abs_d < 0.2:
        interpretation = "negligible"
    elif abs_d < 0.5:
        interpretation = "small"
    elif abs_d < 0.8:
        interpretation = "medium"
    else:
        interpretation = "large"

    return d, interpretation


def mann_whitney_u(
    group1: List[float],
    group2: List[float]
) -> Tuple[float, float]:
    """
    Perform Mann-Whitney U test (non-parametric).
    Returns (U statistic, approximate p-value).
    """
    if not group1 or not group2:
        return 0.0, 1.0

    # Combine and rank
    combined = [(x, 0) for x in group1] + [(x, 1) for x in group2]
    combined.sort(key=lambda x: x[0])

    # Assign ranks (handling ties with average ranks)
    ranks = []
    i = 0
    while i < len(combined):
        j = i
        while j < len(combined) and combined[j][0] == combined[i][0]:
            j += 1
        avg_rank = (i + j + 1) / 2  # Average rank for ties
        for k in range(i, j):
            ranks.append((avg_rank, combined[k][1]))
        i = j

    # Sum ranks for group 1
    r1 = sum(r for r, g in ranks if g == 0)
    n1, n2 = len(group1), len(group2)

    # U statistic
    u1 = r1 - n1 * (n1 + 1) / 2
    u2 = n1 * n2 - u1
    u = min(u1, u2)

    # Normal approximation for p-value (valid for n1, n2 >= 10)
    mean_u = n1 * n2 / 2
    std_u = math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)

    if std_u == 0:
        return u, 1.0

    z = (u - mean_u) / std_u

    # Approximate p-value from z-score (two-tailed)
    # Using error function approximation
    p = 2 * (1 - _normal_cdf(abs(z)))

    return u, p


def _normal_cdf(z: float) -> float:
    """Approximate standard normal CDF using error function approximation."""
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


@dataclass
class HypothesisTestResult:
    """Result of a hypothesis test."""
    test_name: str
    statistic: float
    p_value: float
    significant: bool
    alpha: float = 0.05
    effect_size: Optional[float] = None
    effect_interpretation: Optional[str] = None
    conclusion: str = ""


def compare_scenarios(
    baseline: List[float],
    treatment: List[float],
    metric_name: str,
    alpha: float = 0.05
) -> HypothesisTestResult:
    """
    Compare two scenarios statistically.
    Returns comprehensive hypothesis test results.
    """
    # Effect size
    d, interpretation = calculate_effect_size(baseline, treatment)

    # Mann-Whitney U test (non-parametric, robust)
    u, p = mann_whitney_u(baseline, treatment)

    significant = p < alpha

    # Generate conclusion
    baseline_mean = statistics.mean(baseline) if baseline else 0
    treatment_mean = statistics.mean(treatment) if treatment else 0
    direction = "higher" if treatment_mean > baseline_mean else "lower"

    if significant:
        conclusion = (
            f"{metric_name} is significantly {direction} in treatment "
            f"(p={p:.4f}, Cohen's d={d:.2f} [{interpretation}])"
        )
    else:
        conclusion = (
            f"No significant difference in {metric_name} "
            f"(p={p:.4f}, Cohen's d={d:.2f} [{interpretation}])"
        )

    return HypothesisTestResult(
        test_name="Mann-Whitney U",
        statistic=u,
        p_value=p,
        significant=significant,
        alpha=alpha,
        effect_size=d,
        effect_interpretation=interpretation,
        conclusion=conclusion
    )


@dataclass
class SimulationAnalysis:
    """
    Comprehensive analysis of simulation runs.
    """
    # Raw data from multiple runs
    runs: List[dict] = field(default_factory=list)

    # Computed statistics
    project_completion_rate: Optional[DescriptiveStats] = None
    dispute_rate: Optional[DescriptiveStats] = None
    appeal_rate: Optional[DescriptiveStats] = None

    avg_work_quality: Optional[DescriptiveStats] = None
    avg_contractor_earnings: Optional[DescriptiveStats] = None
    avg_backer_roi: Optional[DescriptiveStats] = None

    total_value_transacted: Optional[DescriptiveStats] = None
    treasury_growth: Optional[DescriptiveStats] = None

    # Confidence intervals
    ci_completion_rate: Optional[ConfidenceInterval] = None
    ci_dispute_rate: Optional[ConfidenceInterval] = None
    ci_avg_quality: Optional[ConfidenceInterval] = None

    def analyze(self):
        """Compute all statistics from runs."""
        if not self.runs:
            return

        # Extract metrics from runs
        completion_rates = []
        dispute_rates = []
        appeal_rates = []
        qualities = []
        contractor_earnings = []
        backer_rois = []
        values = []
        treasuries = []

        for run in self.runs:
            projects = run.get("projects", {})
            completed = projects.get("completed", 0)
            disputed = projects.get("disputed", 0)
            appealed = projects.get("appealed", 0)
            total = projects.get("total", 1)

            completion_rates.append(completed / max(1, total))
            dispute_rates.append(disputed / max(1, completed))
            appeal_rates.append(appealed / max(1, disputed) if disputed > 0 else 0)

            quality = run.get("quality", {})
            qualities.append(quality.get("avg_work_quality", 0))

            agents = run.get("agents", {})
            contractor_earnings.append(agents.get("contractor_earnings", 0))

            financial = run.get("financial", {})
            values.append(financial.get("total_transacted", 0))
            treasuries.append(financial.get("treasury", 0))

        # Compute descriptive stats
        self.project_completion_rate = DescriptiveStats.from_data(completion_rates)
        self.dispute_rate = DescriptiveStats.from_data(dispute_rates)
        self.appeal_rate = DescriptiveStats.from_data(appeal_rates)
        self.avg_work_quality = DescriptiveStats.from_data(qualities)
        self.avg_contractor_earnings = DescriptiveStats.from_data(contractor_earnings)
        self.total_value_transacted = DescriptiveStats.from_data(values)
        self.treasury_growth = DescriptiveStats.from_data(treasuries)

        # Confidence intervals
        self.ci_completion_rate = calculate_confidence_interval(completion_rates)
        self.ci_dispute_rate = calculate_confidence_interval(dispute_rates)
        self.ci_avg_quality = calculate_confidence_interval(qualities)

    def summary(self) -> dict:
        """Return summary as dictionary."""
        return {
            "n_runs": len(self.runs),
            "completion_rate": {
                "mean": self.ci_completion_rate.estimate if self.ci_completion_rate else 0,
                "95% CI": (
                    self.ci_completion_rate.lower if self.ci_completion_rate else 0,
                    self.ci_completion_rate.upper if self.ci_completion_rate else 0
                ),
            },
            "dispute_rate": {
                "mean": self.ci_dispute_rate.estimate if self.ci_dispute_rate else 0,
                "95% CI": (
                    self.ci_dispute_rate.lower if self.ci_dispute_rate else 0,
                    self.ci_dispute_rate.upper if self.ci_dispute_rate else 0
                ),
            },
            "avg_quality": {
                "mean": self.ci_avg_quality.estimate if self.ci_avg_quality else 0,
                "95% CI": (
                    self.ci_avg_quality.lower if self.ci_avg_quality else 0,
                    self.ci_avg_quality.upper if self.ci_avg_quality else 0
                ),
            },
            "total_value": self.total_value_transacted.mean if self.total_value_transacted else 0,
            "treasury": self.treasury_growth.mean if self.treasury_growth else 0,
        }


@dataclass
class EfficacyMetrics:
    """
    Key metrics for evaluating system efficacy.
    """
    # Market efficiency
    transaction_completion_rate: float = 0.0  # % of projects completed
    market_liquidity: float = 0.0             # Value transacted per agent
    price_efficiency: float = 0.0             # How well pricing reflects quality

    # Incentive alignment
    honest_contractor_premium: float = 0.0    # Earnings premium for honest contractors
    reputation_correlation: float = 0.0       # Correlation between rep and outcomes
    dispute_deterrence: float = 0.0           # How well system deters bad behavior

    # Fairness
    gini_coefficient: float = 0.0             # Wealth inequality
    arbiter_accuracy: float = 0.0             # How close rulings are to true quality
    appeal_overturn_rate: float = 0.0         # % of appeals that are successful

    # Sustainability
    treasury_growth_rate: float = 0.0         # DAO treasury growth
    agent_retention: float = 0.0              # % of agents still active at end
    system_stability: float = 0.0             # Variance in key metrics over time

    @classmethod
    def compute(
        cls,
        runs: List[dict],
        contractor_data: List[dict],
        backer_data: List[dict]
    ) -> "EfficacyMetrics":
        """Compute efficacy metrics from simulation data."""
        metrics = cls()

        if not runs:
            return metrics

        # Transaction completion rate
        completion_rates = []
        for run in runs:
            projects = run.get("projects", {})
            completed = projects.get("completed", 0)
            total = projects.get("total", 1)
            completion_rates.append(completed / max(1, total))
        metrics.transaction_completion_rate = statistics.mean(completion_rates)

        # Market liquidity (value per agent)
        total_agents = len(contractor_data) + len(backer_data)
        if total_agents > 0:
            values = [r.get("financial", {}).get("total_transacted", 0) for r in runs]
            metrics.market_liquidity = statistics.mean(values) / total_agents

        # Honest contractor premium
        if contractor_data:
            honest_earnings = [
                c.get("total_earnings", 0)
                for c in contractor_data
                if c.get("strategy") == "honest"
            ]
            other_earnings = [
                c.get("total_earnings", 0)
                for c in contractor_data
                if c.get("strategy") != "honest"
            ]
            if honest_earnings and other_earnings:
                honest_mean = statistics.mean(honest_earnings)
                other_mean = statistics.mean(other_earnings)
                if other_mean > 0:
                    metrics.honest_contractor_premium = (honest_mean - other_mean) / other_mean

        # Dispute deterrence (inverse of dispute rate)
        dispute_rates = []
        for run in runs:
            projects = run.get("projects", {})
            disputed = projects.get("disputed", 0)
            completed = projects.get("completed", 1)
            dispute_rates.append(disputed / max(1, completed))
        avg_dispute_rate = statistics.mean(dispute_rates)
        metrics.dispute_deterrence = 1 - avg_dispute_rate

        # Gini coefficient for contractor earnings
        if contractor_data:
            earnings = sorted([c.get("total_earnings", 0) for c in contractor_data])
            n = len(earnings)
            if n > 0 and sum(earnings) > 0:
                numerator = sum((2 * i - n - 1) * e for i, e in enumerate(earnings, 1))
                denominator = n * sum(earnings)
                metrics.gini_coefficient = numerator / denominator

        # Arbiter accuracy
        arbiter_accuracies = [r.get("arbiter_accuracy", 0.8) for r in runs if "arbiter_accuracy" in r]
        if arbiter_accuracies:
            metrics.arbiter_accuracy = statistics.mean(arbiter_accuracies)

        # Appeal overturn rate
        appeal_rates = []
        for run in runs:
            projects = run.get("projects", {})
            appealed = projects.get("appealed", 0)
            disputed = projects.get("disputed", 1)
            if disputed > 0:
                appeal_rates.append(appealed / disputed)
        if appeal_rates:
            metrics.appeal_overturn_rate = statistics.mean(appeal_rates)

        # Treasury growth rate
        treasuries = [r.get("financial", {}).get("treasury", 0) for r in runs]
        if treasuries and len(treasuries) > 1:
            initial = treasuries[0] if treasuries[0] > 0 else 1
            final = treasuries[-1]
            metrics.treasury_growth_rate = (final - initial) / initial

        return metrics


def calculate_gini(values: List[float]) -> float:
    """Calculate Gini coefficient for inequality."""
    if not values or sum(values) == 0:
        return 0.0

    sorted_values = sorted(values)
    n = len(sorted_values)
    cumsum = 0
    total = sum(sorted_values)

    for i, v in enumerate(sorted_values):
        cumsum += (2 * (i + 1) - n - 1) * v

    return cumsum / (n * total)


def calculate_correlation(x: List[float], y: List[float]) -> float:
    """Calculate Pearson correlation coefficient."""
    if len(x) != len(y) or len(x) < 2:
        return 0.0

    n = len(x)
    mean_x = sum(x) / n
    mean_y = sum(y) / n

    numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    denom_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x))
    denom_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y))

    if denom_x * denom_y == 0:
        return 0.0

    return numerator / (denom_x * denom_y)
