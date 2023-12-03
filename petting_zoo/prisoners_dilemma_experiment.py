import prisoners_dilemma_environment

env = prisoners_dilemma_environment.parallel_env(render_mode="human")
observations, infos = env.reset()
round = 0 

while env.agents:
    # this is where you would insert your policy

    """ Random: both agents play a random move sampled from action space.
    TODO: change action selection according to learning.
    """
    actions = {agent: env.action_space(agent).sample() for agent in env.agents}

    observations, rewards, terminations, truncations, infos = env.step(actions)
    # print("iteration " + str(round) + ": " + str(actions))
    round += 1
env.close()