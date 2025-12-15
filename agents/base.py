"""
Base agent class and common agent functionality.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional
import uuid


@dataclass
class AgentProfile:
    """
    Economic profile tracking an agent's activity in the economy.
    Mirrors the on-chain UserProfile struct.
    """
    # Earnings and spendings by token
    earnings: Dict[str, float] = field(default_factory=dict)
    spendings: Dict[str, float] = field(default_factory=dict)

    # Claimed amounts (for reputation calculation)
    claimed_earnings: Dict[str, float] = field(default_factory=dict)
    claimed_spendings: Dict[str, float] = field(default_factory=dict)

    # Project history
    projects_as_author: List[str] = field(default_factory=list)
    projects_as_contractor: List[str] = field(default_factory=list)
    projects_as_arbiter: List[str] = field(default_factory=list)
    projects_as_backer: List[str] = field(default_factory=list)

    def record_earning(self, token: str, amount: float):
        """Record an earning event."""
        self.earnings[token] = self.earnings.get(token, 0.0) + amount

    def record_spending(self, token: str, amount: float):
        """Record a spending event (e.g., lost funds in dispute)."""
        self.spendings[token] = self.spendings.get(token, 0.0) + amount

    def get_unclaimed_earnings(self, token: str) -> float:
        """Get earnings not yet claimed as reputation."""
        return self.earnings.get(token, 0.0) - self.claimed_earnings.get(token, 0.0)

    def get_unclaimed_spendings(self, token: str) -> float:
        """Get spendings not yet claimed as reputation."""
        return self.spendings.get(token, 0.0) - self.claimed_spendings.get(token, 0.0)

    def claim_reputation(self, token: str) -> tuple[float, float]:
        """
        Claim unclaimed earnings/spendings for reputation.
        Returns: (unclaimed_earnings, unclaimed_spendings)
        """
        unclaimed_earn = self.get_unclaimed_earnings(token)
        unclaimed_spend = self.get_unclaimed_spendings(token)

        self.claimed_earnings[token] = self.earnings.get(token, 0.0)
        self.claimed_spendings[token] = self.spendings.get(token, 0.0)

        return unclaimed_earn, unclaimed_spend


@dataclass
class Agent(ABC):
    """
    Base class for all agents in the simulation.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""

    # Economic state
    profile: AgentProfile = field(default_factory=AgentProfile)
    reputation: float = 0.0
    balance: Dict[str, float] = field(default_factory=dict)  # Token balances

    # Behavioral parameters (agent-specific traits)
    risk_tolerance: float = 0.5          # 0 = risk-averse, 1 = risk-seeking
    rationality: float = 0.9             # Probability of making optimal decision
    honesty: float = 0.9                 # Probability of acting honestly

    # Statistics
    total_projects: int = 0
    successful_projects: int = 0
    disputed_projects: int = 0

    def __post_init__(self):
        if not self.name:
            self.name = f"{self.__class__.__name__}_{self.id}"

    def get_balance(self, token: str) -> float:
        """Get balance for a specific token."""
        return self.balance.get(token, 0.0)

    def add_balance(self, token: str, amount: float):
        """Add to balance (e.g., from project payout)."""
        self.balance[token] = self.get_balance(token) + amount

    def deduct_balance(self, token: str, amount: float) -> bool:
        """Deduct from balance if sufficient. Returns success."""
        if self.get_balance(token) >= amount:
            self.balance[token] -= amount
            return True
        return False

    @property
    def success_rate(self) -> float:
        """Historical success rate."""
        if self.total_projects == 0:
            return 0.5  # Prior belief
        return self.successful_projects / self.total_projects

    @property
    def dispute_rate(self) -> float:
        """Historical dispute rate."""
        if self.total_projects == 0:
            return 0.0
        return self.disputed_projects / self.total_projects

    def claim_all_reputation(self, token_parities: Dict[str, float]) -> float:
        """
        Claim reputation from all unclaimed economic activity.
        Returns total new reputation minted.
        """
        total_new_rep = 0.0
        for token in set(self.profile.earnings.keys()) | set(self.profile.spendings.keys()):
            parity = token_parities.get(token, 1.0)
            unclaimed_earn, unclaimed_spend = self.profile.claim_reputation(token)
            # Net reputation: earnings increase rep, spendings decrease
            new_rep = (unclaimed_earn - unclaimed_spend) * parity
            total_new_rep += new_rep

        self.reputation = max(0.0, self.reputation + total_new_rep)
        return total_new_rep

    @abstractmethod
    def decide(self, context: dict) -> dict:
        """
        Make a decision based on context.
        Override in subclasses to implement agent-specific behavior.
        """
        pass
