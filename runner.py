"""
Simulation runner with Monte Carlo capabilities.
Orchestrates multiple simulation runs for statistical analysis.
"""
import time
import json
import random
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Callable, Any
from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing

from .core.parameters import SimulationConfig, EconomyParameters, SCENARIOS
from .core.economy import Economy
from .analysis.statistics import (
    SimulationAnalysis,
    EfficacyMetrics,
    compare_scenarios,
    calculate_confidence_interval,
    DescriptiveStats,
)


@dataclass
class RunResult:
    """Result of a single simulation run."""
    run_id: int
    seed: int
    config_name: str
    duration_seconds: float
    summary: dict
    contractor_data: List[dict] = field(default_factory=list)
    backer_data: List[dict] = field(default_factory=list)
    arbiter_data: List[dict] = field(default_factory=list)
    time_series: dict = field(default_factory=dict)


def run_single_simulation(
    config: SimulationConfig,
    seed: int,
    run_id: int = 0,
    config_name: str = "default",
    collect_agent_data: bool = True,
    progress_callback: Optional[Callable[[int, int], None]] = None
) -> RunResult:
    """
    Run a single simulation and return results.
    """
    start_time = time.time()

    # Create and initialize economy
    economy = Economy(
        params=config.economy_params,
        config=config
    )
    economy.initialize(seed=seed)

    # Run simulation
    for tick in range(config.num_ticks):
        economy.tick()

        if progress_callback and tick % 100 == 0:
            progress_callback(tick, config.num_ticks)

    # Collect results
    summary = economy.get_summary()

    # Collect agent data if requested
    contractor_data = []
    backer_data = []
    arbiter_data = []

    if collect_agent_data:
        for c in economy.contractors:
            contractor_data.append({
                "id": c.id,
                "strategy": c.strategy,
                "reputation": c.reputation,
                "total_earnings": c.total_earnings,
                "completed_projects": c.completed_projects,
                "successful_projects": c.successful_projects,
                "disputed_projects": c.disputed_projects,
                "success_rate": c.success_rate,
                "skill_level": c.skill_level,
            })

        for b in economy.backers:
            contractor_data.append({
                "id": b.id,
                "strategy": b.strategy,
                "reputation": b.reputation,
                "total_invested": b.total_invested,
                "total_returned": b.total_returned,
                "total_lost": b.total_lost,
                "roi": b.roi,
            })

        for a in economy.arbiters:
            arbiter_data.append({
                "id": a.id,
                "strategy": a.strategy,
                "reputation": a.reputation,
                "total_cases": a.total_cases,
                "overturned_cases": a.overturned_cases,
                "total_fees_earned": a.total_fees_earned,
                "overturn_rate": a.overturn_rate,
            })

    # Time series data
    time_series = {
        "projects_per_tick": economy.metrics.projects_per_tick,
        "disputes_per_tick": economy.metrics.disputes_per_tick,
        "value_per_tick": economy.metrics.value_per_tick,
    }

    duration = time.time() - start_time

    return RunResult(
        run_id=run_id,
        seed=seed,
        config_name=config_name,
        duration_seconds=duration,
        summary=summary,
        contractor_data=contractor_data,
        backer_data=backer_data,
        arbiter_data=arbiter_data,
        time_series=time_series,
    )


def _run_simulation_worker(args):
    """Worker function for parallel execution."""
    config, seed, run_id, config_name = args
    return run_single_simulation(config, seed, run_id, config_name, collect_agent_data=True)


@dataclass
class MonteCarloRunner:
    """
    Monte Carlo simulation runner for statistically rigorous analysis.
    """
    base_config: SimulationConfig = field(default_factory=SimulationConfig)
    n_runs: int = 30  # Default for statistical significance
    base_seed: int = 42
    parallel: bool = True
    max_workers: Optional[int] = None
    results_dir: Path = field(default_factory=lambda: Path("results"))

    # Results
    results: List[RunResult] = field(default_factory=list)
    analysis: Optional[SimulationAnalysis] = None

    def run(
        self,
        config_name: str = "default",
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> SimulationAnalysis:
        """
        Run Monte Carlo simulation with n_runs iterations.
        """
        self.results = []
        seeds = [self.base_seed + i for i in range(self.n_runs)]

        if self.parallel and self.n_runs > 1:
            # Parallel execution
            workers = self.max_workers or max(1, multiprocessing.cpu_count() - 1)
            args_list = [
                (self.base_config, seed, i, config_name)
                for i, seed in enumerate(seeds)
            ]

            with ProcessPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(_run_simulation_worker, args): i
                    for i, args in enumerate(args_list)
                }

                for future in as_completed(futures):
                    result = future.result()
                    self.results.append(result)

                    if progress_callback:
                        progress_callback(len(self.results), self.n_runs, config_name)
        else:
            # Sequential execution
            for i, seed in enumerate(seeds):
                result = run_single_simulation(
                    self.base_config,
                    seed,
                    i,
                    config_name
                )
                self.results.append(result)

                if progress_callback:
                    progress_callback(i + 1, self.n_runs, config_name)

        # Analyze results
        self.analysis = SimulationAnalysis(
            runs=[r.summary for r in self.results]
        )
        self.analysis.analyze()

        return self.analysis

    def run_parameter_sweep(
        self,
        parameter_name: str,
        values: List[Any],
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> Dict[Any, SimulationAnalysis]:
        """
        Run parameter sweep to test sensitivity.
        """
        results = {}

        for i, value in enumerate(values):
            # Create config with modified parameter
            config = SimulationConfig(**asdict(self.base_config))

            # Set parameter (handle nested parameters)
            if "." in parameter_name:
                parts = parameter_name.split(".")
                obj = config
                for part in parts[:-1]:
                    obj = getattr(obj, part)
                setattr(obj, parts[-1], value)
            else:
                setattr(config, parameter_name, value)

            # Run Monte Carlo
            runner = MonteCarloRunner(
                base_config=config,
                n_runs=self.n_runs,
                base_seed=self.base_seed,
                parallel=self.parallel,
                max_workers=self.max_workers,
            )
            analysis = runner.run(f"{parameter_name}={value}")
            results[value] = analysis

            if progress_callback:
                progress_callback(parameter_name, i + 1, len(values))

        return results

    def compare_scenarios(
        self,
        scenario_names: List[str],
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Compare multiple predefined scenarios.
        """
        scenario_results = {}

        for i, name in enumerate(scenario_names):
            if name not in SCENARIOS:
                print(f"Warning: Unknown scenario '{name}', skipping")
                continue

            config = SCENARIOS[name]
            runner = MonteCarloRunner(
                base_config=config,
                n_runs=self.n_runs,
                base_seed=self.base_seed,
                parallel=self.parallel,
                max_workers=self.max_workers,
            )
            analysis = runner.run(name)
            scenario_results[name] = {
                "analysis": analysis,
                "results": runner.results,
            }

            if progress_callback:
                progress_callback(name, i + 1, len(scenario_names))

        return scenario_results

    def save_results(self, filename: Optional[str] = None):
        """Save results to JSON file."""
        self.results_dir.mkdir(parents=True, exist_ok=True)

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"simulation_results_{timestamp}.json"

        filepath = self.results_dir / filename

        data = {
            "metadata": {
                "n_runs": self.n_runs,
                "base_seed": self.base_seed,
                "timestamp": datetime.now().isoformat(),
            },
            "config": {
                "num_ticks": self.base_config.num_ticks,
                "num_contractors": self.base_config.num_contractors,
                "num_backers": self.base_config.num_backers,
                "num_arbiters": self.base_config.num_arbiters,
            },
            "analysis": self.analysis.summary() if self.analysis else None,
            "runs": [
                {
                    "run_id": r.run_id,
                    "seed": r.seed,
                    "duration": r.duration_seconds,
                    "summary": r.summary,
                }
                for r in self.results
            ]
        }

        with open(filepath, "w") as f:
            json.dump(data, f, indent=2, default=str)

        print(f"Results saved to {filepath}")
        return filepath


def run_efficacy_analysis(
    config: SimulationConfig,
    n_runs: int = 30,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Run comprehensive efficacy analysis of the economic system.

    Returns detailed metrics with statistical significance.
    """
    # Run Monte Carlo simulation
    runner = MonteCarloRunner(
        base_config=config,
        n_runs=n_runs,
        base_seed=seed,
    )

    print(f"Running {n_runs} simulations...")
    analysis = runner.run("efficacy_analysis", lambda done, total, name: print(f"  {done}/{total}"))

    # Collect contractor data across all runs
    all_contractor_data = []
    all_backer_data = []
    for result in runner.results:
        all_contractor_data.extend(result.contractor_data)
        all_backer_data.extend(result.backer_data)

    # Compute efficacy metrics
    efficacy = EfficacyMetrics.compute(
        [r.summary for r in runner.results],
        all_contractor_data,
        all_backer_data
    )

    # Extract key metrics with confidence intervals
    results = {
        "n_runs": n_runs,
        "statistical_summary": analysis.summary(),
        "efficacy_metrics": {
            "transaction_completion_rate": efficacy.transaction_completion_rate,
            "market_liquidity": efficacy.market_liquidity,
            "honest_contractor_premium": efficacy.honest_contractor_premium,
            "dispute_deterrence": efficacy.dispute_deterrence,
            "gini_coefficient": efficacy.gini_coefficient,
            "arbiter_accuracy": efficacy.arbiter_accuracy,
            "treasury_growth_rate": efficacy.treasury_growth_rate,
        },
        "interpretation": {
            "system_effective": (
                efficacy.transaction_completion_rate > 0.7 and
                efficacy.dispute_deterrence > 0.7 and
                efficacy.honest_contractor_premium > 0
            ),
            "market_healthy": efficacy.gini_coefficient < 0.5,
            "incentives_aligned": efficacy.honest_contractor_premium > 0.1,
        }
    }

    return results


def compare_economic_parameters(
    baseline_config: SimulationConfig,
    parameter_variations: Dict[str, List[Any]],
    n_runs: int = 20,
    seed: int = 42
) -> Dict[str, Any]:
    """
    Compare different parameter settings to find optimal configuration.
    """
    results = {
        "baseline": None,
        "variations": {},
        "statistical_tests": {},
    }

    # Run baseline
    print("Running baseline...")
    baseline_runner = MonteCarloRunner(
        base_config=baseline_config,
        n_runs=n_runs,
        base_seed=seed,
    )
    baseline_analysis = baseline_runner.run("baseline")
    results["baseline"] = baseline_analysis.summary()

    # Run variations
    for param_name, values in parameter_variations.items():
        print(f"Testing parameter: {param_name}")
        results["variations"][param_name] = {}

        for value in values:
            # Create modified config
            config = SimulationConfig(**asdict(baseline_config))

            # Set parameter
            if "." in param_name:
                parts = param_name.split(".")
                obj = config
                for part in parts[:-1]:
                    obj = getattr(obj, part)
                setattr(obj, parts[-1], value)
            else:
                setattr(config, param_name, value)

            # Run
            runner = MonteCarloRunner(
                base_config=config,
                n_runs=n_runs,
                base_seed=seed,
            )
            analysis = runner.run(f"{param_name}={value}")

            results["variations"][param_name][str(value)] = analysis.summary()

            # Statistical comparison to baseline
            baseline_dispute_rates = [
                r.summary.get("projects", {}).get("disputed_rate", 0)
                for r in baseline_runner.results
            ]
            variation_dispute_rates = [
                r.summary.get("projects", {}).get("disputed_rate", 0)
                for r in runner.results
            ]

            test_result = compare_scenarios(
                baseline_dispute_rates,
                variation_dispute_rates,
                "dispute_rate"
            )

            if param_name not in results["statistical_tests"]:
                results["statistical_tests"][param_name] = {}

            results["statistical_tests"][param_name][str(value)] = {
                "p_value": test_result.p_value,
                "effect_size": test_result.effect_size,
                "significant": test_result.significant,
                "conclusion": test_result.conclusion,
            }

    return results
