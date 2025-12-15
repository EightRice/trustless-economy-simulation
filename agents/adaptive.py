"""
Adaptive agent behaviors that learn from experience.
Implements reinforcement learning-style strategy updates.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import math
import random


@dataclass
class StrategyMemory:
    """
    Tracks outcomes for strategy learning.
    Uses exponential moving average for recent bias.
    """
    # Outcome history by action taken
    action_outcomes: Dict[str, List[float]] = field(default_factory=dict)

    # Exponential moving average of rewards
    ema_rewards: Dict[str, float] = field(default_factory=dict)
    ema_alpha: float = 0.1  # Learning rate

    # Exploration vs exploitation
    epsilon: float = 0.2  # Initial exploration rate
    epsilon_decay: float = 0.995  # Decay per decision
    min_epsilon: float = 0.05

    def record_outcome(self, action: str, reward: float):
        """Record the outcome of an action."""
        if action not in self.action_outcomes:
            self.action_outcomes[action] = []
            self.ema_rewards[action] = reward
        else:
            self.action_outcomes[action].append(reward)
            # Update EMA
            self.ema_rewards[action] = (
                self.ema_alpha * reward +
                (1 - self.ema_alpha) * self.ema_rewards[action]
            )

    def get_best_action(self, available_actions: List[str]) -> str:
        """
        Choose action using epsilon-greedy strategy.
        """
        if random.random() < self.epsilon:
            # Explore: random action
            return random.choice(available_actions)

        # Exploit: choose best known action
        best_action = None
        best_reward = float('-inf')

        for action in available_actions:
            reward = self.ema_rewards.get(action, 0)
            if reward > best_reward:
                best_reward = reward
                best_action = action

        return best_action or random.choice(available_actions)

    def decay_exploration(self):
        """Reduce exploration over time."""
        self.epsilon = max(self.min_epsilon, self.epsilon * self.epsilon_decay)


@dataclass
class ReputationTracker:
    """
    Tracks observed reputation and outcomes for other agents.
    Allows agents to form beliefs about market participants.
    """
    # Observed outcomes by agent ID
    agent_outcomes: Dict[str, List[Tuple[float, float]]] = field(default_factory=dict)  # (quality, payout)

    # Reputation beliefs (learned, not just on-chain rep)
    reputation_beliefs: Dict[str, float] = field(default_factory=dict)

    # Trust update rate
    trust_alpha: float = 0.2

    def observe_outcome(self, agent_id: str, quality: float, successful: bool):
        """Record observed outcome for an agent."""
        if agent_id not in self.agent_outcomes:
            self.agent_outcomes[agent_id] = []
            self.reputation_beliefs[agent_id] = 0.5  # Neutral prior

        self.agent_outcomes[agent_id].append((quality, 1.0 if successful else 0.0))

        # Update belief
        outcome_value = quality if successful else quality * 0.5
        self.reputation_beliefs[agent_id] = (
            self.trust_alpha * outcome_value +
            (1 - self.trust_alpha) * self.reputation_beliefs[agent_id]
        )

    def get_trust(self, agent_id: str, on_chain_rep: float) -> float:
        """
        Get combined trust score (learned + on-chain).
        """
        learned = self.reputation_beliefs.get(agent_id, 0.5)
        # Sigmoid transform of on-chain rep
        on_chain_factor = 1 / (1 + math.exp(-0.02 * (on_chain_rep - 50)))

        # Combine: more weight to learned over time
        n_observations = len(self.agent_outcomes.get(agent_id, []))
        learned_weight = min(0.8, n_observations * 0.1)

        return learned_weight * learned + (1 - learned_weight) * on_chain_factor


class AdaptiveContractorMixin:
    """
    Mixin for contractors that adapt strategy based on outcomes.
    """

    def __init__(self):
        self.strategy_memory = StrategyMemory()
        self.market_tracker = ReputationTracker()
        self._adaptation_enabled = True

    def adapt_quality_strategy(self, project_outcome: dict):
        """
        Update quality strategy based on project outcome.
        """
        if not self._adaptation_enabled:
            return

        quality = project_outcome.get("quality_delivered", 0)
        payout = project_outcome.get("payout", 0)
        disputed = project_outcome.get("disputed", False)

        # Calculate reward: payout minus effort (quality as proxy)
        # High quality costs effort but reduces dispute risk
        effort_cost = quality * 0.3 * project_outcome.get("project_value", 100)
        dispute_cost = 0.5 * project_outcome.get("project_value", 100) if disputed else 0

        reward = payout - effort_cost - dispute_cost

        # Discretize quality into actions
        if quality < 0.4:
            action = "low_quality"
        elif quality < 0.7:
            action = "medium_quality"
        else:
            action = "high_quality"

        self.strategy_memory.record_outcome(action, reward)
        self.strategy_memory.decay_exploration()

    def get_adaptive_quality_target(self) -> float:
        """
        Get target quality level based on learned strategy.
        """
        if not self._adaptation_enabled:
            return 0.7  # Default

        action = self.strategy_memory.get_best_action([
            "low_quality", "medium_quality", "high_quality"
        ])

        quality_targets = {
            "low_quality": 0.3,
            "medium_quality": 0.6,
            "high_quality": 0.85,
        }

        return quality_targets.get(action, 0.7)


class AdaptiveBackerMixin:
    """
    Mixin for backers that adapt funding strategy based on outcomes.
    """

    def __init__(self):
        self.strategy_memory = StrategyMemory()
        self.contractor_tracker = ReputationTracker()
        self._adaptation_enabled = True

    def adapt_funding_strategy(self, project_outcome: dict):
        """
        Update funding strategy based on project outcome.
        """
        if not self._adaptation_enabled:
            return

        immediate_pct = project_outcome.get("immediate_pct", 0)
        returned = project_outcome.get("amount_returned", 0)
        invested = project_outcome.get("amount_invested", 0)
        contractor_id = project_outcome.get("contractor_id")
        quality = project_outcome.get("quality", 0.5)
        successful = project_outcome.get("successful", False)

        # Calculate reward: return on investment
        roi = (returned - invested) / max(invested, 1)

        # Discretize immediate percentage into actions
        if immediate_pct < 0.1:
            action = "conservative"
        elif immediate_pct < 0.15:
            action = "moderate"
        else:
            action = "aggressive"

        self.strategy_memory.record_outcome(action, roi)
        self.strategy_memory.decay_exploration()

        # Update contractor beliefs
        if contractor_id:
            self.contractor_tracker.observe_outcome(contractor_id, quality, successful)

    def get_adaptive_immediate_pct(self, contractor_id: str, on_chain_rep: float) -> float:
        """
        Get immediate percentage based on learned strategy and contractor trust.
        """
        if not self._adaptation_enabled:
            return 0.1  # Default

        # Get base strategy
        action = self.strategy_memory.get_best_action([
            "conservative", "moderate", "aggressive"
        ])

        base_immediate = {
            "conservative": 0.05,
            "moderate": 0.12,
            "aggressive": 0.18,
        }.get(action, 0.1)

        # Adjust based on contractor trust
        trust = self.contractor_tracker.get_trust(contractor_id, on_chain_rep)

        # Higher trust = willing to give more immediate
        adjusted = base_immediate * (0.5 + trust)

        return min(0.2, adjusted)  # Cap at 20%


@dataclass
class MarketEquilibriumTracker:
    """
    Tracks market-level metrics to detect equilibrium states.
    """
    # Rolling window of metrics
    window_size: int = 50
    completion_rates: List[float] = field(default_factory=list)
    dispute_rates: List[float] = field(default_factory=list)
    avg_qualities: List[float] = field(default_factory=list)

    # Equilibrium detection
    equilibrium_threshold: float = 0.02  # Variance threshold

    def record_tick(self, completion_rate: float, dispute_rate: float, avg_quality: float):
        """Record metrics for a tick."""
        self.completion_rates.append(completion_rate)
        self.dispute_rates.append(dispute_rate)
        self.avg_qualities.append(avg_quality)

        # Keep window size
        if len(self.completion_rates) > self.window_size:
            self.completion_rates.pop(0)
            self.dispute_rates.pop(0)
            self.avg_qualities.pop(0)

    def is_equilibrium(self) -> bool:
        """
        Check if market has reached equilibrium (stable state).
        """
        if len(self.completion_rates) < self.window_size:
            return False

        # Check variance of each metric
        def variance(data):
            if not data:
                return float('inf')
            mean = sum(data) / len(data)
            return sum((x - mean) ** 2 for x in data) / len(data)

        return (
            variance(self.completion_rates) < self.equilibrium_threshold and
            variance(self.dispute_rates) < self.equilibrium_threshold and
            variance(self.avg_qualities) < self.equilibrium_threshold
        )

    def get_equilibrium_values(self) -> Dict[str, float]:
        """
        Get the equilibrium values if reached.
        """
        if not self.completion_rates:
            return {}

        return {
            "completion_rate": sum(self.completion_rates) / len(self.completion_rates),
            "dispute_rate": sum(self.dispute_rates) / len(self.dispute_rates),
            "avg_quality": sum(self.avg_qualities) / len(self.avg_qualities),
        }


@dataclass
class DAOParticipationIncentives:
    """
    Models the DAO participation incentives from RepToken.
    """
    # Passive income epoch
    passive_income_budget: float = 1000.0
    passive_income_period: int = 100  # Ticks between epochs
    last_passive_epoch: int = 0

    # Delegate reward epoch
    delegate_reward_budget: float = 500.0
    delegate_reward_period: int = 100
    last_delegate_epoch: int = 0

    # Claim tracking
    unclaimed_passive: Dict[str, float] = field(default_factory=dict)
    unclaimed_delegate: Dict[str, float] = field(default_factory=dict)

    def process_epoch(
        self,
        current_tick: int,
        reputation_balances: Dict[str, float],
        delegated_power: Dict[str, float],  # agent_id -> extra votes from delegation
        total_reputation: float
    ):
        """
        Process passive income and delegate reward epochs.
        """
        # Passive income epoch
        if current_tick - self.last_passive_epoch >= self.passive_income_period:
            self.last_passive_epoch = current_tick

            if total_reputation > 0:
                for agent_id, rep in reputation_balances.items():
                    share = rep / total_reputation
                    reward = self.passive_income_budget * share
                    self.unclaimed_passive[agent_id] = (
                        self.unclaimed_passive.get(agent_id, 0) + reward
                    )

        # Delegate reward epoch
        if current_tick - self.last_delegate_epoch >= self.delegate_reward_period:
            self.last_delegate_epoch = current_tick

            total_delegated = sum(delegated_power.values())
            if total_delegated > 0:
                for agent_id, delegated in delegated_power.items():
                    if delegated > 0:  # Only reward those with delegated votes
                        share = delegated / total_delegated
                        reward = self.delegate_reward_budget * share
                        self.unclaimed_delegate[agent_id] = (
                            self.unclaimed_delegate.get(agent_id, 0) + reward
                        )

    def claim_rewards(self, agent_id: str) -> float:
        """
        Claim all available rewards for an agent.
        Returns total claimed.
        """
        passive = self.unclaimed_passive.pop(agent_id, 0)
        delegate = self.unclaimed_delegate.pop(agent_id, 0)
        return passive + delegate

    def get_expected_passive_income(self, reputation: float, total_reputation: float) -> float:
        """
        Calculate expected passive income per epoch for planning.
        """
        if total_reputation == 0:
            return 0
        return self.passive_income_budget * (reputation / total_reputation)


def calculate_nash_equilibrium_quality(
    platform_fee: float,
    arbitration_fee: float,
    dispute_probability_fn,  # Function: quality -> dispute probability
    max_immediate_pct: float
) -> float:
    """
    Calculate theoretical Nash equilibrium quality level.

    At equilibrium, contractor's marginal cost of quality equals
    marginal benefit from reduced dispute risk.

    This is a simplified analytical solution.
    """
    # Grid search for optimal quality
    best_quality = 0.5
    best_utility = float('-inf')

    for q in [i / 100 for i in range(0, 101, 5)]:
        # Expected payout
        dispute_prob = dispute_probability_fn(q)

        # If no dispute: get full payment minus fees
        no_dispute_payout = (1 - platform_fee) * (1 - max_immediate_pct)

        # If dispute: expected payout based on quality ruling
        dispute_payout = (1 - platform_fee) * q * (1 - max_immediate_pct) - arbitration_fee / 2

        expected_payout = (
            (1 - dispute_prob) * no_dispute_payout +
            dispute_prob * dispute_payout
        )

        # Effort cost (convex in quality)
        effort_cost = 0.3 * q ** 2

        utility = expected_payout - effort_cost

        if utility > best_utility:
            best_utility = utility
            best_quality = q

    return best_quality
