"""
Economic parameters for the Trustless Economy simulation.
These mirror the on-chain configurable values from the smart contracts.
"""
from dataclasses import dataclass, field
from typing import Dict
from enum import Enum


class TokenType(Enum):
    """Supported token types in the economy."""
    NATIVE = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
    USDC = "USDC"
    CUSTOM = "CUSTOM"


@dataclass
class EconomyParameters:
    """
    Core economic parameters that govern the trustless economy.
    All basis points (bps) values: 10000 = 100%
    """
    # Fee structure
    platform_fee_bps: int = 100          # 1% - goes to DAO treasury
    author_fee_bps: int = 100            # 1% - goes to project author
    arbitration_fee_bps: int = 500       # 5% - paid to arbiter on disputes

    # Risk parameters
    max_immediate_bps: int = 2000        # 20% max immediate release
    backers_vote_quorum_bps: int = 7000  # 70% quorum for release/dispute

    # Time parameters (in simulation ticks, not seconds)
    cooling_off_period: int = 2          # Ticks before contractor can sign
    appeal_period: int = 7               # Ticks for DAO to appeal arbitration
    arbitration_timeout: int = 150       # Ticks before arbiter loses fee
    voting_period: int = 5               # Ticks for governance voting
    timelock_delay: int = 2              # Ticks before execution

    # Reputation parameters
    project_threshold_rep: float = 0.0   # Min rep to create projects

    # Token parities (reputation per unit of token)
    token_parities: Dict[str, float] = field(default_factory=lambda: {
        TokenType.NATIVE.value: 1.0,
        TokenType.USDC.value: 1.0,
    })

    def get_parity(self, token: str) -> float:
        """Get reputation parity for a token."""
        return self.token_parities.get(token, 1.0)


@dataclass
class GovernanceParameters:
    """Parameters for DAO governance."""
    proposal_threshold: float = 0.0      # Min rep to create proposal
    quorum_fraction: float = 0.04        # 4% quorum for proposals
    voting_delay: int = 1                # Ticks before voting starts
    voting_period: int = 5               # Ticks for voting
    timelock_delay: int = 2              # Ticks before execution


@dataclass
class SimulationConfig:
    """Configuration for a simulation run."""
    # Simulation duration
    num_ticks: int = 1000                # Total simulation ticks

    # Population sizes
    num_contractors: int = 50
    num_backers: int = 100
    num_arbiters: int = 10

    # Market parameters
    projects_per_tick: float = 2.0       # Average new projects per tick
    avg_project_value: float = 100.0     # Average project value
    project_value_std: float = 50.0      # Std dev of project values

    # Agent behavior parameters
    contractor_completion_rate: float = 0.85  # Base probability of completion
    backer_dispute_threshold: float = 0.3     # Quality threshold for disputes
    arbiter_fairness: float = 0.9             # Base probability of fair ruling

    # Randomness
    seed: int = 42                       # Random seed for reproducibility

    # Economic parameters
    economy_params: EconomyParameters = field(default_factory=EconomyParameters)
    governance_params: GovernanceParameters = field(default_factory=GovernanceParameters)


# Predefined scenarios for testing different economic conditions
SCENARIOS = {
    "baseline": SimulationConfig(),

    "high_fees": SimulationConfig(
        economy_params=EconomyParameters(
            platform_fee_bps=300,        # 3%
            author_fee_bps=200,          # 2%
            arbitration_fee_bps=1000,    # 10%
        )
    ),

    "low_trust": SimulationConfig(
        contractor_completion_rate=0.6,
        backer_dispute_threshold=0.5,
        economy_params=EconomyParameters(
            max_immediate_bps=1000,      # 10% max immediate
        )
    ),

    "high_trust": SimulationConfig(
        contractor_completion_rate=0.95,
        backer_dispute_threshold=0.2,
        economy_params=EconomyParameters(
            max_immediate_bps=4000,      # 40% max immediate
        )
    ),

    "adversarial": SimulationConfig(
        contractor_completion_rate=0.5,
        backer_dispute_threshold=0.6,
        arbiter_fairness=0.7,
        economy_params=EconomyParameters(
            arbitration_fee_bps=1000,    # 10% - higher stakes
            backers_vote_quorum_bps=5000,  # 50% quorum
        )
    ),

    "large_market": SimulationConfig(
        num_contractors=200,
        num_backers=500,
        num_arbiters=30,
        projects_per_tick=10.0,
        num_ticks=2000,
    ),
}
