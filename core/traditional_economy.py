"""
Traditional economy model with legal jurisdiction enforcement.
Compares to trustless model by adding external penalty mechanisms.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import random
import math

from .parameters import EconomyParameters
from .project import Project, ProjectStage, VoteType, Contribution
from .adaptive_economy import (
    AdaptiveContractor,
    AdaptiveBacker,
    AdaptiveArbiter,
    AdaptiveEconomyMetrics,
    poisson_sample,
)
from ..agents.adaptive import MarketEquilibriumTracker


@dataclass
class TraditionalContractor(AdaptiveContractor):
    """
    Contractor in traditional economy with external liability exposure.

    Key difference: Can lose assets OUTSIDE the contract through:
    - Lawsuits for damages
    - Credit score damage affecting all financial dealings
    - Professional license revocation
    - Criminal penalties for fraud
    """
    # External assets that can be seized
    external_assets: float = 500.0

    # Credit score (affects ability to get future contracts everywhere)
    credit_score: float = 700.0

    # Professional license status
    licensed: bool = True
    license_violations: int = 0

    def calculate_external_risk(self, project_value: float, quality: float) -> float:
        """
        Calculate expected external penalty for low quality work.
        In traditional systems, bad actors face penalties beyond contract scope.
        """
        if quality >= 0.6:
            return 0  # Good quality = no external risk

        # Probability of lawsuit increases with poor quality
        lawsuit_prob = (0.6 - quality) * 0.5  # Up to 30% lawsuit chance

        # Expected damages: can exceed contract value
        damage_multiplier = 1.5 + (0.6 - quality) * 2  # 1.5x to 2.7x contract value
        expected_damages = lawsuit_prob * damage_multiplier * project_value

        # Credit score damage (affects ALL future dealings)
        credit_damage_cost = (0.6 - quality) * 50  # Up to 30 point damage

        # License risk
        license_risk = 0
        if quality < 0.4 and self.license_violations >= 2:
            license_risk = 200  # Cost of losing license

        return expected_damages + credit_damage_cost + license_risk

    def decide_quality_traditional(
        self,
        project_value: float,
        immediate_pct: float,
        locked_pct: float
    ) -> float:
        """
        Decide quality considering external enforcement.
        Traditional contractors face more severe penalties for bad work.
        """
        # Get base strategy
        action = self.strategy_memory.get_best_action(["low", "medium", "high"])

        base_quality = {
            "low": 0.4,
            "medium": 0.65,
            "high": 0.85,
        }.get(action, self.base_quality)

        # CRITICAL: Adjust for external risk
        # Calculate expected penalty for each quality level
        low_risk = self.calculate_external_risk(project_value, 0.4)
        med_risk = self.calculate_external_risk(project_value, 0.65)
        high_risk = self.calculate_external_risk(project_value, 0.85)

        # If external risk significantly outweighs effort savings, increase quality
        effort_savings = (0.85 - 0.4) * 0.25 * project_value
        if low_risk > effort_savings * 1.5:
            # External penalties make low quality unprofitable
            base_quality = max(base_quality, 0.6)

        # Incentive factor from locked funds
        incentive_factor = 0.5 + 0.5 * locked_pct
        adjusted_quality = base_quality * incentive_factor

        # Add noise
        noise = random.gauss(0, self.quality_variance)
        final_quality = max(0, min(1, adjusted_quality + noise))

        return final_quality

    def apply_external_penalty(self, quality: float, project_value: float, disputed: bool):
        """Apply external penalties for poor performance."""
        if not disputed:
            return

        # Lawsuit probability
        lawsuit_prob = max(0, (0.6 - quality) * 0.4)
        if random.random() < lawsuit_prob:
            # Sued! Lose assets outside contract
            damages = project_value * (1.5 + random.random())
            actual_damages = min(damages, self.external_assets * 0.3)
            self.external_assets -= actual_damages
            self.balance -= actual_damages * 0.5  # Legal fees

        # Credit score damage
        credit_hit = max(0, (0.6 - quality) * 50)
        self.credit_score = max(300, self.credit_score - credit_hit)

        # License violations
        if quality < 0.4:
            self.license_violations += 1
            if self.license_violations >= 3:
                self.licensed = False


@dataclass
class TraditionalBacker(AdaptiveBacker):
    """
    Backer in traditional economy with legal recourse.

    Key difference: Can pursue legal action for damages beyond escrow.
    """
    # Willingness to sue (litigation appetite)
    litigation_appetite: float = 0.3

    def decide_funding_traditional(
        self,
        project_value: float,
        contractor_id: str,
        contractor_credit_score: float,
        contractor_licensed: bool,
        max_immediate_bps: int
    ) -> Tuple[bool, float, int]:
        """
        Funding decision in traditional economy.
        Credit scores and licenses provide additional trust signals.
        """
        available = self.balance - sum(self.active_investments.values())
        if available < 10:
            return False, 0, 0

        # Traditional trust factors
        learned_trust = self.contractor_trust.get(contractor_id, 0.5)

        # Credit score provides strong signal (normalized to 0-1)
        credit_factor = (contractor_credit_score - 300) / 550  # 300-850 range

        # License requirement
        if not contractor_licensed:
            credit_factor *= 0.3  # Massive penalty for unlicensed

        # Combined trust (credit score matters more in traditional)
        combined_trust = 0.3 * learned_trust + 0.7 * credit_factor

        action = self.strategy_memory.get_best_action(["conservative", "moderate", "aggressive"])

        if action == "conservative":
            if combined_trust < 0.4:
                return False, 0, 0
            amount = min(available * 0.3, project_value * 0.3)
            immediate_pct = 0.15 + 0.15 * combined_trust  # Higher immediate (less risk)
        elif action == "moderate":
            if combined_trust < 0.3:
                return False, 0, 0
            amount = min(available * 0.4, project_value * 0.4)
            immediate_pct = 0.20 + 0.15 * combined_trust
        else:
            amount = min(available * 0.5, project_value * 0.5)
            immediate_pct = 0.25 + 0.15 * combined_trust

        max_immediate = max_immediate_bps / 10000
        immediate_pct = min(immediate_pct, max_immediate)
        immediate_bps = int(immediate_pct * 10000)

        return True, amount, immediate_bps


@dataclass
class TraditionalEconomy:
    """
    Traditional economy with legal jurisdiction enforcement.

    Key differences from trustless:
    1. External penalties (lawsuits, asset seizure)
    2. Credit scores affect all future dealings
    3. Professional licensing requirements
    4. Higher immediate release (more trust due to legal recourse)
    5. Slower dispute resolution but stronger enforcement
    """
    params: EconomyParameters

    # Agents
    contractors: List[TraditionalContractor] = field(default_factory=list)
    backers: List[TraditionalBacker] = field(default_factory=list)
    arbiters: List[AdaptiveArbiter] = field(default_factory=list)

    # Projects
    projects: Dict[str, Project] = field(default_factory=dict)

    # Treasury (court fees, etc.)
    treasury: float = 0.0

    # Tracking
    metrics: AdaptiveEconomyMetrics = field(default_factory=AdaptiveEconomyMetrics)
    equilibrium_tracker: MarketEquilibriumTracker = field(default_factory=MarketEquilibriumTracker)

    # State
    current_tick: int = 0
    rng: random.Random = field(default_factory=random.Random)

    # Traditional economy parameters
    legal_fee_rate: float = 0.15  # 15% of disputed value goes to legal fees
    lawsuit_success_rate: float = 0.7  # Courts usually side with evidence

    def initialize(self, num_contractors: int, num_backers: int, num_arbiters: int, seed: int = 42):
        """Initialize with agents."""
        self.rng.seed(seed)
        random.seed(seed)

        for i in range(num_contractors):
            c = TraditionalContractor(
                id=f"C{i}",
                balance=self.rng.uniform(50, 150),
                external_assets=self.rng.uniform(300, 700),
                credit_score=self.rng.uniform(650, 800),
                base_quality=self.rng.uniform(0.5, 0.9),
                quality_variance=self.rng.uniform(0.05, 0.15),
            )
            c.strategy_memory.epsilon = self.rng.uniform(0.1, 0.4)
            self.contractors.append(c)

        for i in range(num_backers):
            b = TraditionalBacker(
                id=f"B{i}",
                balance=self.rng.uniform(100, 400),
                litigation_appetite=self.rng.uniform(0.1, 0.5),
            )
            b.strategy_memory.epsilon = self.rng.uniform(0.1, 0.4)
            self.backers.append(b)

        for i in range(num_arbiters):
            # In traditional: arbiters are courts/judges
            a = AdaptiveArbiter(
                id=f"A{i}",
                balance=self.rng.uniform(200, 400),
                bias=self.rng.uniform(-0.05, 0.05),  # Courts more neutral
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

        # 3. Sign projects
        self._process_signing()

        # 4. Process ongoing projects
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

        # 5. Process disputes (through courts)
        self._process_disputes()

        # 6. Track metrics
        total_resolved = self.metrics.completed_projects + self.metrics.disputed_projects
        if total_resolved > 0:
            completion_rate = self.metrics.completed_projects / total_resolved
            dispute_rate = self.metrics.disputed_projects / total_resolved
        else:
            completion_rate = 0.5
            dispute_rate = 0.5

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

        if self.contractors:
            avg_quality_target = sum(c.base_quality for c in self.contractors) / len(self.contractors)
            self.metrics.contractor_quality_targets.append(avg_quality_target)

        self.equilibrium_tracker.record_tick(completion_rate, dispute_rate, avg_quality)
        if self.equilibrium_tracker.is_equilibrium() and self.metrics.equilibrium_tick is None:
            self.metrics.equilibrium_tick = self.current_tick

        self.current_tick += 1

    def _create_project(self):
        """Create a new project."""
        available = [c for c in self.contractors
                     if len(c.active_projects) < c.max_projects and c.licensed]
        if not available:
            return

        contractor = self.rng.choice(available)

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

            potential_backers = [b for b in self.backers if project.id not in b.active_investments]
            sample_size = min(15, len(potential_backers))

            if sample_size > 0:
                sampled_backers = self.rng.sample(potential_backers, sample_size)

                for backer in sampled_backers:
                    should_fund, amount, immediate_bps = backer.decide_funding_traditional(
                        project.target_value,
                        contractor.id,
                        contractor.credit_score,
                        contractor.licensed,
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

            if project.total_contributed >= project.target_value * 0.5:
                project.stage = ProjectStage.PENDING

            if self.current_tick - project.created_tick > 20 and project.total_contributed < project.target_value * 0.3:
                for backer_id, contrib in project.contributions.items():
                    backer = self._get_backer(backer_id)
                    if backer:
                        backer.balance += contrib.total_amount
                        if project.id in backer.active_investments:
                            del backer.active_investments[project.id]
                project.stage = ProjectStage.CLOSED

    def _process_signing(self):
        """Contractors sign projects."""
        pending = [p for p in self.projects.values() if p.stage == ProjectStage.PENDING]

        for project in pending:
            if self.current_tick - project.created_tick < self.params.cooling_off_period:
                continue

            contractor = self._get_contractor(project.contractor_id)
            if not contractor or not contractor.licensed:
                continue

            # Traditional: no arbiter stake required (courts handle disputes)
            # But contractor may need to provide performance bond
            bond = project.total_contributed * 0.05
            if contractor.balance >= bond:
                contractor.balance -= bond
                project.contractor_stake = bond

                immediate = project.total_immediate
                contractor.balance += immediate

                contractor.active_projects.append(project.id)
                project.signed_tick = self.current_tick
                project.stage = ProjectStage.ONGOING

    def _process_ongoing_project(self, project: Project) -> Optional[dict]:
        """Process an ongoing project."""
        contractor = self._get_contractor(project.contractor_id)
        if not contractor:
            return None

        if project.actual_quality == 0:
            immediate_pct = project.total_immediate / max(project.total_contributed, 1)
            locked_pct = 1 - immediate_pct
            project.actual_quality = contractor.decide_quality_traditional(
                project.total_contributed,
                immediate_pct,
                locked_pct
            )

        # Backers evaluate quality
        observed_quality = project.actual_quality + self.rng.gauss(0, 0.1)
        observed_quality = max(0, min(1, observed_quality))

        for backer_id, contribution in project.contributions.items():
            if contribution.voting_power == 0:
                continue

            backer = self._get_backer(backer_id)
            if not backer:
                continue

            # Traditional: higher quality threshold (legal recourse available)
            threshold = 0.55 + 0.15 * (1 - backer.risk_tolerance)
            if observed_quality >= threshold:
                contribution.vote = VoteType.RELEASE
            else:
                contribution.vote = VoteType.DISPUTE

        release_reached, dispute_reached = project.get_quorum_status(self.params.backers_vote_quorum_bps)

        result = {"completed": False, "disputed": False, "quality": project.actual_quality}

        time_ongoing = self.current_tick - (project.signed_tick or self.current_tick)
        voting_deadline = 10

        if release_reached:
            self._complete_project(project, disputed=False)
            result["completed"] = True
            self.metrics.completed_projects += 1
        elif dispute_reached:
            project.stage = ProjectStage.DISPUTE
            result["disputed"] = True
            self.metrics.disputed_projects += 1
        elif time_ongoing >= voting_deadline:
            release_votes = project.release_votes
            dispute_votes = project.dispute_votes

            if release_votes >= dispute_votes:
                self._complete_project(project, disputed=False)
                result["completed"] = True
                self.metrics.completed_projects += 1
            else:
                project.stage = ProjectStage.DISPUTE
                result["disputed"] = True
                self.metrics.disputed_projects += 1

        return result

    def _process_disputes(self):
        """Process disputed projects through legal system."""
        disputed = [p for p in self.projects.values() if p.stage == ProjectStage.DISPUTE]

        for project in disputed:
            contractor = self._get_contractor(project.contractor_id)
            if not contractor:
                continue

            # Court ruling based on evidence (quality)
            # Traditional courts are more accurate but slower
            true_quality = project.actual_quality
            court_noise = self.rng.gauss(0, 0.08)  # Courts more accurate
            ruling = max(0, min(1, true_quality + court_noise))
            project.arbitration_ruling = ruling

            # Legal fees
            legal_fees = project.total_contributed * self.legal_fee_rate
            self.treasury += legal_fees

            # Apply external penalties to contractor
            contractor.apply_external_penalty(
                project.actual_quality,
                project.total_contributed,
                True
            )

            # Credit score update based on ruling
            if ruling < 0.5:
                contractor.credit_score = max(300, contractor.credit_score - 30)
            elif ruling > 0.7:
                contractor.credit_score = min(850, contractor.credit_score + 5)

            self._complete_project(project, disputed=True)

    def _complete_project(self, project: Project, disputed: bool):
        """Complete a project and distribute funds."""
        contractor = self._get_contractor(project.contractor_id)
        final_ruling = project.arbitration_ruling if disputed else 1.0

        locked = project.total_locked
        contractor_share = locked * final_ruling

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
                # Successful completion improves credit
                contractor.credit_score = min(850, contractor.credit_score + 2)

            if project.id in contractor.active_projects:
                contractor.active_projects.remove(project.id)

            # Learn from outcome (including external penalty risk)
            external_penalty = contractor.calculate_external_risk(
                project.total_contributed, project.actual_quality
            ) if disputed else 0

            contractor.learn_from_outcome(
                project.actual_quality,
                contractor_payout - external_penalty,
                disputed,
                project.total_contributed
            )

            contractor.reputation += contractor_payout * 0.01

        self.treasury += platform_fee

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

            backer.learn_from_outcome(
                contribution.total_amount,
                refund + contribution.immediate_amount,
                contractor.id if contractor else "",
                project.actual_quality,
                contribution.immediate_bps / 10000,
                not disputed
            )

            if not disputed:
                backer.reputation += contribution.total_amount * 0.005

        project.stage = ProjectStage.CLOSED
        project.resolved_tick = self.current_tick

    def _get_contractor(self, cid: str) -> Optional[TraditionalContractor]:
        for c in self.contractors:
            if c.id == cid:
                return c
        return None

    def _get_backer(self, bid: str) -> Optional[TraditionalBacker]:
        for b in self.backers:
            if b.id == bid:
                return b
        return None

    def get_summary(self) -> dict:
        """Get summary statistics."""
        window = 100
        recent_completion = self.metrics.completion_rates[-window:] if self.metrics.completion_rates else []
        recent_disputes = self.metrics.dispute_rates[-window:] if self.metrics.dispute_rates else []
        recent_quality = self.metrics.quality_history[-window:] if self.metrics.quality_history else []

        avg_completion = sum(recent_completion) / len(recent_completion) if recent_completion else 0
        avg_dispute = sum(recent_disputes) / len(recent_disputes) if recent_disputes else 0
        avg_quality = sum(recent_quality) / len(recent_quality) if recent_quality else 0

        quality_targets = self.metrics.contractor_quality_targets
        if len(quality_targets) > 100:
            early_quality = sum(quality_targets[:50]) / 50
            late_quality = sum(quality_targets[-50:]) / 50
            quality_convergence = late_quality - early_quality
        else:
            quality_convergence = 0

        # Traditional-specific metrics
        avg_credit = sum(c.credit_score for c in self.contractors) / len(self.contractors) if self.contractors else 0
        licensed_pct = sum(1 for c in self.contractors if c.licensed) / len(self.contractors) if self.contractors else 0

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
            },
            "traditional_metrics": {
                "avg_credit_score": avg_credit,
                "licensed_contractors": licensed_pct,
            }
        }
