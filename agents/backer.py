"""
Backer agent - provides capital and votes on project outcomes.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import random
import math

from .base import Agent, AgentProfile
from ..core.project import Project, VoteType, Contribution


class BackerStrategy:
    """Different backer behavioral strategies."""
    CONSERVATIVE = "conservative"       # Low risk, low immediate
    BALANCED = "balanced"               # Moderate approach
    AGGRESSIVE = "aggressive"           # High risk, high immediate
    REPUTATION_BASED = "reputation_based"  # Immediate based on contractor rep
    PASSIVE = "passive"                 # Rarely votes, follows majority


@dataclass
class Backer(Agent):
    """
    Backer agent that funds projects in the trustless economy.

    Key behaviors:
    - Decides which projects to fund
    - Chooses immediate vs locked split
    - Votes to release or dispute
    - Withdraws funds after resolution
    """
    strategy: str = BackerStrategy.BALANCED

    # Capital allocation
    max_single_investment: float = 0.2   # Max % of portfolio per project
    min_investment: float = 5.0          # Minimum contribution size
    target_utilization: float = 0.6      # Target % of capital deployed

    # Current state
    active_contributions: Dict[str, float] = field(default_factory=dict)  # project_id -> amount
    total_invested: float = 0.0
    total_returned: float = 0.0
    total_lost: float = 0.0

    # Decision parameters
    quality_threshold: float = 0.6       # Min quality to vote release
    dispute_threshold: float = 0.4       # Quality below which to dispute
    immediate_preference: float = 0.1    # Base immediate release preference

    def __post_init__(self):
        super().__post_init__()
        # Adjust parameters based on strategy
        if self.strategy == BackerStrategy.CONSERVATIVE:
            self.immediate_preference = 0.05
            self.risk_tolerance = 0.3
            self.quality_threshold = 0.7
        elif self.strategy == BackerStrategy.AGGRESSIVE:
            self.immediate_preference = 0.18
            self.risk_tolerance = 0.8
            self.quality_threshold = 0.5
        elif self.strategy == BackerStrategy.REPUTATION_BASED:
            # Immediate preference determined by contractor reputation
            self.immediate_preference = 0.1  # Base, adjusted per contractor
        elif self.strategy == BackerStrategy.PASSIVE:
            self.quality_threshold = 0.5
            self.rationality = 0.5  # Often doesn't vote optimally

    @property
    def available_capital(self) -> float:
        """Capital available for new investments."""
        total_balance = self.get_balance("native")
        current_invested = sum(self.active_contributions.values())
        return max(0, total_balance - current_invested)

    @property
    def current_utilization(self) -> float:
        """Current capital utilization rate."""
        total = self.get_balance("native") + sum(self.active_contributions.values())
        if total == 0:
            return 0
        return sum(self.active_contributions.values()) / total

    @property
    def roi(self) -> float:
        """Return on investment."""
        if self.total_invested == 0:
            return 0
        return (self.total_returned - self.total_invested) / self.total_invested

    def calculate_immediate_offer(
        self,
        contractor_reputation: float,
        contractor_success_rate: float,
        project_value: float,
        max_immediate_bps: int
    ) -> int:
        """
        Determine immediate release percentage to offer.

        Returns basis points (0-max_immediate_bps).
        """
        max_pct = max_immediate_bps / 10000

        if self.strategy == BackerStrategy.REPUTATION_BASED:
            # Immediate directly tied to contractor reputation
            # Higher rep = more trust = more immediate
            rep_factor = 1 / (1 + math.exp(-0.02 * (contractor_reputation - 100)))
            base_immediate = max_pct * rep_factor * 0.8  # Cap at 80% of max
        else:
            base_immediate = self.immediate_preference

        # Adjust for contractor success rate
        success_factor = contractor_success_rate if contractor_success_rate > 0 else 0.5
        adjusted = base_immediate * (0.5 + 0.5 * success_factor)

        # Strategy adjustments
        if self.strategy == BackerStrategy.CONSERVATIVE:
            adjusted *= 0.7
        elif self.strategy == BackerStrategy.AGGRESSIVE:
            adjusted *= 1.3

        # Add noise based on rationality
        noise = random.gauss(0, 0.02 * (1 - self.rationality))
        final = max(0, min(max_pct, adjusted + noise))

        return int(final * 10000)

    def should_fund_project(
        self,
        project_value: float,
        contractor_reputation: float,
        contractor_success_rate: float,
        num_other_backers: int,
        current_tick: int
    ) -> Tuple[bool, float]:
        """
        Decide whether to fund a project and how much.

        Returns: (should_fund, amount)
        """
        # Check capacity
        max_investment = self.get_balance("native") * self.max_single_investment
        if max_investment < self.min_investment:
            return False, 0

        # Check utilization target
        if self.current_utilization >= self.target_utilization:
            if random.random() > self.risk_tolerance:
                return False, 0

        # Evaluate contractor
        trust_score = self._evaluate_contractor_trust(
            contractor_reputation,
            contractor_success_rate
        )

        # Strategy-specific funding decisions
        if self.strategy == BackerStrategy.CONSERVATIVE:
            if trust_score < 0.6:
                return False, 0
            amount = min(max_investment, project_value * 0.2)  # Conservative amounts

        elif self.strategy == BackerStrategy.AGGRESSIVE:
            if trust_score < 0.3:
                return False, 0
            amount = min(max_investment, project_value * 0.5)  # Larger stakes

        elif self.strategy == BackerStrategy.REPUTATION_BASED:
            if trust_score < 0.4:
                return False, 0
            # Amount proportional to trust
            amount = min(max_investment, project_value * trust_score * 0.4)

        else:  # BALANCED or PASSIVE
            if trust_score < 0.4:
                return False, 0
            amount = min(max_investment, project_value * 0.3)

        # Ensure minimum investment
        if amount < self.min_investment:
            return False, 0

        return True, amount

    def _evaluate_contractor_trust(
        self,
        reputation: float,
        success_rate: float
    ) -> float:
        """
        Calculate trust score for a contractor.
        Returns value 0-1.
        """
        # Combine reputation and success rate
        rep_score = 1 / (1 + math.exp(-0.02 * (reputation - 50)))
        success_score = success_rate if success_rate > 0 else 0.5

        # Weight: 60% reputation, 40% success rate
        return 0.6 * rep_score + 0.4 * success_score

    def decide_vote(
        self,
        project: Project,
        observed_quality: float,
        other_votes: Dict[str, VoteType],
        current_tick: int
    ) -> VoteType:
        """
        Decide how to vote on a project.

        Args:
            project: The project being voted on
            observed_quality: Perceived quality of work (may differ from actual)
            other_votes: How other backers have voted
            current_tick: Current simulation tick
        """
        # Check if we have voting power
        contribution = project.contributions.get(self.id)
        if not contribution or contribution.voting_power == 0:
            return VoteType.NONE

        # Calculate perceived quality (with noise)
        noise = random.gauss(0, 0.1 * (1 - self.rationality))
        perceived_quality = max(0, min(1, observed_quality + noise))

        # Strategy-specific voting
        if self.strategy == BackerStrategy.PASSIVE:
            # Follow majority
            release_count = sum(1 for v in other_votes.values() if v == VoteType.RELEASE)
            dispute_count = sum(1 for v in other_votes.values() if v == VoteType.DISPUTE)
            if release_count > dispute_count:
                return VoteType.RELEASE
            elif dispute_count > release_count:
                return VoteType.DISPUTE
            # If tie, use quality threshold
            return VoteType.RELEASE if perceived_quality >= 0.5 else VoteType.DISPUTE

        # Quality-based voting
        if perceived_quality >= self.quality_threshold:
            return VoteType.RELEASE
        elif perceived_quality <= self.dispute_threshold:
            return VoteType.DISPUTE
        else:
            # Uncertain - probabilistic based on quality
            prob_release = (perceived_quality - self.dispute_threshold) / \
                          (self.quality_threshold - self.dispute_threshold)
            return VoteType.RELEASE if random.random() < prob_release else VoteType.DISPUTE

    def decide_appeal(
        self,
        arbitration_ruling: float,
        observed_quality: float,
        appeal_cost: float
    ) -> bool:
        """
        Decide whether to support a DAO appeal of arbitration.
        """
        # Expected fair outcome
        expected_contractor_share = observed_quality

        # If ruling is far from fair, support appeal
        deviation = abs(arbitration_ruling - expected_contractor_share)
        return deviation > 0.3 and random.random() < self.rationality

    def decide(self, context: dict) -> dict:
        """Generic decision interface."""
        decision_type = context.get("type")

        if decision_type == "fund_project":
            should_fund, amount = self.should_fund_project(
                context["project_value"],
                context["contractor_reputation"],
                context["contractor_success_rate"],
                context.get("num_other_backers", 0),
                context["current_tick"]
            )
            immediate_bps = self.calculate_immediate_offer(
                context["contractor_reputation"],
                context["contractor_success_rate"],
                context["project_value"],
                context["max_immediate_bps"]
            ) if should_fund else 0

            return {
                "fund": should_fund,
                "amount": amount,
                "immediate_bps": immediate_bps
            }

        elif decision_type == "vote":
            return {
                "vote": self.decide_vote(
                    context["project"],
                    context["observed_quality"],
                    context.get("other_votes", {}),
                    context["current_tick"]
                )
            }

        elif decision_type == "appeal":
            return {
                "support_appeal": self.decide_appeal(
                    context["arbitration_ruling"],
                    context["observed_quality"],
                    context.get("appeal_cost", 0)
                )
            }

        return {}


def create_backer_population(
    n: int,
    strategy_distribution: Optional[Dict[str, float]] = None,
    seed: Optional[int] = None
) -> List[Backer]:
    """
    Create a population of backers with varied strategies and capital.

    Args:
        n: Number of backers to create
        strategy_distribution: Dict mapping strategy -> probability
        seed: Random seed for reproducibility
    """
    if seed is not None:
        random.seed(seed)

    if strategy_distribution is None:
        strategy_distribution = {
            BackerStrategy.CONSERVATIVE: 0.3,
            BackerStrategy.BALANCED: 0.35,
            BackerStrategy.AGGRESSIVE: 0.15,
            BackerStrategy.REPUTATION_BASED: 0.15,
            BackerStrategy.PASSIVE: 0.05,
        }

    strategies = list(strategy_distribution.keys())
    weights = list(strategy_distribution.values())

    backers = []
    for i in range(n):
        strategy = random.choices(strategies, weights=weights)[0]

        # Vary individual traits
        backer = Backer(
            strategy=strategy,
            max_single_investment=random.uniform(0.1, 0.3),
            min_investment=random.uniform(3, 10),
            target_utilization=random.uniform(0.4, 0.8),
            risk_tolerance=random.uniform(0.2, 0.8),
            rationality=random.uniform(0.6, 1.0),
        )

        # Give initial capital (power law distribution - some whale backers)
        base_capital = random.uniform(100, 500)
        if random.random() < 0.1:  # 10% chance of being a whale
            base_capital *= random.uniform(3, 10)

        backer.balance["native"] = base_capital

        backers.append(backer)

    return backers
