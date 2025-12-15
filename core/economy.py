"""
Economy simulation engine - the marketplace that manages all projects.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import random
import math

from .parameters import EconomyParameters, SimulationConfig


from .project import Project, ProjectStage, VoteType, Contribution, ProjectOutcome
from ..agents.contractor import Contractor
from ..agents.backer import Backer
from ..agents.arbiter import Arbiter, DAOGovernance


def poisson_sample(lam: float, rng: random.Random) -> int:
    """Sample from Poisson distribution using inverse transform."""
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
class EconomyMetrics:
    """Metrics collected during simulation."""
    # Project metrics
    projects_created: int = 0
    projects_completed: int = 0
    projects_disputed: int = 0
    projects_appealed: int = 0
    projects_vetoed: int = 0

    # Financial metrics
    total_value_transacted: float = 0.0
    total_immediate_released: float = 0.0
    total_fees_collected: float = 0.0
    total_arbitration_fees: float = 0.0

    # Agent metrics
    contractor_earnings: float = 0.0
    backer_returns: float = 0.0
    arbiter_earnings: float = 0.0

    # Quality metrics
    average_work_quality: float = 0.0
    average_dispute_quality: float = 0.0  # Quality of disputed projects

    # Time series data
    projects_per_tick: List[int] = field(default_factory=list)
    disputes_per_tick: List[int] = field(default_factory=list)
    value_per_tick: List[float] = field(default_factory=list)


@dataclass
class Economy:
    """
    The main economy/marketplace simulation.

    Manages:
    - Project creation and lifecycle
    - Agent interactions
    - Financial flows
    - Reputation updates
    """
    params: EconomyParameters
    config: SimulationConfig

    # Agents
    contractors: List[Contractor] = field(default_factory=list)
    backers: List[Backer] = field(default_factory=list)
    arbiters: List[Arbiter] = field(default_factory=list)
    dao: DAOGovernance = field(default_factory=DAOGovernance)

    # State
    projects: Dict[str, Project] = field(default_factory=dict)
    completed_outcomes: List[ProjectOutcome] = field(default_factory=list)
    current_tick: int = 0

    # Metrics
    metrics: EconomyMetrics = field(default_factory=EconomyMetrics)

    # Random generator
    rng: random.Random = field(default_factory=random.Random)

    def initialize(self, seed: Optional[int] = None):
        """Initialize the economy with agents."""
        if seed is not None:
            self.rng.seed(seed)
            random.seed(seed)

        # Import here to avoid circular imports
        from ..agents.contractor import create_contractor_population
        from ..agents.backer import create_backer_population
        from ..agents.arbiter import create_arbiter_population

        self.contractors = create_contractor_population(
            self.config.num_contractors, seed=seed
        )
        self.backers = create_backer_population(
            self.config.num_backers, seed=seed
        )
        self.arbiters = create_arbiter_population(
            self.config.num_arbiters, seed=seed
        )

        # Initialize DAO with total reputation
        self.dao.total_reputation_supply = sum(
            c.reputation for c in self.contractors
        ) + sum(
            b.reputation for b in self.backers
        ) + sum(
            a.reputation for a in self.arbiters
        )

    def tick(self):
        """Advance simulation by one tick."""
        tick_projects = 0
        tick_disputes = 0
        tick_value = 0.0

        # 1. Create new projects
        num_new_projects = poisson_sample(self.config.projects_per_tick, self.rng)
        for _ in range(num_new_projects):
            project = self._create_project()
            if project:
                self.projects[project.id] = project
                tick_projects += 1
                tick_value += project.target_value
                self.metrics.projects_created += 1

        # 2. Process funding for open projects
        self._process_funding()

        # 3. Process contractor signing for pending projects
        self._process_signing()

        # 4. Determine work quality and voting for ongoing projects
        disputes = self._process_ongoing()
        tick_disputes += disputes

        # 5. Process arbitration for disputed projects
        self._process_arbitration()

        # 6. Process appeals for appealable projects
        self._process_appeals()

        # 7. Process withdrawals for closed projects
        self._process_withdrawals()

        # 8. Update reputation (periodic)
        if self.current_tick % 10 == 0:
            self._update_reputations()

        # Record metrics
        self.metrics.projects_per_tick.append(tick_projects)
        self.metrics.disputes_per_tick.append(tick_disputes)
        self.metrics.value_per_tick.append(tick_value)

        self.current_tick += 1

    def _create_project(self) -> Optional[Project]:
        """Create a new project with author and contractor."""
        # Select author (any backer with capital)
        eligible_authors = [b for b in self.backers if b.available_capital > 20]
        if not eligible_authors:
            return None

        author = self.rng.choice(eligible_authors)

        # Select contractor (available and interested)
        eligible_contractors = [
            c for c in self.contractors if c.available_capacity > 0
        ]
        if not eligible_contractors:
            return None

        contractor = self.rng.choice(eligible_contractors)

        # Determine project value
        value = max(10, self.rng.gauss(
            self.config.avg_project_value,
            self.config.project_value_std
        ))

        # Calculate arbitration fee
        arb_fee = value * (self.params.arbitration_fee_bps / 10000)

        # Check if contractor will take it
        expected_immediate = contractor.reputation_factor * (self.params.max_immediate_bps / 10000)
        if not contractor.should_take_project(value, expected_immediate, arb_fee, self.current_tick):
            return None

        # Create project
        project = Project(
            author_id=author.id,
            contractor_id=contractor.id,
            target_value=value,
            created_tick=self.current_tick,
            stage=ProjectStage.OPEN,
        )

        # Record project in profiles
        author.profile.projects_as_author.append(project.id)
        contractor.profile.projects_as_contractor.append(project.id)
        contractor.active_projects.append(project.id)

        return project

    def _process_funding(self):
        """Process backer funding for open projects."""
        open_projects = [
            p for p in self.projects.values()
            if p.stage == ProjectStage.OPEN
        ]

        for project in open_projects:
            contractor = self._get_contractor(project.contractor_id)
            if not contractor:
                continue

            # Get backers interested in funding
            for backer in self.backers:
                if project.id in backer.active_contributions:
                    continue  # Already contributed

                # Decide to fund
                decision = backer.decide({
                    "type": "fund_project",
                    "project_value": project.target_value,
                    "contractor_reputation": contractor.reputation,
                    "contractor_success_rate": contractor.success_rate,
                    "max_immediate_bps": self.params.max_immediate_bps,
                    "current_tick": self.current_tick,
                })

                if decision["fund"] and decision["amount"] > 0:
                    amount = min(decision["amount"], backer.available_capital)
                    immediate_bps = min(
                        decision["immediate_bps"],
                        self.params.max_immediate_bps
                    )

                    # Create contribution
                    contribution = Contribution(
                        backer_id=backer.id,
                        total_amount=amount,
                        immediate_bps=immediate_bps,
                    )
                    project.contributions[backer.id] = contribution

                    # Update backer state
                    backer.active_contributions[project.id] = amount
                    backer.total_invested += amount
                    backer.profile.projects_as_backer.append(project.id)

            # Check if project is sufficiently funded
            if project.total_contributed >= project.target_value * 0.8:
                project.stage = ProjectStage.PENDING

    def _process_signing(self):
        """Process contractor signing for pending projects."""
        pending_projects = [
            p for p in self.projects.values()
            if p.stage == ProjectStage.PENDING
        ]

        for project in pending_projects:
            # Check cooling off period
            if self.current_tick - project.created_tick < self.params.cooling_off_period:
                continue

            # Select arbiter
            available_arbiters = [
                a for a in self.arbiters if a.available_capacity > 0
            ]
            if not available_arbiters:
                continue

            arbiter = self.rng.choice(available_arbiters)
            arb_fee = project.total_contributed * (self.params.arbitration_fee_bps / 10000)

            if not arbiter.should_take_case(
                project.total_contributed,
                arb_fee,
                self._get_contractor(project.contractor_id).reputation if self._get_contractor(project.contractor_id) else 0,
                len(project.contributions)
            ):
                continue

            # Contractor stakes
            contractor = self._get_contractor(project.contractor_id)
            if not contractor:
                continue

            stake_amount = arb_fee / 2
            if not contractor.deduct_balance("native", stake_amount):
                continue

            project.contractor_stake = stake_amount
            contractor.total_staked += stake_amount

            # Arbiter stakes
            if not arbiter.deduct_balance("native", stake_amount):
                contractor.add_balance("native", stake_amount)
                project.contractor_stake = 0
                continue

            project.arbiter_stake = stake_amount
            project.arbiter_id = arbiter.id
            arbiter.active_cases.append(project.id)
            arbiter.profile.projects_as_arbiter.append(project.id)

            # Contractor receives immediate funds
            total_immediate = project.total_immediate
            contractor.add_balance("native", total_immediate)
            self.metrics.total_immediate_released += total_immediate

            project.signed_tick = self.current_tick
            project.stage = ProjectStage.ONGOING

    def _process_ongoing(self) -> int:
        """Process ongoing projects - work quality and voting."""
        disputes = 0
        ongoing_projects = [
            p for p in self.projects.values()
            if p.stage == ProjectStage.ONGOING
        ]

        for project in ongoing_projects:
            contractor = self._get_contractor(project.contractor_id)
            if not contractor:
                continue

            # Determine work quality (if not already set)
            if project.actual_quality == 0:
                project.actual_quality = contractor.determine_work_quality(
                    project.total_contributed,
                    project.total_immediate,
                    project.total_locked,
                    monitoring_level=len(project.contributions) / 10  # More backers = more monitoring
                )

            # Backers vote
            for backer_id, contribution in project.contributions.items():
                backer = self._get_backer(backer_id)
                if not backer or contribution.voting_power == 0:
                    continue

                # Observe quality (with noise)
                observed_quality = project.actual_quality + self.rng.gauss(0, 0.1)
                observed_quality = max(0, min(1, observed_quality))

                other_votes = {
                    bid: c.vote for bid, c in project.contributions.items()
                    if bid != backer_id
                }

                vote_decision = backer.decide({
                    "type": "vote",
                    "project": project,
                    "observed_quality": observed_quality,
                    "other_votes": other_votes,
                    "current_tick": self.current_tick,
                })

                contribution.vote = vote_decision["vote"]

            # Check quorum
            release_reached, dispute_reached = project.get_quorum_status(
                self.params.backers_vote_quorum_bps
            )

            if release_reached:
                project.stage = ProjectStage.CLOSED
                project.resolved_tick = self.current_tick
                self._finalize_successful_project(project)
            elif dispute_reached:
                project.stage = ProjectStage.DISPUTE
                disputes += 1
                self.metrics.projects_disputed += 1

        return disputes

    def _process_arbitration(self):
        """Process arbitration for disputed projects."""
        disputed_projects = [
            p for p in self.projects.values()
            if p.stage == ProjectStage.DISPUTE
        ]

        for project in disputed_projects:
            arbiter = self._get_arbiter(project.arbiter_id)
            if not arbiter:
                # Timeout - fee goes to treasury
                if project.signed_tick and self.current_tick - project.signed_tick > self.params.arbitration_timeout:
                    self.dao.treasury_balance += project.arbitration_fee
                    project.stage = ProjectStage.CLOSED
                    project.resolved_tick = self.current_tick
                    self._finalize_disputed_project(project, 0.5)  # Default 50-50
                continue

            # Wait for decision time
            if project.signed_tick and self.current_tick - project.signed_tick < arbiter.decision_time:
                continue

            # Arbiter rules
            contractor = self._get_contractor(project.contractor_id)
            contractor_rep = contractor.reputation if contractor else 0

            backer_total_rep = sum(
                self._get_backer(bid).reputation if self._get_backer(bid) else 0
                for bid in project.contributions.keys()
            )

            ruling = arbiter.determine_ruling(
                actual_quality=project.actual_quality,
                contractor_claim=1.0,  # Contractor claims 100%
                backer_claim=0.0,      # Backers claim 0%
                evidence_quality=0.7,
                contractor_reputation=contractor_rep,
                backer_total_reputation=backer_total_rep,
            )

            project.arbitration_ruling = ruling
            project.stage = ProjectStage.APPEALABLE

    def _process_appeals(self):
        """Process appeals for arbitrated projects."""
        appealable_projects = [
            p for p in self.projects.values()
            if p.stage == ProjectStage.APPEALABLE
        ]

        for project in appealable_projects:
            # Check appeal period
            if project.signed_tick and self.current_tick - project.signed_tick > self.params.appeal_period + 50:
                # No appeal, finalize
                project.stage = ProjectStage.CLOSED
                project.resolved_tick = self.current_tick
                self._finalize_disputed_project(project, project.arbitration_ruling)
                continue

            # Check if DAO should appeal (simplified - based on deviation)
            deviation = abs(project.arbitration_ruling - project.actual_quality)
            if deviation > 0.25 and self.rng.random() < 0.7:
                project.stage = ProjectStage.APPEAL
                self.metrics.projects_appealed += 1

                # DAO decides
                approved, new_ruling = self.dao.decide_appeal(
                    project.arbitration_ruling,
                    project.actual_quality,
                    0,  # appellant reputation
                    0.7,  # evidence
                    {}  # voters
                )

                if approved and new_ruling is not None:
                    project.dao_overruled = True
                    project.dao_ruling = new_ruling

                    # Arbiter loses fee
                    arbiter = self._get_arbiter(project.arbiter_id)
                    if arbiter:
                        arbiter.overturned_cases += 1
                        # Fee goes to treasury instead
                        self.dao.treasury_balance += project.arbitration_fee

                    project.stage = ProjectStage.CLOSED
                    project.resolved_tick = self.current_tick
                    self._finalize_disputed_project(project, new_ruling)
                else:
                    # Appeal rejected, use arbiter ruling
                    project.stage = ProjectStage.CLOSED
                    project.resolved_tick = self.current_tick
                    self._finalize_disputed_project(project, project.arbitration_ruling)

    def _process_withdrawals(self):
        """Process withdrawals for closed projects."""
        # Already handled in finalize methods
        pass

    def _finalize_successful_project(self, project: Project):
        """Finalize a successfully completed project."""
        contractor = self._get_contractor(project.contractor_id)
        if not contractor:
            return

        total_locked = project.total_locked
        platform_fee = total_locked * (self.params.platform_fee_bps / 10000)
        author_fee = (total_locked - platform_fee) * (self.params.author_fee_bps / 10000)
        contractor_payout = total_locked - platform_fee - author_fee

        # Distribute funds
        contractor.add_balance("native", contractor_payout)
        contractor.total_earnings += contractor_payout
        contractor.profile.record_earning("native", contractor_payout)
        contractor.successful_projects += 1
        contractor.completed_projects += 1
        if project.id in contractor.active_projects:
            contractor.active_projects.remove(project.id)

        # Return stakes
        contractor.add_balance("native", project.contractor_stake)

        # Author fee
        author = self._get_backer(project.author_id)
        if author:
            author.add_balance("native", author_fee)
            author.profile.record_earning("native", author_fee)

        # Platform fee
        self.dao.treasury_balance += platform_fee
        self.metrics.total_fees_collected += platform_fee

        # Arbiter gets stake back (no dispute)
        arbiter = self._get_arbiter(project.arbiter_id)
        if arbiter:
            arbiter.add_balance("native", project.arbiter_stake)
            if project.id in arbiter.active_cases:
                arbiter.active_cases.remove(project.id)

        # Update backer returns
        for backer_id, contribution in project.contributions.items():
            backer = self._get_backer(backer_id)
            if backer and backer_id in backer.active_contributions:
                del backer.active_contributions[project.id]
                backer.total_returned += contribution.total_amount  # Got value for money

        # Record metrics
        self.metrics.projects_completed += 1
        self.metrics.total_value_transacted += project.total_contributed
        self.metrics.contractor_earnings += contractor_payout

        # Update quality metrics
        n = self.metrics.projects_completed
        self.metrics.average_work_quality = (
            (self.metrics.average_work_quality * (n - 1) + project.actual_quality) / n
        )

        # Create outcome record
        outcome = ProjectOutcome(
            project_id=project.id,
            contractor_payout=contractor_payout,
            author_fee_earned=author_fee,
            platform_fee_collected=platform_fee,
            was_successful=True,
            duration_ticks=project.resolved_tick - project.created_tick if project.resolved_tick else 0,
        )
        self.completed_outcomes.append(outcome)

    def _finalize_disputed_project(self, project: Project, contractor_share: float):
        """Finalize a disputed project with the given contractor share."""
        contractor = self._get_contractor(project.contractor_id)
        total_locked = project.total_locked

        # Arbitration fee distribution
        arb_fee = project.arbitration_fee
        arbiter = self._get_arbiter(project.arbiter_id)

        if not project.dao_overruled and arbiter:
            # Arbiter gets the fee
            arbiter.add_balance("native", arb_fee)
            arbiter.total_fees_earned += arb_fee
            arbiter.profile.record_earning("native", arb_fee)
            arbiter.total_cases += 1
            self.metrics.arbiter_earnings += arb_fee
            if project.id in arbiter.active_cases:
                arbiter.active_cases.remove(project.id)

        # Split locked funds according to ruling
        contractor_amount = total_locked * contractor_share
        backer_refund = total_locked * (1 - contractor_share)

        # Apply platform fees to contractor portion
        platform_fee = contractor_amount * (self.params.platform_fee_bps / 10000)
        contractor_payout = contractor_amount - platform_fee

        if contractor:
            contractor.add_balance("native", contractor_payout)
            contractor.profile.record_earning("native", contractor_payout)
            contractor.disputed_projects += 1
            contractor.completed_projects += 1
            if project.id in contractor.active_projects:
                contractor.active_projects.remove(project.id)
            # Contractor loses stake (went to arb fee)
            self.metrics.contractor_earnings += contractor_payout

        # Platform fee
        self.dao.treasury_balance += platform_fee
        self.metrics.total_fees_collected += platform_fee
        self.metrics.total_arbitration_fees += arb_fee

        # Refund backers proportionally
        for backer_id, contribution in project.contributions.items():
            backer = self._get_backer(backer_id)
            if not backer:
                continue

            # Calculate backer's share of refund
            if total_locked > 0:
                backer_share = contribution.locked_amount / total_locked
            else:
                backer_share = 0

            refund = backer_refund * backer_share
            backer.add_balance("native", refund)
            backer.total_returned += refund

            # Record spending (lost amount)
            lost = contribution.locked_amount - refund
            if lost > 0:
                backer.profile.record_spending("native", lost)
                backer.total_lost += lost

            if project.id in backer.active_contributions:
                del backer.active_contributions[project.id]

        # Record metrics
        self.metrics.projects_completed += 1
        self.metrics.total_value_transacted += project.total_contributed
        n_disputes = self.metrics.projects_disputed
        if n_disputes > 0:
            self.metrics.average_dispute_quality = (
                (self.metrics.average_dispute_quality * (n_disputes - 1) + project.actual_quality) / n_disputes
            )

        # Create outcome record
        outcome = ProjectOutcome(
            project_id=project.id,
            contractor_payout=contractor_payout,
            platform_fee_collected=platform_fee,
            arbiter_fee_earned=arb_fee if not project.dao_overruled else 0,
            was_disputed=True,
            was_appealed=project.dao_overruled,
            was_successful=contractor_share > 0.5,
            duration_ticks=project.resolved_tick - project.created_tick if project.resolved_tick else 0,
        )
        self.completed_outcomes.append(outcome)

    def _update_reputations(self):
        """Update reputation for all agents."""
        parities = self.params.token_parities

        for contractor in self.contractors:
            contractor.claim_all_reputation(parities)

        for backer in self.backers:
            backer.claim_all_reputation(parities)

        for arbiter in self.arbiters:
            arbiter.claim_all_reputation(parities)

        # Update DAO total
        self.dao.total_reputation_supply = sum(
            c.reputation for c in self.contractors
        ) + sum(
            b.reputation for b in self.backers
        ) + sum(
            a.reputation for a in self.arbiters
        )

    def _get_contractor(self, contractor_id: Optional[str]) -> Optional[Contractor]:
        """Get contractor by ID."""
        if not contractor_id:
            return None
        for c in self.contractors:
            if c.id == contractor_id:
                return c
        return None

    def _get_backer(self, backer_id: Optional[str]) -> Optional[Backer]:
        """Get backer by ID."""
        if not backer_id:
            return None
        for b in self.backers:
            if b.id == backer_id:
                return b
        return None

    def _get_arbiter(self, arbiter_id: Optional[str]) -> Optional[Arbiter]:
        """Get arbiter by ID."""
        if not arbiter_id:
            return None
        for a in self.arbiters:
            if a.id == arbiter_id:
                return a
        return None

    def get_summary(self) -> dict:
        """Get summary statistics of the economy."""
        return {
            "tick": self.current_tick,
            "projects": {
                "total": self.metrics.projects_created,
                "completed": self.metrics.projects_completed,
                "disputed": self.metrics.projects_disputed,
                "disputed_rate": self.metrics.projects_disputed / max(1, self.metrics.projects_completed),
                "appealed": self.metrics.projects_appealed,
                "active": len([p for p in self.projects.values() if p.stage != ProjectStage.CLOSED]),
            },
            "financial": {
                "total_transacted": self.metrics.total_value_transacted,
                "immediate_released": self.metrics.total_immediate_released,
                "fees_collected": self.metrics.total_fees_collected,
                "treasury": self.dao.treasury_balance,
            },
            "agents": {
                "contractor_earnings": self.metrics.contractor_earnings,
                "arbiter_earnings": self.metrics.arbiter_earnings,
                "avg_contractor_rep": sum(c.reputation for c in self.contractors) / len(self.contractors) if self.contractors else 0,
                "avg_backer_rep": sum(b.reputation for b in self.backers) / len(self.backers) if self.backers else 0,
            },
            "quality": {
                "avg_work_quality": self.metrics.average_work_quality,
                "avg_dispute_quality": self.metrics.average_dispute_quality,
            },
        }
