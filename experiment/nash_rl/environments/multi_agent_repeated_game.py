"""Module containint code for a repeated game environment."""

from typing import Optional, Any

from gymnasium import spaces
from pettingzoo import ParallelEnv  # type: ignore
import nashpy as nash  # type: ignore
import numpy as np
import numpy.typing as npt

ObsType = npt.NDArray[np.int64]
ActionType = np.int64
AgentID = int

RepeatedGameEnvironmentOptions = dict[str, Any]
AgentInfo = dict[str, Any]

PHI_EMPTY_ACTION = 0


def make_observation_space(
    agent_actions_dim: tuple[int, ...], agent_id: AgentID, agent_memory_length: int
) -> spaces.MultiDiscrete:
    num_actions_agent = agent_actions_dim[agent_id]
    others_actions_dim = (
        agent_actions_dim[:agent_id] + agent_actions_dim[agent_id + 1 :]
    )
    new_agent_actions_dim = (num_actions_agent,) + others_actions_dim
    return spaces.MultiDiscrete(
        np.asarray((new_agent_actions_dim,) * agent_memory_length) + 1
    )  # +1 for empty action


def make_observation_from_prev_plays(
    previous_plays: list[tuple[ActionType, ...]],
    agent_id: AgentID,
    agent_memory_length: int,
    num_agents: int,
) -> ObsType:
    plays_array = np.asarray(previous_plays)
    if len(plays_array) < agent_memory_length:
        num_rounds_padded = agent_memory_length - len(plays_array)
        padding = np.full((num_rounds_padded, num_agents), PHI_EMPTY_ACTION)
        plays_array = (
            np.concatenate((padding, plays_array)) if len(plays_array) > 0 else padding
        )
    player_plays = plays_array[-agent_memory_length:, agent_id : agent_id + 1]
    others_plays = np.delete(plays_array, agent_id, axis=1)[-agent_memory_length:, :]
    return np.concatenate((player_plays, others_plays), axis=1)


def get_game_rewards(game: nash.Game, actions: npt.NDArray[np.int64]):
    offsetted_actions = tuple(actions)
    rewards = [
        game.payoff_matrices[agent_id][offsetted_actions]
        for agent_id in range(len(game.payoff_matrices))
    ]
    return rewards


class MultiAgentRepeatedGameEnvironment(ParallelEnv[AgentID, ObsType, ActionType]):
    """Class representing a generic repeated game environment."""

    # ========== Base class properties (static) ==========

    metadata = {"name": "repeated_game_environment_v0", "render_modes": ["ansi"]}

    # ========== Game properties (changed only at creation) ==========

    # === Base class properties ===
    agents: list[AgentID]
    possible_agents: list[AgentID]
    observation_spaces: dict[AgentID, spaces.MultiDiscrete]  # type: ignore # Observation space for each agent
    action_spaces: dict[AgentID, spaces.Discrete]  # type: ignore # Action space for each agent

    # === Repeated game properties ===
    game: nash.Game
    agent_memory_length: int
    max_rounds: int
    render_mode: Optional[str]

    # ========== Environment run properties =========
    previous_plays: list[tuple[ActionType, ...]]
    cumulative_agent_rewards: dict[AgentID, float]

    # === Repeated game properties ===
    round_number: int

    def __init__(
        self,
        game: nash.Game,
        agent_memory_length: int,
        max_rounds: int = 500,
        render_mode: Optional[str] = None,
    ):
        num_agents = len(game.payoff_matrices)
        num_actions = game.payoff_matrices[0].shape

        self.possible_agents = [i for i in range(num_agents)]
        self.agents = self.possible_agents
        self.action_spaces = {i: spaces.Discrete(num_actions[i]) for i in self.agents}  # type: ignore
        self.observation_spaces = {  # type: ignore
            i: make_observation_space(num_actions, i, agent_memory_length)
            for i in self.agents
        }

        self.game = game
        self.agent_memory_length = agent_memory_length
        self.max_rounds = max_rounds
        self.render_mode = render_mode

    def _make_agent_observations(self) -> dict[AgentID, ObsType]:
        observations = {
            agent_id: make_observation_from_prev_plays(self.previous_plays, agent_id, self.agent_memory_length, len(self.agents))  # type: ignore
            for agent_id in self.agents
        }
        return observations

    def _make_infos(self) -> dict[AgentID, AgentInfo]:
        return {
            agent_id: {"total_reward": self.cumulative_agent_rewards[agent_id]}
            for agent_id in self.agents
        }

    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[RepeatedGameEnvironmentOptions] = None,
    ) -> tuple[dict[AgentID, ObsType], dict[AgentID, AgentInfo]]:
        self.round_number = 0
        # TODO Fix type error
        self.previous_plays = np.asarray([])  # type: ignore
        self.cumulative_agent_rewards = {agent_id: 0 for agent_id in self.agents}

        observations = self._make_agent_observations()

        # Get dummy infos. Necessary for proper parallel_to_aec conversion
        agent_infos: dict[AgentID, dict[str, Any]] = self._make_infos()

        return (observations, agent_infos)

    def step(
        self,
        actions: dict[AgentID, ActionType],
    ) -> tuple[
        dict[AgentID, ObsType],
        dict[AgentID, float],
        dict[AgentID, bool],
        dict[AgentID, bool],
        dict[AgentID, AgentInfo],
    ]:
        array_actions = np.asarray([actions[agent_id] for agent_id in self.agents])
        tuple_rewards = get_game_rewards(self.game, array_actions)

        offset_actions = array_actions + 1

        self.previous_plays = (
            np.concatenate((self.previous_plays, [offset_actions]))
            if len(self.previous_plays) > 0
            else np.asarray([offset_actions])
        )

        observations = self._make_agent_observations()
        rewards = {agent_id: tuple_rewards[agent_id] for agent_id in self.agents}

        terminations = {agent_id: False for agent_id in self.agents}

        truncations = {agent_id: False for agent_id in self.agents}
        if (
            self.round_number == self.max_rounds
        ):  # Terminate after the last one, since the termination round is not counted for training
            truncations = {agent_id: True for agent_id in self.agents}

        for agent_id in self.agents:
            self.cumulative_agent_rewards[agent_id] += rewards[agent_id].item()

        # Get dummy infos. Necessary for proper parallel_to_aec conversion
        agent_infos: dict[AgentID, dict[str, Any]] = self._make_infos()

        self.round_number += 1

        return (observations, rewards, terminations, truncations, agent_infos)

    def render(self) -> None:
        # 'ansi' mode prints text-based representation of the game
        if self.render_mode == "ansi":
            print(self.previous_plays)

    def observation_space(self, agent: AgentID) -> spaces.MultiDiscrete:
        return self.observation_spaces[agent]

    def action_space(self, agent: AgentID) -> spaces.Discrete:
        return self.action_spaces[agent]
