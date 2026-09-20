"""Annual schedule, competing operators, semi-Markov firms and separate observations."""
from dataclasses import asdict
import math
import numpy as np
import pandas as pd
from .config import Config, Policy


def random_stream(seed, replicate, channel, year=0, cohort=0):
    return np.random.default_rng(np.random.SeedSequence([seed, replicate, channel, year, cohort]))


def softmax(x, axis=-1):
    e = np.exp(x - np.max(x, axis=axis, keepdims=True))
    return e / e.sum(axis=axis, keepdims=True)


def quotas(weights, n, rng):
    exact = n * weights / weights.sum()
    out = np.floor(exact).astype(int)
    tie = rng.random(len(out))
    order = np.lexsort((tie, -(exact - out)))
    out[order[:n - out.sum()]] += 1
    return out


def competing_offers(utility, capacity, preferences):
    """Simultaneous proposals; chosen firms leave pool; no duplicate allocations."""
    j, count = utility.shape
    owner = np.full(count, -1, dtype=int)
    remaining = capacity.copy()
    ranks = np.argsort(-utility, axis=1, kind="stable")
    while remaining.sum() and np.any(owner < 0):
        offers = np.zeros((j, count), dtype=bool)
        for op in range(j):
            available = ranks[op][owner[ranks[op]] < 0]
            offers[op, available[:remaining[op]]] = True
        offered = offers.any(axis=0)
        if not offered.any():
            break
        winners = np.argmax(np.where(offers[:, offered], preferences[:, offered], -np.inf), axis=0)
        owner[offered] = winners
        remaining -= np.bincount(winners, minlength=j)
    return owner, remaining


class Simulation:
    def __init__(self, bundle, config=Config(), policy=Policy(), replicate=0):
        self.bundle, self.c, self.policy, self.rep = bundle, config.validate(), policy.validate(), replicate
        c = config
        r = self.rng(1)
        weights = r.choice(bundle.operator_sizes, c.operators, replace=True)
        self.weights = weights / weights.sum()
        self.initial_weights = self.weights.copy()
        a, b = r.normal(size=(2, c.operators, 5))
        # Better precision and better support can correlate; portfolio size never determines either.
        b = c.ability_correlation * a + np.sqrt(1 - c.ability_correlation**2) * b
        self.noise = c.signal_noise * np.exp(-.25 * a)
        self.ability = np.exp(.3 * b - .045)
        if c.homogeneous_abilities:
            self.noise[:] = c.signal_noise
            self.ability[:] = 1
        self.capacity = np.maximum(c.slots * c.support_years * self.weights, 1e-9)
        self.groups, self.snapshots, self.history, self.panel, self.allocations = [], [], [], [], []
        self.t = 0
        self.last_birth = c.warmup + c.cohorts - 1
        self.end = self.last_birth + c.horizon
        self.pool_size = max(1, int(math.ceil(c.slots * c.candidate_ratio)))
        self.last_scores = np.full(c.operators, c.prior_mean)
        self.last_unknown = 1.0
        self.last_reward = 0.0

    def rng(self, channel, year=0, cohort=0):
        return random_stream(self.c.seed, self.rep, channel, year, cohort)

    def scores(self):
        c = self.c
        numer = np.full(c.operators, c.prior_strength * c.prior_mean)
        denom = np.full(c.operators, c.prior_strength)
        unknown_count = total = 0
        for snap in self.snapshots:
            if not self.t - c.score_window <= snap["year"] <= self.t - 1:
                continue
            value = snap["value"].copy()
            if c.erase_after_exit:
                value[snap["group"]["state"][snap["indices"]] == 4] = np.nan
            unknown = np.isnan(value)
            unknown_count += int(unknown.sum()); total += len(value)
            credit = np.where(unknown, 0 if c.observed_only else c.unknown_credit, value)
            eligible = ~unknown if c.observed_only else np.ones(len(value), dtype=bool)
            numer += np.bincount(snap["ops"], weights=credit, minlength=c.operators)
            denom += np.bincount(snap["ops"], weights=eligible.astype(float), minlength=c.operators)
        self.last_unknown = unknown_count / total if total else 1.0
        self.last_scores = np.divide(numer, denom, out=np.full(c.operators, c.prior_mean), where=denom > 0)
        return self.last_scores

    def birth(self, q, policy):
        c, t, m = self.c, self.t, self.pool_size
        r = self.rng(2, t)
        sector_weights = self.bundle.weights * np.exp(c.sector_tilt * np.linspace(-1, 1, 5))
        sector = r.choice(5, m, p=sector_weights / sector_weights.sum())
        quality = r.normal(size=m)
        delay_z = c.quality_delay * quality + np.sqrt(1 - c.quality_delay**2) * r.normal(size=m)
        delay_z += np.asarray(c.sector_delay_shift)[sector]
        speed = np.digitize(delay_z, [-.43, .43])
        observed = speed.copy()
        error = r.random(m) < c.misclassification
        observed[error] = (observed[error] + r.integers(1, 3, size=error.sum())) % 3
        due = np.array([2, 3, 5])[observed] if policy.differentiated else np.full(m, policy.horizon)
        signal = quality[None, :] + self.noise[:, sector] * self.rng(3, t).normal(size=(c.operators, m))
        probability = 1 / (1 + np.exp(-np.clip(signal + .5 * (due - np.array([2, 3, 5])[observed]), -30, 30)))
        incentive = c.adaptation * policy.response * probability
        utility = signal + incentive
        owner, unfilled = competing_offers(utility, q, self.rng(4, t).random((c.operators, m)))
        ix = np.where(owner >= 0)[0]
        if not len(ix):
            return unfilled
        u = self.rng(5, t).random(m)[ix]
        initial = np.minimum((u[:, None] > self.bundle.initial[sector[ix]].cumsum(axis=1)).sum(axis=1), 3)
        size = len(ix)
        self.groups.append(dict(cohort=t, idx=ix, op=owner[ix], sector=sector[ix], quality=quality[ix],
                                speed=speed[ix], observed_speed=observed[ix], due=due[ix], state=initial,
                                duration=np.zeros(size, dtype=int), shock=np.zeros(size),
                                cumulative=np.zeros(size), sustained=np.zeros(size, dtype=bool),
                                prev_profit=np.zeros(size, dtype=bool), prev_observed_profit=np.full(size, np.nan),
                                final_revenue=np.zeros(size), final_alive=np.ones(size, dtype=bool),
                                target=c.warmup <= t <= self.last_birth))
        return unfilled

    def step(self, action=None, keep_panel=True):
        """Government action at t uses only snapshots dated <= t-1."""
        c, t = self.c, self.t
        if t > self.end:
            raise StopIteration
        score = self.scores()
        policy = self.policy
        if action is not None:
            from dataclasses import replace
            policy = replace(policy, response=float(action[0]), exploration=float(action[1]))
        active_policy = Policy() if t < c.warmup else policy
        old = self.weights.copy()
        if active_policy.equal:
            self.weights = np.full(c.operators, 1 / c.operators)
        else:
            target = (1 - active_policy.exploration) * softmax(c.beta * score) + active_policy.exploration / c.operators
            self.weights = (1 - active_policy.response) * old + active_policy.response * target
        has_birth = t <= self.last_birth or c.tail_entries
        q = quotas(self.weights, c.slots if has_birth else 0, self.rng(6, t))
        unfilled = self.birth(q, active_policy) if has_birth else np.zeros(c.operators, int)
        active = np.zeros(c.operators)
        for g in self.groups:
            age = t - g["cohort"]
            if age < c.support_years:
                active += np.bincount(g["op"], weights=(g["state"] != 4), minlength=c.operators)
        support = np.minimum(1, self.capacity / np.maximum(active, 1)) if c.dilution else np.ones(c.operators)
        macro = self.rng(7, t).normal() * c.macro_scale
        reward = 0.0
        for g in self.groups:
            age, ix = t - g["cohort"], g["idx"]
            n = len(ix)
            if age > 0:
                innovations = self.rng(8, t, g["cohort"]).normal(size=self.pool_size)[ix]
                g["shock"] = c.shock_ar * g["shock"] + np.sqrt(1 - c.shock_ar**2) * innovations
                old_state = g["state"].copy()
                probability = self.bundle.transition[g["sector"], old_state]
                logits = np.log(np.maximum(probability, 1e-12))
                delay = np.array([2, 3, 5])[g["speed"]]
                advantage = (c.quality_effect * g["quality"] + c.delay_effect * np.clip((age - delay) / 3, -1, 1)
                             + c.age_effect * min(age, 5) + c.duration_effect * np.minimum(g["duration"], 3)
                             + macro + c.shock_scale * g["shock"])
                effort = support[g["op"]] if age < c.support_years else np.zeros(n)
                advantage += c.support_effect * self.ability[g["op"], g["sector"]] * effort
                logits += advantage[:, None] * np.array([-.3, .3, .3, .7, -.5])
                logits[:, [1, 3]] += c.revenue_intercept
                logits[:, [2, 3]] += c.profit_intercept
                logits[:, 4] += c.exit_intercept
                u = self.rng(9, t, g["cohort"]).random(self.pool_size)[ix]
                new_state = np.minimum((u[:, None] > softmax(logits).cumsum(axis=1)).sum(axis=1), 4)
                new_state[old_state == 4] = 4
                g["duration"] = np.where(new_state == old_state, g["duration"] + 1, 0)
                g["state"] = new_state
            # Common innovations indexed by candidate ID, even after policy selection changes.
            emission_z = self.rng(10, t, g["cohort"]).normal(size=self.pool_size)[ix]
            rank_z = (.3 * g["quality"] + .3 * g["shock"] + np.sqrt(.82) * emission_z)
            u = np.array([.5 * (1 + math.erf(float(z) / np.sqrt(2))) for z in rank_z])
            v = self.rng(11, t, g["cohort"]).random(self.pool_size)[ix]
            rev, profit = self.bundle.emit(g["sector"], g["state"], u, v, c.emission_family)
            # Post-exit flow is zero in the model accounting ledger, never imputed into empirical data.
            closed = g["state"] == 4
            positive = (profit > 0) & ~closed
            if 1 <= age <= c.horizon:
                g["cumulative"] += profit / (1 + c.discount)**age
                if age >= 2:
                    g["sustained"] |= positive & g["prev_profit"]
                if g["target"]:
                    reward += float(profit.sum() / (1 + c.discount)**age)
            g["prev_profit"] = positive
            if age == c.horizon:
                g["final_revenue"], g["final_alive"] = rev.copy(), ~closed
            obs_rng = self.rng(12, t, g["cohort"])
            visible = obs_rng.random(self.pool_size)[ix] >= c.online_missing
            detected = closed & (obs_rng.random(self.pool_size)[ix] < c.closure_detection)
            visible &= ~closed
            value = np.where(visible, rev >= c.threshold if c.metric == "revenue" else positive, np.nan)
            if c.metric == "sustained_profit":
                value = np.where(visible & np.isfinite(g["prev_observed_profit"]) & (age >= 2),
                                 positive & (g["prev_observed_profit"] == 1), np.nan)
            value[detected] = 0
            g["prev_observed_profit"] = np.where(visible, positive, np.nan)
            due_now = age == g["due"]
            if due_now.any():
                ids = np.where(due_now)[0]
                self.snapshots.append(dict(year=t, ops=g["op"][ids], value=value[ids], group=g, indices=ids))
            if keep_panel and age <= c.horizon:
                self.panel.append(pd.DataFrame(dict(id=g["cohort"] * self.pool_size + ix, co=g["cohort"],
                    age=age, year=t, op=g["op"], sector=np.array(self.bundle.sectors)[g["sector"]],
                    state=g["state"], duration=g["duration"], rev=rev, profit=profit, closed=closed,
                    quality=g["quality"], speed=g["speed"], observed_speed=g["observed_speed"],
                    online_rev=np.where(visible, rev, np.nan), online_profit=np.where(visible, profit, np.nan),
                    closure_known=detected, target=g["target"], support=np.where(age < c.support_years, support[g["op"]], 0))))
        for j in range(c.operators):
            self.allocations.append(dict(year=t, op=j, score=score[j], weight=self.weights[j], quota=q[j],
                                         unfilled=unfilled[j], support=support[j], active=active[j]))
        self.history.append(dict(year=t, hhi=float(np.sum(self.weights**2)), turnover=float(np.abs(self.weights - old).sum() / 2),
                                 unknown=self.last_unknown, filled=int(q.sum() - unfilled.sum()),
                                 response=active_policy.response, exploration=active_policy.exploration,
                                 target_reward=reward, phase="warmup" if t < c.warmup else "policy" if t <= self.last_birth else "tail"))
        self.last_reward = reward
        self.t += 1
        return reward

    def finish(self):
        c = self.c
        groups = [g for g in self.groups if g["target"]]
        cumulative = np.concatenate([g["cumulative"] for g in groups]) if groups else np.array([])
        sustained = np.concatenate([g["sustained"] for g in groups]) if groups else np.array([], bool)
        revenue = np.concatenate([g["final_revenue"] for g in groups]) if groups else np.array([])
        alive = np.concatenate([g["final_alive"] for g in groups]) if groups else np.array([], bool)
        slow = np.concatenate([g["speed"] == 2 for g in groups]) if groups else np.array([], bool)
        quality = np.concatenate([g["quality"] for g in groups]) if groups else np.array([])
        budget = c.slots * c.cohorts * c.unit_cost
        history = pd.DataFrame(self.history)
        summary = dict(policy=self.policy.name, replicate=self.rep, allocated_budget=budget,
                       spent_budget=len(cumulative) * c.unit_cost, unused_budget=budget - len(cumulative) * c.unit_cost,
                       firms=len(cumulative), cumulative_profit=float(cumulative.sum()),
                       profit_per_budget=float(cumulative.sum() / budget) if budget else np.nan,
                       sustained_profit=int(sustained.sum()), revenue_H=float(revenue.sum()),
                       exit_H=int((~alive).sum()), slow_share=float(slow.mean()) if len(slow) else np.nan,
                       latent_quality=float(quality.mean()) if len(quality) else np.nan,
                       hhi=float(history[history.phase.eq("policy")].hhi.mean()),
                       tail_budget=float(history.loc[history.phase.eq("tail"), "filled"].sum() * c.unit_cost),
                       profit_p10=float(np.quantile(cumulative, .1)) if len(cumulative) else np.nan,
                       profit_p50=float(np.quantile(cumulative, .5)) if len(cumulative) else np.nan,
                       profit_p90=float(np.quantile(cumulative, .9)) if len(cumulative) else np.nan)
        return dict(summary=summary, history=history, allocations=pd.DataFrame(self.allocations),
                    panel=pd.concat(self.panel, ignore_index=True) if self.panel else pd.DataFrame())


def simulate(bundle, config, policy, replicate=0, keep_panel=False, controller=None):
    sim = Simulation(bundle, config, policy, replicate)
    while sim.t <= sim.end:
        sim.scores()
        action = controller(sim) if controller and config.warmup <= sim.t <= sim.last_birth else None
        sim.step(action, keep_panel)
    return sim.finish()


def survey_view(panel, bundle, seed=20260920):
    """Retrospective survey mask; never sent to agents or government scoring."""
    p = panel.copy()
    latest = p.groupby("id").tail(1).set_index("id").closed
    probability = p.id.map(latest).map(bundle.survey_missing).fillna(.1).to_numpy()
    rng = np.random.default_rng(seed)
    missing = rng.random(len(p)) < probability
    p.loc[missing | p.closed, ["rev", "profit"]] = np.nan
    p["triplezero"] = False
    from .data import states
    p["state"] = states(p, bundle.threshold)
    return p
