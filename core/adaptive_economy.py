"""
Adaptive economy simulation with learning agents and DAO incentives.
Agents update their strategies based on observed outcomes.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import random
import math

from .parameters import EconomyParameters, SimulationConfig
from .project import Project, ProjectStage, VoteType, Contribution, ProjectOutcome
from ..agents.adaptive import (
    StrategyMemory,
    ReputationTracker,
    MarketEquilibriumTracker,
    DAOParticipationIncentives,
)


def poisson_sample(lam: float, rng: random.Random) -> int:
    """Sample from Poisson distribution."""
    if lam <= 0:
        return 0
    L = math.exp(-lam)
    k = 0
    p = 1.0
    while p > L:
        k += 1
        p *= rng.random()
    return k - 1


@dataclass
class AdaptiveContractor:
    """Contractor that learns optimal strategy over time."""
    id: str

    # Economic state
    balance: float = 100.0
    reputation: float = 0.0
    total_earnings: float = 0.0

    # Learning
    strategy_memory: StrategyMemory = field(default_factory=StrategyMemory)
    quality_history: List[Tuple[float, float]] = field(default_factory=list)  # (quality, reward)

    # Current strategy parameters (adapt over time)
    base_quality: float = 0.7
    quality_variance: float = 0.1

    # Capacity
    active_projects: List[str] = field(default_factory=list)
    max_projects: int = 3

    # Stats
    completed_projects: int = 0
    disputed_projects: int = 0
    successful_projects: int = 0

    def decide_quality(self, project_value: float, immediate_pct: float, locked_pct: float) -> float:
        """
        Decide work quality based on learned strategy.
        """
        # Get learned optimal quality
        action = self.strategy_memory.get_best_action(["low", "medium", "high"])

        target_quality = {
            "low": 0.4,
            "medium": 0.65,
            "high": 0.85,
        }.get(action, self.base_quality)

        # Adjust based on incentive structure
        # Higher locked % = more incentive for quality
        incentive_factor = 0.5 + 0.5 * locked_pct
        adjusted_quality = target_quality * incentive_factor

        # Add noise
        noise = random.gauss(0, self.quality_variance)
        final_quality = max(0, min(1, adjusted_quality + noise))

        return final_quality

    def learn_from_outcome(self, quality: float, payout: float, disputed: bool, project_value: float):
        """Update strategy based on project outcome.

        Key insight: Factor in reputation gains from quality.
        High quality = more reputation = more immediate release on future projects = less risk.
        """
        # Calculate direct reward (normalized)
        effort_cost = quality * 0.25 * project_value  # Slightly lower effort cost assumption
        dispute_penalty = 0.4 * project_value if disputed else 0

        # CRITICAL: Factor in reputation/trust value for future projects
        # High quality without disputes = reputation gain = future benefits
        # Reputation impacts future immediate release % (trust pricing)
        reputation_bonus = 0
        reputation_penalty = 0
        if not disputed:
            # Successful project: quality contributes strongly to future trust
            reputation_bonus = quality * 0.25 * project_value
        elif quality > 0.7:
            # High quality disputed: reputation still preserved
            reputation_bonus = quality * 0.10 * project_value

        # Penalty for low quality (reputation damage = future costs)
        if quality < 0.5:
            reputation_penalty = (0.5 - quality) * 0.15 * project_value

        reward = (payout - effort_cost - dispute_penalty + reputation_bonus - reputation_penalty) / max(project_value, 1)

        # Categorize action
        if quality < 0.5:
            action = "low"
        elif quality < 0.75:
            action = "medium"
        else:
            action = "high"

        self.strategy_memory.record_outcome(action, reward)
        self.strategy_memory.decay_exploration()

        # Track history
        self.quality_history.append((quality, reward))

        # Adapt base quality toward successful strategies
        if len(self.quality_history) > 10:
            recent = self.quality_history[-10:]
            best_quality = max(recent, key=lambda x: x[1])[0]
            # Slowly move toward best performing quality
            self.base_quality = 0.9 * self.base_quality + 0.1 * best_quality


@dataclass
class AdaptiveBacker:
    """Backer that learns optimal funding strategy."""
    id: str

    # Economic state
    balance: float = 200.0
    reputation: float = 0.0
    total_invested: float = 0.0
    total_returned: float = 0.0

    # Learning
    strategy_memory: StrategyMemory = field(default_factory=StrategyMemory)
    contractor_trust: Dict[str, float] = field(default_factory=dict)

    # Current strategy (adapts)
    base_immediate_pct: float = 0.1
    risk_tolerance: float = 0.5

    # Active investments
    active_investments: Dict[str, float] = field(default_factory=dict)

    def decide_funding(
        self,
        project_value: float,
        contractor_id: str,
        contractor_rep: float,
        max_immediate_bps: int
    ) -> Tuple[bool, float, int]:
        """
        Decide whether to fund and with what immediate %.
        Returns: (should_fund, amount, immediate_bps)

        Key insight: Higher reputation = more trust = higher immediate release.
        This creates positive feedback for quality contractors.
        """
        # Check capacity
        available = self.balance - sum(self.active_investments.values())
        if available < 10:
            return False, 0, 0

        # Get learned trust for this contractor (default 0.5 for unknown)
        learned_trust = self.contractor_trust.get(contractor_id, 0.5)

        # On-chain reputation has STRONG impact (key synergy mechanism)
        # Reputation grows from successful projects, so this rewards quality
        # Use steeper curve: low rep = much lower trust, high rep = high trust
        rep_factor = 1 / (1 + math.exp(-0.05 * (contractor_rep - 30)))

        # More weight to reputation as it builds (learning to trust the system)
        n_interactions = len([k for k in self.contractor_trust.keys()])
        rep_weight = min(0.7, 0.3 + n_interactions * 0.02)
        combined_trust = (1 - rep_weight) * learned_trust + rep_weight * rep_factor

        # Decide based on learned strategy
        action = self.strategy_memory.get_best_action(["conservative", "moderate", "aggressive"])

        # All strategies willing to fund, but trust threshold varies
        if action == "conservative":
            if combined_trust < 0.3:
                return False, 0, 0
            amount = min(available * 0.25, project_value * 0.25)
            # Conservative: lower immediate, but scales strongly with trust
            immediate_pct = 0.03 + 0.12 * combined_trust
        elif action == "moderate":
            if combined_trust < 0.2:
                return False, 0, 0
            amount = min(available * 0.35, project_value * 0.35)
            immediate_pct = 0.05 + 0.12 * combined_trust
        else:  # aggressive
            amount = min(available * 0.5, project_value * 0.5)
            # Aggressive: higher immediate for high-trust contractors
            immediate_pct = 0.08 + 0.12 * combined_trust

        # Cap immediate (but allow up to max for high-trust contractors)
        max_immediate = max_immediate_bps / 10000
        immediate_pct = min(immediate_pct, max_immediate)
        immediate_bps = int(immediate_pct * 10000)

        return True, amount, immediate_bps

    def learn_from_outcome(
        self,
        invested: float,
        returned: float,
        contractor_id: str,
        quality: float,
        immediate_pct: float,
        successful: bool
    ):
        """Update strategy based on outcome."""
        # Calculate ROI
        roi = (returned - invested) / max(invested, 1)

        # Categorize action
        if immediate_pct < 0.08:
            action = "conservative"
        elif immediate_pct < 0.14:
            action = "moderate"
        else:
            action = "aggressive"

        self.strategy_memory.record_outcome(action, roi)
        self.strategy_memory.decay_exploration()

        # Update contractor trust
        old_trust = self.contractor_trust.get(contractor_id, 0.5)
        outcome_score = quality if successful else quality * 0.3
        self.contractor_trust[contractor_id] = 0.7 * old_trust + 0.3 * outcome_score


@dataclass
class AdaptiveArbiter:
    """Arbiter that learns to rule fairly."""
    id: str

    balance: float = 300.0
    reputation: float = 0.0

    # Learning
    ruling_history: List[Tuple[float, float, bool]] = field(default_factory=list)  # (ruling, quality, overturned)

    # Stats
    total_cases: int = 0
    overturned_cases: int = 0
    fees_earned: float = 0.0

    # Strategy
    bias: float = 0.0  # Learned bias toward contractor (+) or backer (-)

    def make_ruling(self, observed_quality: float) -> float:
        """
        Decide ruling based on observed quality and learned bias.
        Returns contractor's share (0-1).
        """
        # Base ruling on quality
        ruling = observed_quality + self.bias

        # Add small noise
        noise = random.gauss(0, 0.05)
        ruling = max(0, min(1, ruling + noise))

        return ruling

    def learn_from_outcome(self, ruling: float, actual_quality: float, overturned: bool):
        """Update strategy based on whether ruling was overturned."""
        self.ruling_history.append((ruling, actual_quality, overturned))

        if overturned:
            self.overturned_cases += 1
            # Adjust bias toward fairness
            if ruling > actual_quality:
                self.bias -= 0.05  # Was too pro-contractor
            else:
                self.bias += 0.05  # Was too pro-backer

        # Decay bias toward 0 (fair) over time
        self.bias *= 0.95


@dataclass
class AdaptiveEconomyMetrics:
    """Metrics with time series for equilibrium detection."""
    # Per-tick metrics
    completion_rates: List[float] = field(default_factory=list)
    dispute_rates: List[float] = field(default_factory=list)
    quality_history: List[float] = field(default_factory=list)

    # Cumulative
    total_projects: int = 0
    completed_projects: int = 0
    disputed_projects: int = 0

    # Strategy distribution over time
    contractor_quality_targets: List[float] = field(default_factory=list)
    backer_immediate_offers: List[float] = field(default_factory=list)

    # Equilibrium tracking
    equilibrium_tick: Optional[int] = None


@dataclass
class AdaptiveEconomy:
    """
    Economy with adaptive agents that learn over time.
    Includes DAO participation incentives.
    """
    params: EconomyParameters

    # Agents
    contractors: List[AdaptiveContractor] = field(default_factory=list)
    backers: List[AdaptiveBacker] = field(default_factory=list)
    arbiters: List[AdaptiveArbiter] = field(default_factory=list)

    # Projects
    projects: Dict[str, Project] = field(default_factory=dict)

    # DAO incentives
    dao_incentives: DAOParticipationIncentives = field(default_factory=DAOParticipationIncentives)
    treasury: float = 0.0

    # Tracking
    metrics: AdaptiveEconomyMetrics = field(default_factory=AdaptiveEconomyMetrics)
    equilibrium_tracker: MarketEquilibriumTracker = field(default_factory=MarketEquilibriumTracker)

    # State
    current_tick: int = 0
    rng: random.Random = field(default_factory=random.Random)

    def initialize(self, num_contractors: int, num_backers: int, num_arbiters: int, seed: int = 42):
        """Initialize with agents."""
        self.rng.seed(seed)
        random.seed(seed)

        # Create contractors with varied initial strategies
        for i in range(num_contractors):
            c = AdaptiveContractor(
                id=f"C{i}",
                balance=self.rng.uniform(50, 150),
                base_quality=self.rng.uniform(0.5, 0.9),
                quality_variance=self.rng.uniform(0.05, 0.15),
            )
            # Vary initial exploration
            c.strategy_memory.epsilon = self.rng.uniform(0.1, 0.4)
            self.contractors.append(c)

        # Create backers
        for i in range(num_backers):
            b = AdaptiveBacker(
                id=f"B{i}",
                balance=self.rng.uniform(100, 400),
                base_immediate_pct=self.rng.uniform(0.05, 0.15),
                risk_tolerance=self.rng.uniform(0.3, 0.7),
            )
            b.strategy_memory.epsilon = self.rng.uniform(0.1, 0.4)
            self.backers.append(b)

        # Create arbiters
        for i in range(num_arbiters):
            a = AdaptiveArbiter(
                id=f"A{i}",
                balance=self.rng.uniform(200, 400),
                bias=self.rng.uniform(-0.1, 0.1),  # Slight initial bias
            )
            self.arbiters.append(a)

    def tick(self):
        """Run one simulation tick."""
        tick_completed = 0
        tick_disputed = 0
        tick_quality_sum = 0
        tick_quality_count = 0

        # 1. Create new projects
        num_new = poisson_sample(2.0, self.rng)
        for _ in range(num_new):
            self._create_project()

        # 2. Fund open projects
        self._process_funding()

        # 3. Sign and start projects
        self._process_signing()

        # 4. Process ongoing projects (work + voting)
        for project in list(self.projects.values()):
            if project.stage == ProjectStage.ONGOING:
                result = self._process_ongoing_project(project)
                if result:
                    if result["completed"]:
                        tick_completed += 1
                        tick_quality_sum += result["quality"]
                        tick_quality_count += 1
                    if result["disputed"]:
                        tick_disputed += 1

        # 5. Process disputes
        self._process_disputes()

        # 6. Process DAO epochs (passive income, delegate rewards)
        self._process_dao_epochs()

        # 7. Track metrics using cumulative rates (more stable)
        total_resolved = self.metrics.completed_projects + self.metrics.disputed_projects
        if total_resolved > 0:
            completion_rate = self.metrics.completed_projects / total_resolved
            dispute_rate = self.metrics.disputed_projects / total_resolved
        else:
            completion_rate = 0.5
            dispute_rate = 0.5

        # Quality: exponential moving average
        if tick_quality_count > 0:
            tick_avg_quality = tick_quality_sum / tick_quality_count
            if self.metrics.quality_history:
                avg_quality = 0.9 * self.metrics.quality_history[-1] + 0.1 * tick_avg_quality
            else:
                avg_quality = tick_avg_quality
        else:
            avg_quality = self.metrics.quality_history[-1] if self.metrics.quality_history else 0.7

        self.metrics.completion_rates.append(completion_rate)
        self.metrics.dispute_rates.append(dispute_rate)
        self.metrics.quality_history.append(avg_quality)

        # Track strategy evolution
        if self.contractors:
            avg_quality_target = sum(c.base_quality for c in self.contractors) / len(self.contractors)
            self.metrics.contractor_quality_targets.append(avg_quality_target)

        if self.backers:
            avg_immediate = sum(b.base_immediate_pct for b in self.backers) / len(self.backers)
            self.metrics.backer_immediate_offers.append(avg_immediate)

        # Check for equilibrium
        self.equilibrium_tracker.record_tick(completion_rate, dispute_rate, avg_quality)
        if self.equilibrium_tracker.is_equilibrium() and self.metrics.equilibrium_tick is None:
            self.metrics.equilibrium_tick = self.current_tick

        self.current_tick += 1

    def _create_project(self):
        """Create a new project."""
        # Select contractor with capacity
        available = [c for c in self.contractors if len(c.active_projects) < c.max_projects]
        if not available:
            return

        contractor = self.rng.choice(available)

        # Create project
        project_id = f"P{self.metrics.total_projects}"
        project = Project(
            id=project_id,
            contractor_id=contractor.id,
            target_value=self.rng.uniform(50, 150),
            created_tick=self.current_tick,
            stage=ProjectStage.OPEN,
        )

        self.projects[project_id] = project
        self.metrics.total_projects += 1

    def _process_funding(self):
        """Backers fund open projects."""
        open_projects = [p for p in self.projects.values() if p.stage == ProjectStage.OPEN]

        for project in open_projects:
            contractor = self._get_contractor(project.contractor_id)
            if not contractor:
                continue

            # Each backer considers funding with some probability
            potential_backers = [b for b in self.backers if project.id not in b.active_investments]
            # Sample more backers to get projects funded faster
            sample_size = min(15, len(potential_backers))
            if sample_size > 0:
                sampled_backers = self.rng.sample(potential_backers, sample_size)

                for backer in sampled_backers:
                    should_fund, amount, immediate_bps = backer.decide_funding(
                        project.target_value,
                        contractor.id,
                        contractor.reputation,
                        self.params.max_immediate_bps
                    )

                    if should_fund and amount > 0:
                        contribution = Contribution(
                            backer_id=backer.id,
                            total_amount=amount,
                            immediate_bps=immediate_bps,
                        )
                        project.contributions[backer.id] = contribution
                        backer.active_investments[project.id] = amount
                        backer.total_invested += amount

            # Check if funded enough
            if project.total_contributed >= project.target_value * 0.5:  # Lower threshold
                project.stage = ProjectStage.PENDING

            # Expire old unfunded projects
            if self.current_tick - project.created_tick > 20 and project.total_contributed < project.target_value * 0.3:
                # Refund any contributions and remove
                for backer_id, contrib in project.contributions.items():
                    backer = self._get_backer(backer_id)
                    if backer:
                        backer.balance += contrib.total_amount
                        if project.id in backer.active_investments:
                            del backer.active_investments[project.id]
                project.stage = ProjectStage.CLOSED

    def _process_signing(self):
        """Contractors sign projects, arbiters assigned."""
        pending = [p for p in self.projects.values() if p.stage == ProjectStage.PENDING]

        for project in pending:
            # Cooling off check
            if self.current_tick - project.created_tick < self.params.cooling_off_period:
                continue

            contractor = self._get_contractor(project.contractor_id)
            if not contractor:
                continue

            # Assign arbiter - count only active cases (not total historical)
            arbiter_active_cases = {}
            for proj in self.projects.values():
                if proj.stage in [ProjectStage.ONGOING, ProjectStage.DISPUTE, ProjectStage.APPEALABLE, ProjectStage.APPEAL]:
                    if proj.arbiter_id:
                        arbiter_active_cases[proj.arbiter_id] = arbiter_active_cases.get(proj.arbiter_id, 0) + 1

            available_arbiters = [a for a in self.arbiters if arbiter_active_cases.get(a.id, 0) < 5]
            if not available_arbiters:
                continue

            arbiter = self.rng.choice(available_arbiters)
            project.arbiter_id = arbiter.id

            # Calculate stakes
            arb_fee = project.total_contributed * (self.params.arbitration_fee_bps / 10000)
            stake = arb_fee / 2

            if contractor.balance >= stake and arbiter.balance >= stake:
                contractor.balance -= stake
                arbiter.balance -= stake
                project.contractor_stake = stake
                project.arbiter_stake = stake

                # Contractor receives immediate
                immediate = project.total_immediate
                contractor.balance += immediate

                contractor.active_projects.append(project.id)
                project.signed_tick = self.current_tick
                project.stage = ProjectStage.ONGOING

    def _process_ongoing_project(self, project: Project) -> Optional[dict]:
        """Process an ongoing project: work quality and voting."""
        contractor = self._get_contractor(project.contractor_id)
        if not contractor:
            return None

        # Determine quality (if not set)
        if project.actual_quality == 0:
            immediate_pct = project.total_immediate / max(project.total_contributed, 1)
            locked_pct = 1 - immediate_pct
            project.actual_quality = contractor.decide_quality(
                project.total_contributed,
                immediate_pct,
                locked_pct
            )

        # Backers vote based on observed quality
        observed_quality = project.actual_quality + self.rng.gauss(0, 0.1)
        observed_quality = max(0, min(1, observed_quality))

        for backer_id, contribution in project.contributions.items():
            if contribution.voting_power == 0:
                continue

            backer = self._get_backer(backer_id)
            if not backer:
                continue

            # Vote based on quality threshold (learned)
            threshold = 0.5 + 0.2 * (1 - backer.risk_tolerance)
            if observed_quality >= threshold:
                contribution.vote = VoteType.RELEASE
            else:
                contribution.vote = VoteType.DISPUTE

        # Check quorum
        release_reached, dispute_reached = project.get_quorum_status(self.params.backers_vote_quorum_bps)

        result = {"completed": False, "disputed": False, "quality": project.actual_quality}

        # Calculate time in ONGOING stage
        time_ongoing = self.current_tick - (project.signed_tick or self.current_tick)
        voting_deadline = 10  # Ticks allowed for voting

        if release_reached:
            self._complete_project(project, disputed=False)
            result["completed"] = True
            self.metrics.completed_projects += 1
        elif dispute_reached:
            project.stage = ProjectStage.DISPUTE
            result["disputed"] = True
            self.metrics.disputed_projects += 1
        elif time_ongoing >= voting_deadline:
            # Voting deadline reached - resolve based on majority vote
            release_votes = project.release_votes
            dispute_votes = project.dispute_votes

            if release_votes >= dispute_votes:
                # Majority voted release (or tie goes to contractor)
                self._complete_project(project, disputed=False)
                result["completed"] = True
                self.metrics.completed_projects += 1
            else:
                # Majority voted dispute
                project.stage = ProjectStage.DISPUTE
                result["disputed"] = True
                self.metrics.disputed_projects += 1

        return result

    def _process_disputes(self):
        """Process disputed projects through arbitration."""
        disputed = [p for p in self.projects.values() if p.stage == ProjectStage.DISPUTE]

        for project in disputed:
            arbiter = self._get_arbiter(project.arbiter_id)
            if not arbiter:
                continue

            # Arbiter makes ruling
            observed_quality = project.actual_quality + self.rng.gauss(0, 0.1)
            ruling = arbiter.make_ruling(observed_quality)
            project.arbitration_ruling = ruling

            # Check for DAO appeal (if ruling far from fair)
            deviation = abs(ruling - project.actual_quality)
            if deviation > 0.25 and self.rng.random() < 0.6:
                # DAO overturns
                project.dao_overruled = True
                project.dao_ruling = project.actual_quality + self.rng.gauss(0, 0.05)
                project.dao_ruling = max(0, min(1, project.dao_ruling))
                arbiter.learn_from_outcome(ruling, project.actual_quality, overturned=True)
            else:
                arbiter.learn_from_outcome(ruling, project.actual_quality, overturned=False)
                arbiter.fees_earned += project.arbitration_fee
                arbiter.balance += project.arbitration_fee

            self._complete_project(project, disputed=True)
            arbiter.total_cases += 1

    def _complete_project(self, project: Project, disputed: bool):
        """Complete a project and distribute rewards."""
        contractor = self._get_contractor(project.contractor_id)
        final_ruling = project.dao_ruling if project.dao_overruled else (project.arbitration_ruling if disputed else 1.0)

        locked = project.total_locked
        contractor_share = locked * final_ruling

        # Apply fees
        platform_fee = contractor_share * (self.params.platform_fee_bps / 10000)
        contractor_payout = contractor_share - platform_fee

        if contractor:
            contractor.balance += contractor_payout + project.contractor_stake
            contractor.total_earnings += contractor_payout
            contractor.completed_projects += 1
            if disputed:
                contractor.disputed_projects += 1
            else:
                contractor.successful_projects += 1

            if project.id in contractor.active_projects:
                contractor.active_projects.remove(project.id)

            # Learn from outcome
            contractor.learn_from_outcome(
                project.actual_quality,
                contractor_payout,
                disputed,
                project.total_contributed
            )

            # Update reputation
            contractor.reputation += contractor_payout * 0.01

        self.treasury += platform_fee

        # Refund backers
        backer_refund = locked * (1 - final_ruling)
        for backer_id, contribution in project.contributions.items():
            backer = self._get_backer(backer_id)
            if not backer:
                continue

            share = contribution.locked_amount / max(locked, 1)
            refund = backer_refund * share
            backer.balance += refund
            backer.total_returned += refund + contribution.immediate_amount * final_ruling

            if project.id in backer.active_investments:
                del backer.active_investments[project.id]

            # Learn from outcome
            backer.learn_from_outcome(
                contribution.total_amount,
                refund + contribution.immediate_amount,
                contractor.id if contractor else "",
                project.actual_quality,
                contribution.immediate_bps / 10000,
                not disputed
            )

            # Update reputation
            if not disputed:
                backer.reputation += contribution.total_amount * 0.005

        project.stage = ProjectStage.CLOSED
        project.resolved_tick = self.current_tick

    def _process_dao_epochs(self):
        """Process DAO participation incentives."""
        # Collect reputation balances
        rep_balances = {}
        for c in self.contractors:
            rep_balances[c.id] = c.reputation
        for b in self.backers:
            rep_balances[b.id] = b.reputation
        for a in self.arbiters:
            rep_balances[a.id] = a.reputation

        total_rep = sum(rep_balances.values())

        # Simplified delegation (assume some delegation exists)
        delegated_power = {k: v * 0.1 for k, v in rep_balances.items() if v > 50}

        # Process epochs
        self.dao_incentives.process_epoch(
            self.current_tick,
            rep_balances,
            delegated_power,
            total_rep
        )

        # Agents claim rewards periodically
        if self.current_tick % 50 == 0:
            for c in self.contractors:
                reward = self.dao_incentives.claim_rewards(c.id)
                c.balance += reward
                c.reputation += reward * 0.01
            for b in self.backers:
                reward = self.dao_incentives.claim_rewards(b.id)
                b.balance += reward
                b.reputation += reward * 0.01

    def _get_contractor(self, cid: str) -> Optional[AdaptiveContractor]:
        for c in self.contractors:
            if c.id == cid:
                return c
        return None

    def _get_backer(self, bid: str) -> Optional[AdaptiveBacker]:
        for b in self.backers:
            if b.id == bid:
                return b
        return None

    def _get_arbiter(self, aid: str) -> Optional[AdaptiveArbiter]:
        for a in self.arbiters:
            if a.id == aid:
                return a
        return None

    def get_summary(self) -> dict:
        """Get summary statistics."""
        # Calculate rolling averages for last 100 ticks
        window = 100
        recent_completion = self.metrics.completion_rates[-window:] if self.metrics.completion_rates else []
        recent_disputes = self.metrics.dispute_rates[-window:] if self.metrics.dispute_rates else []
        recent_quality = self.metrics.quality_history[-window:] if self.metrics.quality_history else []

        avg_completion = sum(recent_completion) / len(recent_completion) if recent_completion else 0
        avg_dispute = sum(recent_disputes) / len(recent_disputes) if recent_disputes else 0
        avg_quality = sum(recent_quality) / len(recent_quality) if recent_quality else 0

        # Strategy convergence
        quality_targets = self.metrics.contractor_quality_targets
        if len(quality_targets) > 100:
            early_quality = sum(quality_targets[:50]) / 50
            late_quality = sum(quality_targets[-50:]) / 50
            quality_convergence = late_quality - early_quality
        else:
            quality_convergence = 0

        return {
            "tick": self.current_tick,
            "equilibrium_reached": self.metrics.equilibrium_tick is not None,
            "equilibrium_tick": self.metrics.equilibrium_tick,
            "recent_metrics": {
                "completion_rate": avg_completion,
                "dispute_rate": avg_dispute,
                "avg_quality": avg_quality,
            },
            "cumulative": {
                "total_projects": self.metrics.total_projects,
                "completed": self.metrics.completed_projects,
                "disputed": self.metrics.disputed_projects,
            },
            "treasury": self.treasury,
            "strategy_evolution": {
                "quality_convergence": quality_convergence,
                "contractor_avg_quality": sum(c.base_quality for c in self.contractors) / len(self.contractors) if self.contractors else 0,
                "backer_avg_immediate": sum(b.base_immediate_pct for b in self.backers) / len(self.backers) if self.backers else 0,
            },
            "agent_stats": {
                "avg_contractor_reputation": sum(c.reputation for c in self.contractors) / len(self.contractors) if self.contractors else 0,
                "avg_backer_reputation": sum(b.reputation for b in self.backers) / len(self.backers) if self.backers else 0,
                "arbiter_accuracy": 1 - (sum(a.overturned_cases for a in self.arbiters) / max(1, sum(a.total_cases for a in self.arbiters))),
            }
        }
