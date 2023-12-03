from pettingzoo.classic import rps_v2

env = rps_v2.parallel_env(render_mode="human")
observations, infos = env.reset()
round = 0 

while env.agents:
    # this is where you would insert your policy
    actions = {agent: env.action_space(agent).sample() for agent in env.agents}
    print("iteration " + str(round) + ": " + str(actions))

    observations, rewards, terminations, truncations, infos = env.step(actions)

    round += 1
env.close()