"""
Contractor agent - provides services and earns through project completion.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import random
import math

from .base import Agent, AgentProfile


class ContractorStrategy:
    """Different contractor behavioral strategies."""
    HONEST = "honest"              # Always delivers quality work
    OPPORTUNISTIC = "opportunistic"  # Quality varies based on monitoring
    CAPITAL_CONSTRAINED = "capital_constrained"  # Needs high immediate %
    REPUTATION_BUILDER = "reputation_builder"  # Prioritizes rep over short-term gains
    MALICIOUS = "malicious"        # Tries to exploit the system


@dataclass
class Contractor(Agent):
    """
    Contractor agent that provides services in the trustless economy.

    Key behaviors:
    - Decides whether to take on projects
    - Determines work quality based on incentives
    - Stakes arbitration fees
    - Withdraws earnings
    """
    strategy: str = ContractorStrategy.HONEST

    # Capabilities
    skill_level: float = 0.8           # Base work quality capability
    capacity: int = 3                   # Max concurrent projects
    min_project_value: float = 10.0    # Minimum project size to consider

    # Current state
    active_projects: List[str] = field(default_factory=list)
    completed_projects: int = 0
    total_earnings: float = 0.0
    total_staked: float = 0.0

    # Strategy-specific parameters
    immediate_preference: float = 0.5   # Preferred immediate release %
    quality_effort_ratio: float = 0.8   # How much effort put into quality

    def __post_init__(self):
        super().__post_init__()
        # Adjust parameters based on strategy
        if self.strategy == ContractorStrategy.CAPITAL_CONSTRAINED:
            self.immediate_preference = 0.8
            self.risk_tolerance = 0.7
        elif self.strategy == ContractorStrategy.REPUTATION_BUILDER:
            self.immediate_preference = 0.2
            self.quality_effort_ratio = 1.0
        elif self.strategy == ContractorStrategy.MALICIOUS:
            self.honesty = 0.2
            self.immediate_preference = 0.9
        elif self.strategy == ContractorStrategy.OPPORTUNISTIC:
            self.honesty = 0.6
            self.quality_effort_ratio = 0.5

    @property
    def available_capacity(self) -> int:
        """Remaining capacity for new projects."""
        return max(0, self.capacity - len(self.active_projects))

    @property
    def reputation_factor(self) -> float:
        """
        Factor (0-1) representing trustworthiness based on reputation.
        Used by backers to determine immediate release %.
        """
        # Sigmoid function: reputation -> trust factor
        # At rep=0: ~0.27, at rep=100: ~0.73, at rep=500: ~0.99
        return 1 / (1 + math.exp(-0.02 * (self.reputation - 50)))

    def should_take_project(
        self,
        project_value: float,
        expected_immediate_pct: float,
        arbitration_fee: float,
        current_tick: int
    ) -> bool:
        """
        Decide whether to accept a project.

        Considers:
        - Current capacity
        - Project value vs minimum
        - Immediate release percentage
        - Required stake
        - Strategy-specific factors
        """
        # Basic constraints
        if self.available_capacity <= 0:
            return False
        if project_value < self.min_project_value:
            return False

        # Can afford the stake?
        stake_required = arbitration_fee / 2
        if self.get_balance("native") < stake_required:
            # Capital constrained - might still take if immediate covers stake
            immediate_amount = project_value * expected_immediate_pct
            if immediate_amount < stake_required:
                return False

        # Strategy-specific decisions
        if self.strategy == ContractorStrategy.CAPITAL_CONSTRAINED:
            # Need high immediate to cover operating costs
            if expected_immediate_pct < 0.15:
                return random.random() < 0.3  # Low chance
            return True

        elif self.strategy == ContractorStrategy.MALICIOUS:
            # Only take projects with high immediate (to take and run)
            return expected_immediate_pct >= 0.15

        elif self.strategy == ContractorStrategy.REPUTATION_BUILDER:
            # Take anything to build history
            return True

        else:
            # Honest/Opportunistic - standard decision
            # Expected value calculation
            expected_payout = project_value * (1 - 0.02)  # After fees
            risk = 1 - self.skill_level  # Risk of dispute
            expected_value = expected_payout * (1 - risk)

            return expected_value > stake_required

    def determine_work_quality(
        self,
        project_value: float,
        immediate_received: float,
        locked_amount: float,
        monitoring_level: float  # 0-1, how closely backers are watching
    ) -> float:
        """
        Determine actual work quality delivered.

        Quality depends on:
        - Skill level (capability)
        - Effort (strategy-dependent)
        - Incentives (locked vs immediate)
        - Monitoring
        """
        base_quality = self.skill_level * self.quality_effort_ratio

        if self.strategy == ContractorStrategy.HONEST:
            # Always deliver best quality
            return min(1.0, base_quality + random.gauss(0, 0.05))

        elif self.strategy == ContractorStrategy.MALICIOUS:
            # Minimal effort, especially if high immediate
            if immediate_received > locked_amount:
                return random.uniform(0.0, 0.3)
            return random.uniform(0.2, 0.5)

        elif self.strategy == ContractorStrategy.OPPORTUNISTIC:
            # Quality depends on monitoring and incentive structure
            incentive_factor = locked_amount / (project_value + 0.01)
            monitoring_factor = monitoring_level
            effort = (incentive_factor + monitoring_factor) / 2

            return min(1.0, base_quality * effort + random.gauss(0, 0.1))

        elif self.strategy == ContractorStrategy.REPUTATION_BUILDER:
            # Always high effort, even beyond skill
            return min(1.0, base_quality + 0.1 + random.gauss(0, 0.05))

        elif self.strategy == ContractorStrategy.CAPITAL_CONSTRAINED:
            # Try to deliver but may be rushed
            return min(1.0, base_quality * 0.9 + random.gauss(0, 0.1))

        return base_quality

    def decide_arbitration_response(
        self,
        project_value: float,
        work_quality: float,
        arbiter_reputation: float
    ) -> float:
        """
        When disputed, decide what share to propose/accept.
        Returns proposed contractor share (0-1).
        """
        # Base proposal on actual quality delivered
        fair_share = work_quality

        if self.strategy == ContractorStrategy.HONEST:
            # Accept fair outcome
            return fair_share

        elif self.strategy == ContractorStrategy.MALICIOUS:
            # Always claim 100%
            return 1.0

        else:
            # Add some noise based on rationality
            noise = random.gauss(0, 0.1 * (1 - self.rationality))
            return max(0.0, min(1.0, fair_share + noise))

    def decide(self, context: dict) -> dict:
        """Generic decision interface."""
        decision_type = context.get("type")

        if decision_type == "take_project":
            return {
                "accept": self.should_take_project(
                    context["project_value"],
                    context["expected_immediate_pct"],
                    context["arbitration_fee"],
                    context["current_tick"]
                )
            }

        elif decision_type == "work_quality":
            return {
                "quality": self.determine_work_quality(
                    context["project_value"],
                    context["immediate_received"],
                    context["locked_amount"],
                    context.get("monitoring_level", 0.5)
                )
            }

        elif decision_type == "arbitration":
            return {
                "proposed_share": self.decide_arbitration_response(
                    context["project_value"],
                    context["work_quality"],
                    context.get("arbiter_reputation", 0.5)
                )
            }

        return {}


def create_contractor_population(
    n: int,
    strategy_distribution: Optional[Dict[str, float]] = None,
    seed: Optional[int] = None
) -> List[Contractor]:
    """
    Create a population of contractors with varied strategies and traits.

    Args:
        n: Number of contractors to create
        strategy_distribution: Dict mapping strategy -> probability
        seed: Random seed for reproducibility
    """
    if seed is not None:
        random.seed(seed)

    if strategy_distribution is None:
        strategy_distribution = {
            ContractorStrategy.HONEST: 0.5,
            ContractorStrategy.OPPORTUNISTIC: 0.25,
            ContractorStrategy.CAPITAL_CONSTRAINED: 0.15,
            ContractorStrategy.REPUTATION_BUILDER: 0.05,
            ContractorStrategy.MALICIOUS: 0.05,
        }

    strategies = list(strategy_distribution.keys())
    weights = list(strategy_distribution.values())

    contractors = []
    for i in range(n):
        strategy = random.choices(strategies, weights=weights)[0]

        # Vary individual traits
        contractor = Contractor(
            strategy=strategy,
            skill_level=random.gauss(0.7, 0.15),
            capacity=random.randint(2, 5),
            min_project_value=random.uniform(5, 20),
            risk_tolerance=random.uniform(0.3, 0.8),
            rationality=random.uniform(0.7, 1.0),
            honesty=random.uniform(0.5, 1.0) if strategy != ContractorStrategy.MALICIOUS else random.uniform(0.1, 0.3),
        )

        # Give initial capital
        contractor.balance["native"] = random.uniform(50, 200)

        contractors.append(contractor)

    return contractors
