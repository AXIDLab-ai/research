"""Optional E7: finite-action tabular Q learning using online information only."""
from dataclasses import replace
import numpy as np
import pandas as pd
from .config import Policy
from .model import Simulation, simulate

ACTIONS = [(lam, eps) for lam in (0, .25, .5, 1) for eps in (0, .1, .25)]


def observable_state(sim):
    return (min((sim.t - sim.c.warmup) // 3, 3),
            int(np.clip(np.floor(np.mean(sim.last_scores) * 4), 0, 3)),
            int(np.clip(np.floor(np.std(sim.last_scores) * 10), 0, 3)),
            int(np.clip(np.floor(sim.last_unknown * 4), 0, 3)),
            int(np.clip(np.floor(np.sum(sim.weights**2) * sim.c.operators), 1, 5)))


def observed_reward(sim, rows):
    # Missing outcomes get no monetary reward; this normative proxy is explicit.
    # No latent quality, true profits, future exits or survey-retrospective records enter Q updates.
    total = 0.0
    for frame in rows:
        g = frame[frame.target & frame.age.between(1, sim.c.horizon)]
        total += (g.online_profit.fillna(0) / (1 + sim.c.discount)**g.age).sum()
    return float(total / max(sim.c.slots * sim.c.cohorts * sim.c.unit_cost, 1))


def train(bundle, config, episodes=100, learning_rate=.15, gamma=.95, epsilon=.2, progress=None):
    q = {}
    logs = []
    rng = np.random.default_rng(config.seed + 70123)
    train_cfg = replace(config, seed=config.seed + 100000)
    for episode in range(episodes):
        sim = Simulation(bundle, train_cfg, Policy("q_learning", 3), episode)
        transitions = []
        tail_return = 0.0
        tail_steps = 0
        while sim.t <= sim.end:
            sim.scores()
            decision = config.warmup <= sim.t <= sim.last_birth
            state = observable_state(sim) if decision else None
            if decision:
                values = q.setdefault(state, np.zeros(len(ACTIONS)))
                action = int(rng.integers(len(ACTIONS))) if rng.random() < epsilon else int(np.argmax(values))
            sim.step(ACTIONS[action] if decision else None, keep_panel=True)
            # Consume each year's observation records once, then release them for bounded memory.
            reward = observed_reward(sim, sim.panel)
            sim.panel.clear()
            if decision:
                transitions.append((state, action, reward))
            elif sim.t > sim.last_birth + 1:
                tail_return += gamma**tail_steps * reward
                tail_steps += 1
        if transitions:
            s, a, reward = transitions[-1]
            transitions[-1] = (s, a, reward + gamma * tail_return)
        for k in range(len(transitions) - 1, -1, -1):
            state, action, reward = transitions[k]
            future = np.max(q.setdefault(transitions[k + 1][0], np.zeros(len(ACTIONS)))) if k + 1 < len(transitions) else 0
            q[state][action] += learning_rate * (reward + gamma * future - q[state][action])
        logs.append(dict(episode=episode, observed_return=sum(x[2] for x in transitions), **sim.finish()["summary"]))
        if progress:
            progress(episode + 1, episodes)
    payload = {",".join(map(str, k)): v.tolist() for k, v in q.items()}
    return dict(q=payload, actions=ACTIONS, train_seed=train_cfg.seed, evaluation_seed=config.seed + 200000,
                episodes=episodes, gamma=gamma, learning_rate=learning_rate, epsilon=epsilon,
                reward="online observed discounted operating profit / allocated budget; missing=0; not EVSI"), pd.DataFrame(logs)


def evaluate(bundle, config, learned, repetitions=30):
    cfg = replace(config, seed=int(learned["evaluation_seed"]))
    def controller(sim):
        key = ",".join(map(str, observable_state(sim)))
        values = learned["q"].get(key)
        # Unseen information states default to fixed allocation, not latent-optimal actions.
        return learned["actions"][int(np.argmax(values))] if values else (0, 0)
    rows = []
    for rep in range(repetitions):
        for policy in (Policy(), Policy("common3", 3, .5), Policy("q_learning", 3)):
            out = simulate(bundle, cfg, policy, rep, controller=controller if policy.name == "q_learning" else None)
            rows.append(out["summary"])
    return pd.DataFrame(rows)
