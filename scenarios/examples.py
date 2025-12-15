"""
Example scenarios for testing specific hypotheses about the economic system.

These scenarios are designed to test edge cases and validate the robustness
of the incentive mechanisms under various conditions.
"""
from ..core.parameters import SimulationConfig, EconomyParameters, GovernanceParameters


# =============================================================================
# HYPOTHESIS TESTING SCENARIOS
# =============================================================================

# Hypothesis: Higher platform fees reduce market participation
HIGH_PLATFORM_FEES = SimulationConfig(
    economy_params=EconomyParameters(
        platform_fee_bps=500,  # 5% platform fee
        author_fee_bps=200,    # 2% author fee
    ),
    num_ticks=1000,
    num_contractors=50,
    num_backers=100,
)

# Hypothesis: Very low immediate cap forces more trust-building
MINIMAL_IMMEDIATE = SimulationConfig(
    economy_params=EconomyParameters(
        max_immediate_bps=500,  # Only 5% immediate allowed
    ),
    num_ticks=1000,
)

# Hypothesis: Higher quorum prevents minority exploitation
STRICT_QUORUM = SimulationConfig(
    economy_params=EconomyParameters(
        backers_vote_quorum_bps=9000,  # 90% quorum required
    ),
    num_ticks=1000,
)

# Hypothesis: High arbitration fees attract better arbiters
EXPENSIVE_ARBITRATION = SimulationConfig(
    economy_params=EconomyParameters(
        arbitration_fee_bps=1500,  # 15% arbitration fee
    ),
    num_ticks=1000,
)


# =============================================================================
# STRESS TEST SCENARIOS
# =============================================================================

# Test: Market with mostly malicious actors
HOSTILE_MARKET = SimulationConfig(
    contractor_completion_rate=0.4,
    backer_dispute_threshold=0.6,
    arbiter_fairness=0.6,
    economy_params=EconomyParameters(
        max_immediate_bps=1000,  # Limit exposure
        arbitration_fee_bps=1000,  # Higher stakes
    ),
    num_ticks=1000,
)

# Test: Rapid market growth
HYPERGROWTH = SimulationConfig(
    projects_per_tick=10.0,  # 5x normal rate
    avg_project_value=200.0,
    num_contractors=100,
    num_backers=300,
    num_arbiters=20,
    num_ticks=500,
)

# Test: Capital scarcity
LOW_LIQUIDITY = SimulationConfig(
    num_backers=20,  # Few backers
    projects_per_tick=0.5,  # Fewer projects
    avg_project_value=50.0,  # Smaller projects
    num_ticks=1000,
)


# =============================================================================
# COMPARISON SCENARIOS (for A/B testing)
# =============================================================================

# Baseline for all comparisons
COMPARISON_BASELINE = SimulationConfig(
    num_ticks=1000,
    num_contractors=50,
    num_backers=100,
    num_arbiters=10,
    seed=12345,  # Fixed seed for reproducibility
)

# A: Higher immediate cap
COMPARISON_HIGH_IMMEDIATE = SimulationConfig(
    economy_params=EconomyParameters(
        max_immediate_bps=4000,  # 40% vs 20%
    ),
    num_ticks=1000,
    num_contractors=50,
    num_backers=100,
    num_arbiters=10,
    seed=12345,
)

# B: Lower immediate cap
COMPARISON_LOW_IMMEDIATE = SimulationConfig(
    economy_params=EconomyParameters(
        max_immediate_bps=1000,  # 10% vs 20%
    ),
    num_ticks=1000,
    num_contractors=50,
    num_backers=100,
    num_arbiters=10,
    seed=12345,
)


# =============================================================================
# LONG-TERM STABILITY SCENARIOS
# =============================================================================

# Test reputation accumulation over many cycles
REPUTATION_MATURITY = SimulationConfig(
    num_ticks=5000,  # 5x longer
    num_contractors=30,
    num_backers=60,
    num_arbiters=5,
    projects_per_tick=1.0,  # Slower pace
)

# Test market concentration effects
MARKET_CONCENTRATION = SimulationConfig(
    num_contractors=10,  # Few contractors
    num_backers=200,     # Many backers
    num_ticks=2000,
    contractor_completion_rate=0.9,  # High completion to build reputation
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_all_scenarios() -> dict:
    """Return all defined scenarios as a dictionary."""
    return {
        # Hypothesis testing
        "high_platform_fees": HIGH_PLATFORM_FEES,
        "minimal_immediate": MINIMAL_IMMEDIATE,
        "strict_quorum": STRICT_QUORUM,
        "expensive_arbitration": EXPENSIVE_ARBITRATION,

        # Stress tests
        "hostile_market": HOSTILE_MARKET,
        "hypergrowth": HYPERGROWTH,
        "low_liquidity": LOW_LIQUIDITY,

        # A/B comparisons
        "comparison_baseline": COMPARISON_BASELINE,
        "comparison_high_immediate": COMPARISON_HIGH_IMMEDIATE,
        "comparison_low_immediate": COMPARISON_LOW_IMMEDIATE,

        # Long-term stability
        "reputation_maturity": REPUTATION_MATURITY,
        "market_concentration": MARKET_CONCENTRATION,
    }


def describe_scenario(name: str) -> str:
    """Return a description of what a scenario tests."""
    descriptions = {
        "high_platform_fees": "Tests market participation with 5% platform + 2% author fees",
        "minimal_immediate": "Tests trust dynamics with only 5% max immediate release",
        "strict_quorum": "Tests voting with 90% quorum requirement",
        "expensive_arbitration": "Tests arbiter quality with 15% arbitration fee",
        "hostile_market": "Stress test with mostly malicious/unreliable actors",
        "hypergrowth": "Tests system under rapid growth (5x project rate)",
        "low_liquidity": "Tests system with scarce capital and few backers",
        "comparison_baseline": "Baseline for A/B testing comparisons",
        "comparison_high_immediate": "A/B test: 40% max immediate (vs 20% baseline)",
        "comparison_low_immediate": "A/B test: 10% max immediate (vs 20% baseline)",
        "reputation_maturity": "Long-term test: 5000 ticks to observe reputation effects",
        "market_concentration": "Tests effects of few contractors dominating market",
    }
    return descriptions.get(name, "No description available")
