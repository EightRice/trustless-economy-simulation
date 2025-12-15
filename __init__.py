"""
Trustless Economy Game-Theory Simulation

A simulation framework for evaluating the efficacy of the Trustless Economy
smart contract system's incentive architecture.

Example usage:

    from simulation import run_quick_analysis, run_full_analysis

    # Quick analysis with fewer runs
    results = run_quick_analysis()

    # Full analysis with statistical significance
    results = run_full_analysis()

    # Compare scenarios
    from simulation import compare_all_scenarios
    comparison = compare_all_scenarios()
"""
from .core.parameters import (
    SimulationConfig,
    EconomyParameters,
    GovernanceParameters,
    TokenType,
    SCENARIOS,
)
from .core.project import Project, ProjectStage, VoteType, Contribution
from .core.economy import Economy, EconomyMetrics
from .agents import (
    Contractor,
    ContractorStrategy,
    Backer,
    BackerStrategy,
    Arbiter,
    ArbiterStrategy,
    DAOGovernance,
)
from .runner import (
    MonteCarloRunner,
    RunResult,
    run_single_simulation,
    run_efficacy_analysis,
    compare_economic_parameters,
)
from .analysis.statistics import (
    SimulationAnalysis,
    EfficacyMetrics,
    ConfidenceInterval,
    compare_scenarios,
)
from .analysis.visualization import TextReporter, DataExporter


def run_quick_analysis(
    n_runs: int = 10,
    num_ticks: int = 500,
    seed: int = 42
) -> dict:
    """
    Run a quick analysis suitable for rapid iteration.

    Returns summary statistics and efficacy metrics.
    """
    config = SimulationConfig(
        num_ticks=num_ticks,
        num_contractors=30,
        num_backers=60,
        num_arbiters=5,
        seed=seed,
    )

    return run_efficacy_analysis(config, n_runs=n_runs, seed=seed)


def run_full_analysis(
    n_runs: int = 30,
    num_ticks: int = 1000,
    seed: int = 42
) -> dict:
    """
    Run a full analysis with statistical significance.

    Uses 30 runs (minimum for statistical relevance) with longer duration.
    Returns comprehensive results with confidence intervals.
    """
    config = SimulationConfig(
        num_ticks=num_ticks,
        num_contractors=50,
        num_backers=100,
        num_arbiters=10,
        seed=seed,
    )

    return run_efficacy_analysis(config, n_runs=n_runs, seed=seed)


def compare_all_scenarios(
    n_runs: int = 20,
    seed: int = 42
) -> dict:
    """
    Compare all predefined scenarios.

    Returns analysis for each scenario plus statistical comparisons.
    """
    runner = MonteCarloRunner(
        base_config=SimulationConfig(),
        n_runs=n_runs,
        base_seed=seed,
    )

    scenario_names = ["baseline", "high_fees", "low_trust", "high_trust", "adversarial"]
    results = runner.compare_scenarios(
        scenario_names,
        progress_callback=lambda name, done, total: print(f"  Completed {name} ({done}/{total})")
    )

    return results


__all__ = [
    # Config
    "SimulationConfig",
    "EconomyParameters",
    "GovernanceParameters",
    "TokenType",
    "SCENARIOS",
    # Core
    "Project",
    "ProjectStage",
    "VoteType",
    "Contribution",
    "Economy",
    "EconomyMetrics",
    # Agents
    "Contractor",
    "ContractorStrategy",
    "Backer",
    "BackerStrategy",
    "Arbiter",
    "ArbiterStrategy",
    "DAOGovernance",
    # Runner
    "MonteCarloRunner",
    "RunResult",
    "run_single_simulation",
    "run_efficacy_analysis",
    "compare_economic_parameters",
    # Analysis
    "SimulationAnalysis",
    "EfficacyMetrics",
    "ConfidenceInterval",
    "compare_scenarios",
    "TextReporter",
    "DataExporter",
    # Quick functions
    "run_quick_analysis",
    "run_full_analysis",
    "compare_all_scenarios",
]
