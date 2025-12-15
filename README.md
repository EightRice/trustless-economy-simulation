# Trustless Economy Game-Theory Simulation

A game-theoretic agent-based simulation framework for analyzing incentive alignment in decentralized marketplace mechanisms.

**Paper**: "Incentive Alignment in Trustless Economies: A Game-Theoretic Simulation of Decentralized Marketplace Mechanisms" (see `paper/` directory)

## Key Findings

- **Stable Equilibria**: 100% of simulation runs reach stable Nash equilibrium
- **Positive Quality Convergence**: Agents learn cooperative strategies over time (+2.0% quality improvement)
- **Enforcement Premium**: Traditional economies achieve ~4.8% lower dispute rates through external penalties (statistically significant, 95% CI: 3.7%–5.8%)
- **Effectiveness Ratio**: Trustless mechanisms capture ~85% of traditional enforcement effectiveness

## Overview

This simulation models the key actors and mechanisms of the trustless economy marketplace:

- **Contractors** - Service providers with different behavioral strategies
- **Backers** - Capital providers who fund projects and vote on outcomes
- **Arbiters** - Dispute resolvers who stake and rule on contested projects
- **DAO** - Collective governance for appeals and parameter management

The simulation tracks project lifecycles, reputation accrual, financial flows, and statistical outcomes to evaluate whether the incentive structure achieves its goals.

## Quick Start

```bash
# Run from the DAO root directory
cd C:\code\DAO

# Quick demo (10 runs, fast)
python -m simulation

# Full analysis (30 runs, statistically significant)
python -m simulation --full

# Compare predefined scenarios
python -m simulation --compare

# Parameter sensitivity analysis
python -m simulation --sweep fee
python -m simulation --sweep immediate
python -m simulation --sweep quorum
```

## Key Metrics Evaluated

### Market Efficiency
- **Transaction Completion Rate** - % of projects successfully completed
- **Market Liquidity** - Value transacted per agent

### Incentive Alignment
- **Honest Contractor Premium** - Earnings advantage for honest behavior
- **Dispute Deterrence** - How effectively the system prevents bad actors

### Fairness
- **Gini Coefficient** - Wealth inequality among participants
- **Arbiter Accuracy** - How close rulings are to true quality
- **Appeal Overturn Rate** - % of unfair rulings corrected

### Sustainability
- **Treasury Growth** - DAO fee accumulation
- **System Stability** - Variance in key metrics over time

## Architecture

```
simulation/
├── core/
│   ├── parameters.py    # Economic and simulation configuration
│   ├── project.py       # Project lifecycle state machine
│   └── economy.py       # Main marketplace simulation engine
├── agents/
│   ├── base.py          # Base agent class and profiles
│   ├── contractor.py    # Contractor strategies and behavior
│   ├── backer.py        # Backer strategies and behavior
│   └── arbiter.py       # Arbiter strategies and DAO governance
├── analysis/
│   ├── statistics.py    # Statistical tests and metrics
│   └── visualization.py # Reports and data export
├── scenarios/           # Predefined test scenarios
├── results/             # Output directory for results
├── runner.py            # Monte Carlo simulation runner
└── main.py              # CLI entry point
```

## Agent Strategies

### Contractors
| Strategy | Description |
|----------|-------------|
| `honest` | Always delivers quality work |
| `opportunistic` | Quality varies based on monitoring |
| `capital_constrained` | Needs high immediate release % |
| `reputation_builder` | Prioritizes rep over short-term gains |
| `malicious` | Attempts to exploit the system |

### Backers
| Strategy | Description |
|----------|-------------|
| `conservative` | Low risk, low immediate offers |
| `balanced` | Moderate approach |
| `aggressive` | Higher risk tolerance |
| `reputation_based` | Immediate % based on contractor rep |
| `passive` | Follows majority votes |

### Arbiters
| Strategy | Description |
|----------|-------------|
| `fair` | Rules based on actual evidence |
| `contractor_biased` | Tends to favor contractors |
| `backer_biased` | Tends to favor backers |
| `split_the_difference` | Always finds middle ground |
| `corrupt` | Can be influenced by reputation/power |

## Predefined Scenarios

```python
from simulation import SCENARIOS

# Available scenarios:
# - baseline: Default parameters
# - high_fees: Elevated platform fees (3%, 2%, 10%)
# - low_trust: Low completion rate, low max immediate
# - high_trust: High completion rate, high max immediate
# - adversarial: Hostile environment with malicious actors
# - large_market: Scaled up population for stress testing
```

## Statistical Methodology

The simulation uses rigorous statistical methods:

1. **Monte Carlo Sampling** - Multiple runs (default 30) for statistical power
2. **Confidence Intervals** - 95% CI for all key metrics
3. **Effect Size** - Cohen's d for comparing scenarios
4. **Non-parametric Tests** - Mann-Whitney U for robustness
5. **Sensitivity Analysis** - Parameter sweeps to identify optimal values

### Minimum Runs for Statistical Relevance

| Purpose | Recommended Runs |
|---------|-----------------|
| Quick exploration | 10 |
| Basic significance | 30 |
| High precision | 100 |
| Publication-quality | 1000 |

## API Usage

```python
from simulation import (
    SimulationConfig,
    EconomyParameters,
    Economy,
    MonteCarloRunner,
    run_efficacy_analysis,
)

# Custom configuration
config = SimulationConfig(
    num_ticks=1000,
    num_contractors=50,
    num_backers=100,
    num_arbiters=10,
    economy_params=EconomyParameters(
        platform_fee_bps=100,      # 1%
        arbitration_fee_bps=500,   # 5%
        max_immediate_bps=2000,    # 20%
    )
)

# Run analysis
results = run_efficacy_analysis(config, n_runs=30)

# Access results
print(f"Completion rate: {results['statistical_summary']['completion_rate']}")
print(f"System effective: {results['interpretation']['system_effective']}")
```

## Parameter Reference

### Economy Parameters

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `platform_fee_bps` | 100 | 0-1000 | Platform fee in basis points (1%) |
| `author_fee_bps` | 100 | 0-1000 | Author fee in basis points |
| `arbitration_fee_bps` | 500 | 0-2000 | Arbitration fee (5% of project value) |
| `max_immediate_bps` | 2000 | 0-5000 | Max immediate release (20%) |
| `backers_vote_quorum_bps` | 7000 | 5000-9500 | Voting quorum (70%) |
| `cooling_off_period` | 2 | 1-10 | Ticks before contractor can sign |
| `appeal_period` | 7 | 1-30 | Ticks for DAO appeal window |

### Simulation Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `num_ticks` | 1000 | Simulation duration |
| `num_contractors` | 50 | Number of contractor agents |
| `num_backers` | 100 | Number of backer agents |
| `num_arbiters` | 10 | Number of arbiter agents |
| `projects_per_tick` | 2.0 | Average new projects per tick |
| `avg_project_value` | 100 | Mean project value |
| `contractor_completion_rate` | 0.85 | Base completion probability |

## Output Files

Results are saved to the `results/` directory:

- `*_results.json` - Full simulation results
- `*_timeseries.json` - Time series data for plotting
- `*_agents.json` - Final agent state distributions
- `*.csv` - Tabular data for spreadsheet analysis

## Extending the Simulation

### Adding New Agent Strategies

```python
# In agents/contractor.py
class ContractorStrategy:
    MY_STRATEGY = "my_strategy"

# In Contractor class
def __post_init__(self):
    if self.strategy == ContractorStrategy.MY_STRATEGY:
        self.honesty = 0.7
        self.quality_effort_ratio = 0.9
```

### Adding New Scenarios

```python
# In core/parameters.py
SCENARIOS["my_scenario"] = SimulationConfig(
    economy_params=EconomyParameters(
        platform_fee_bps=200,
    ),
    contractor_completion_rate=0.9,
)
```

### Custom Analysis

```python
from simulation.analysis.statistics import (
    calculate_confidence_interval,
    compare_scenarios,
    calculate_gini,
)

# Custom statistical analysis
ci = calculate_confidence_interval(data, confidence=0.99)
test = compare_scenarios(baseline_data, treatment_data, "metric_name")
inequality = calculate_gini(earnings_list)
```

## Interpretation Guidelines

### Healthy System Indicators
- Completion rate > 70%
- Dispute rate < 15%
- Honest contractor premium > 10%
- Gini coefficient < 0.5
- Treasury growth positive

### Warning Signs
- Rising dispute rates over time
- Malicious strategies becoming profitable
- Decreasing average work quality
- Extreme wealth concentration

## Dependencies

The simulation uses only Python standard library:
- `dataclasses` - Data structures
- `random` - Stochastic simulation
- `math` - Statistical calculations
- `statistics` - Descriptive statistics
- `json` - Data serialization
- `pathlib` - File handling
- `concurrent.futures` - Parallel execution

No external dependencies required.

## License

Part of the Homebase DAO project. See main repository license.
