"""
Project lifecycle state machine for the Trustless Economy simulation.
Models the full project lifecycle from creation to resolution.
"""
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, Optional, List, Tuple
import uuid


class ProjectStage(Enum):
    """Project lifecycle stages matching the smart contract."""
    OPEN = auto()        # Project created, accepting funding
    PENDING = auto()     # Parties set, waiting for contractor signature
    ONGOING = auto()     # Work in progress
    DISPUTE = auto()     # Disputed, waiting for arbitration
    APPEALABLE = auto()  # Arbiter ruled, can be appealed
    APPEAL = auto()      # DAO is reviewing appeal
    CLOSED = auto()      # Final state


class VoteType(Enum):
    """Types of votes backers can cast."""
    NONE = auto()
    RELEASE = auto()
    DISPUTE = auto()


@dataclass
class Contribution:
    """A backer's contribution to a project."""
    backer_id: str
    total_amount: float
    immediate_bps: int           # Basis points for immediate release
    vote: VoteType = VoteType.NONE
    withdrawn: bool = False

    @property
    def immediate_amount(self) -> float:
        """Amount released immediately to contractor."""
        return self.total_amount * (self.immediate_bps / 10000)

    @property
    def locked_amount(self) -> float:
        """Amount held in escrow."""
        return self.total_amount - self.immediate_amount

    @property
    def voting_power(self) -> float:
        """Only locked funds count for voting."""
        return self.locked_amount if not self.withdrawn else 0.0


@dataclass
class Project:
    """
    Represents a project in the trustless economy.
    Tracks the full state machine and all financial flows.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    token: str = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"

    # Parties
    author_id: Optional[str] = None
    contractor_id: Optional[str] = None
    arbiter_id: Optional[str] = None

    # Financial state
    contributions: Dict[str, Contribution] = field(default_factory=dict)
    contractor_stake: float = 0.0        # Half of arbitration fee
    arbiter_stake: float = 0.0           # Half of arbitration fee

    # Project state
    stage: ProjectStage = ProjectStage.OPEN
    created_tick: int = 0
    signed_tick: Optional[int] = None
    resolved_tick: Optional[int] = None

    # Quality (for simulation - represents actual work quality)
    actual_quality: float = 0.0          # 0.0 to 1.0

    # Arbitration
    arbitration_ruling: Optional[float] = None  # 0.0 to 1.0 (contractor's share)
    dao_overruled: bool = False
    dao_ruling: Optional[float] = None

    # Metadata
    description: str = ""
    target_value: float = 0.0            # Intended project value

    @property
    def total_contributed(self) -> float:
        """Total amount contributed by all backers."""
        return sum(c.total_amount for c in self.contributions.values())

    @property
    def total_immediate(self) -> float:
        """Total immediate funds (already released to contractor)."""
        return sum(c.immediate_amount for c in self.contributions.values())

    @property
    def total_locked(self) -> float:
        """Total locked funds in escrow."""
        return sum(c.locked_amount for c in self.contributions.values())

    @property
    def total_voting_power(self) -> float:
        """Total voting power (locked funds from non-withdrawn backers)."""
        return sum(c.voting_power for c in self.contributions.values())

    @property
    def release_votes(self) -> float:
        """Total voting power for release."""
        return sum(
            c.voting_power for c in self.contributions.values()
            if c.vote == VoteType.RELEASE
        )

    @property
    def dispute_votes(self) -> float:
        """Total voting power for dispute."""
        return sum(
            c.voting_power for c in self.contributions.values()
            if c.vote == VoteType.DISPUTE
        )

    def get_quorum_status(self, quorum_bps: int) -> Tuple[bool, bool]:
        """
        Check if release or dispute quorum has been reached.
        Returns: (release_reached, dispute_reached)
        """
        if self.total_voting_power == 0:
            return False, False

        quorum_threshold = self.total_voting_power * (quorum_bps / 10000)
        return (
            self.release_votes >= quorum_threshold,
            self.dispute_votes >= quorum_threshold
        )

    @property
    def arbitration_fee(self) -> float:
        """Total arbitration fee for this project."""
        # This would be calculated based on project value and arbitration_fee_bps
        # For now, we'll calculate it when needed in the economy
        return self.contractor_stake + self.arbiter_stake

    def can_transition_to(self, new_stage: ProjectStage) -> bool:
        """Check if transition to new stage is valid."""
        valid_transitions = {
            ProjectStage.OPEN: [ProjectStage.PENDING, ProjectStage.CLOSED],
            ProjectStage.PENDING: [ProjectStage.ONGOING, ProjectStage.OPEN, ProjectStage.CLOSED],
            ProjectStage.ONGOING: [ProjectStage.DISPUTE, ProjectStage.CLOSED],
            ProjectStage.DISPUTE: [ProjectStage.APPEALABLE, ProjectStage.CLOSED],
            ProjectStage.APPEALABLE: [ProjectStage.APPEAL, ProjectStage.CLOSED],
            ProjectStage.APPEAL: [ProjectStage.CLOSED],
            ProjectStage.CLOSED: [],
        }
        return new_stage in valid_transitions.get(self.stage, [])


@dataclass
class ProjectOutcome:
    """Records the final outcome of a completed project."""
    project_id: str
    stage_history: List[ProjectStage] = field(default_factory=list)

    # Financial outcomes
    contractor_payout: float = 0.0
    author_fee_earned: float = 0.0
    platform_fee_collected: float = 0.0
    arbiter_fee_earned: float = 0.0

    # Backer outcomes (backer_id -> amount recovered)
    backer_recoveries: Dict[str, float] = field(default_factory=dict)

    # Reputation changes
    contractor_reputation_delta: float = 0.0
    backer_reputation_deltas: Dict[str, float] = field(default_factory=dict)

    # Outcome classification
    was_disputed: bool = False
    was_appealed: bool = False
    was_successful: bool = False  # From contractor's perspective

    # Timing
    duration_ticks: int = 0
