"""
Arbiter agent - resolves disputes between contractors and backers.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import random
import math

from .base import Agent, AgentProfile


class ArbiterStrategy:
    """Different arbiter behavioral strategies."""
    FAIR = "fair"                    # Rules based on actual evidence
    CONTRACTOR_BIASED = "contractor_biased"  # Tends to favor contractors
    BACKER_BIASED = "backer_biased"  # Tends to favor backers
    SPLIT_THE_DIFFERENCE = "split"   # Always finds middle ground
    CORRUPT = "corrupt"              # Can be influenced


@dataclass
class Arbiter(Agent):
    """
    Arbiter agent that resolves disputes in the trustless economy.

    Key behaviors:
    - Decides whether to take arbitration cases
    - Rules on disputed projects (contractor's share 0-100%)
    - Stakes arbitration fee
    - Earns fee if ruling not overturned by DAO
    """
    strategy: str = ArbiterStrategy.FAIR

    # Capabilities
    expertise: float = 0.8             # Ability to assess true quality
    availability: float = 0.9          # Probability of accepting a case
    decision_time: int = 5             # Ticks to make a decision

    # Current state
    active_cases: List[str] = field(default_factory=list)
    max_concurrent_cases: int = 3
    total_cases: int = 0
    overturned_cases: int = 0
    total_fees_earned: float = 0.0

    # Bias parameters (used by biased strategies)
    bias_strength: float = 0.0         # How much to deviate from fair ruling

    def __post_init__(self):
        super().__post_init__()
        # Adjust parameters based on strategy
        if self.strategy == ArbiterStrategy.CONTRACTOR_BIASED:
            self.bias_strength = random.uniform(0.1, 0.3)
        elif self.strategy == ArbiterStrategy.BACKER_BIASED:
            self.bias_strength = random.uniform(-0.3, -0.1)
        elif self.strategy == ArbiterStrategy.CORRUPT:
            self.honesty = random.uniform(0.2, 0.5)

    @property
    def available_capacity(self) -> int:
        """Remaining capacity for new cases."""
        return max(0, self.max_concurrent_cases - len(self.active_cases))

    @property
    def overturn_rate(self) -> float:
        """Historical rate of decisions being overturned."""
        if self.total_cases == 0:
            return 0
        return self.overturned_cases / self.total_cases

    @property
    def reliability_score(self) -> float:
        """
        Score (0-1) representing arbiter reliability.
        Used by backers/contractors when choosing arbiters.
        """
        if self.total_cases < 3:
            return 0.5  # Prior belief for new arbiters
        return 1 - self.overturn_rate

    def should_take_case(
        self,
        project_value: float,
        arbitration_fee: float,
        contractor_reputation: float,
        num_backers: int
    ) -> bool:
        """
        Decide whether to accept an arbitration case.
        """
        # Check capacity
        if self.available_capacity <= 0:
            return False

        # Can afford the stake?
        stake_required = arbitration_fee / 2
        if self.get_balance("native") < stake_required:
            return False

        # Availability check
        if random.random() > self.availability:
            return False

        # Complexity assessment (more backers = more complex)
        complexity_factor = 1 + (num_backers - 1) * 0.1
        if complexity_factor > 2 and random.random() > self.expertise:
            return False  # Too complex

        return True

    def determine_ruling(
        self,
        actual_quality: float,
        contractor_claim: float,
        backer_claim: float,
        evidence_quality: float,  # 0-1, how clear the evidence is
        contractor_reputation: float,
        backer_total_reputation: float
    ) -> float:
        """
        Determine the ruling (contractor's share, 0-1).

        Args:
            actual_quality: True work quality (arbiter may not know this perfectly)
            contractor_claim: What contractor claims they deserve
            backer_claim: What backers claim contractor deserves
            evidence_quality: How clear the evidence is
            contractor_reputation: Contractor's reputation
            backer_total_reputation: Sum of backer reputations
        """
        # Perceive quality based on expertise and evidence
        perception_noise = random.gauss(0, 0.1 * (1 - self.expertise * evidence_quality))
        perceived_quality = max(0, min(1, actual_quality + perception_noise))

        # Strategy-specific ruling
        if self.strategy == ArbiterStrategy.FAIR:
            ruling = perceived_quality

        elif self.strategy == ArbiterStrategy.CONTRACTOR_BIASED:
            ruling = min(1.0, perceived_quality + self.bias_strength)

        elif self.strategy == ArbiterStrategy.BACKER_BIASED:
            ruling = max(0.0, perceived_quality + self.bias_strength)  # bias_strength is negative

        elif self.strategy == ArbiterStrategy.SPLIT_THE_DIFFERENCE:
            # Average of claims, weighted by perceived quality
            mid_point = (contractor_claim + backer_claim) / 2
            ruling = 0.5 * perceived_quality + 0.5 * mid_point

        elif self.strategy == ArbiterStrategy.CORRUPT:
            # Can be swayed by reputation (proxy for influence)
            total_rep = contractor_reputation + backer_total_reputation
            if total_rep > 0:
                contractor_influence = contractor_reputation / total_rep
            else:
                contractor_influence = 0.5

            # Mix perceived quality with influence
            ruling = self.honesty * perceived_quality + (1 - self.honesty) * contractor_influence

        else:
            ruling = perceived_quality

        # Add some randomness based on rationality
        noise = random.gauss(0, 0.05 * (1 - self.rationality))
        final_ruling = max(0, min(1, ruling + noise))

        return final_ruling

    def will_ruling_be_fair(
        self,
        ruling: float,
        actual_quality: float,
        tolerance: float = 0.2
    ) -> bool:
        """
        Check if a ruling is within tolerance of fair outcome.
        Used to predict DAO overturn.
        """
        return abs(ruling - actual_quality) <= tolerance

    def estimate_overturn_risk(
        self,
        ruling: float,
        actual_quality: float,
        dao_activity_level: float  # 0-1, how active the DAO is
    ) -> float:
        """
        Estimate probability of DAO overturning this ruling.
        """
        deviation = abs(ruling - actual_quality)

        # Base probability from deviation
        if deviation < 0.1:
            base_prob = 0.05
        elif deviation < 0.2:
            base_prob = 0.2
        elif deviation < 0.3:
            base_prob = 0.5
        else:
            base_prob = 0.8

        # Adjust for DAO activity
        return base_prob * dao_activity_level

    def decide(self, context: dict) -> dict:
        """Generic decision interface."""
        decision_type = context.get("type")

        if decision_type == "take_case":
            return {
                "accept": self.should_take_case(
                    context["project_value"],
                    context["arbitration_fee"],
                    context["contractor_reputation"],
                    context.get("num_backers", 1)
                )
            }

        elif decision_type == "rule":
            return {
                "ruling": self.determine_ruling(
                    context["actual_quality"],
                    context["contractor_claim"],
                    context["backer_claim"],
                    context.get("evidence_quality", 0.7),
                    context.get("contractor_reputation", 0),
                    context.get("backer_total_reputation", 0)
                )
            }

        return {}


@dataclass
class DAOGovernance:
    """
    Represents the DAO's collective governance for appeals and parameter changes.
    Not a single agent but an aggregate decision-making body.
    """
    # Governance parameters
    appeal_threshold: float = 0.5       # Min voting power to approve appeal
    proposal_threshold: float = 100     # Min rep to propose
    quorum_fraction: float = 0.04       # 4% quorum

    # State
    treasury_balance: float = 0.0
    total_reputation_supply: float = 0.0
    active_proposals: List[dict] = field(default_factory=list)

    # Statistics
    appeals_processed: int = 0
    appeals_approved: int = 0
    parameters_changed: int = 0

    def decide_appeal(
        self,
        arbitration_ruling: float,
        actual_quality: float,
        appellant_reputation: float,
        evidence_presented: float,  # Quality of evidence
        voter_composition: Dict[str, float]  # voter_id -> reputation
    ) -> tuple[bool, Optional[float]]:
        """
        DAO decides on an appeal.

        Returns: (approved, new_ruling if approved else None)
        """
        self.appeals_processed += 1

        # Calculate fair ruling
        fair_ruling = actual_quality

        # Deviation from fair
        deviation = abs(arbitration_ruling - fair_ruling)

        # Probability of approval based on deviation and evidence
        if deviation < 0.15:
            base_approval_prob = 0.1  # Minor deviation, likely uphold
        elif deviation < 0.25:
            base_approval_prob = 0.4
        elif deviation < 0.35:
            base_approval_prob = 0.7
        else:
            base_approval_prob = 0.9  # Major deviation, likely overturn

        # Adjust for evidence quality
        approval_prob = base_approval_prob * (0.5 + 0.5 * evidence_presented)

        # Simulate vote
        if random.random() < approval_prob:
            self.appeals_approved += 1
            # New ruling closer to fair
            noise = random.gauss(0, 0.05)
            new_ruling = max(0, min(1, fair_ruling + noise))
            return True, new_ruling

        return False, None

    def should_veto_project(
        self,
        project_value: float,
        suspicious_activity_score: float,  # 0-1
        reporter_reputation: float
    ) -> bool:
        """
        Decide if DAO should veto a suspicious project.
        """
        # Only veto highly suspicious projects
        threshold = 0.7 - (reporter_reputation / 1000)  # Higher rep reporters are more trusted
        return suspicious_activity_score > threshold


def create_arbiter_population(
    n: int,
    strategy_distribution: Optional[Dict[str, float]] = None,
    seed: Optional[int] = None
) -> List[Arbiter]:
    """
    Create a population of arbiters with varied strategies and expertise.

    Args:
        n: Number of arbiters to create
        strategy_distribution: Dict mapping strategy -> probability
        seed: Random seed for reproducibility
    """
    if seed is not None:
        random.seed(seed)

    if strategy_distribution is None:
        strategy_distribution = {
            ArbiterStrategy.FAIR: 0.6,
            ArbiterStrategy.CONTRACTOR_BIASED: 0.1,
            ArbiterStrategy.BACKER_BIASED: 0.1,
            ArbiterStrategy.SPLIT_THE_DIFFERENCE: 0.15,
            ArbiterStrategy.CORRUPT: 0.05,
        }

    strategies = list(strategy_distribution.keys())
    weights = list(strategy_distribution.values())

    arbiters = []
    for i in range(n):
        strategy = random.choices(strategies, weights=weights)[0]

        # Vary individual traits
        arbiter = Arbiter(
            strategy=strategy,
            expertise=random.gauss(0.75, 0.1),
            availability=random.uniform(0.7, 1.0),
            decision_time=random.randint(3, 10),
            max_concurrent_cases=random.randint(2, 5),
            rationality=random.uniform(0.7, 1.0),
        )

        # Give initial capital for staking
        arbiter.balance["native"] = random.uniform(200, 500)

        arbiters.append(arbiter)

    return arbiters
