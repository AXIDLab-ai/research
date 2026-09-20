"""Pattern calibration retains an admissible set; no policy-ranking-based fitting."""
from dataclasses import asdict, replace
import json
from pathlib import Path
import numpy as np
import pandas as pd
from .config import Policy, digest
from .data import states
from .model import simulate, survey_view

NUISANCE = {"revenue_intercept": (-1.5, 1.5), "profit_intercept": (-1.5, 1.5),
            "exit_intercept": (-1.5, 1.5), "age_effect": (-.15, .15), "duration_effect": (-.15, .15)}


def lhs(bounds, count, seed):
    rng = np.random.default_rng(seed)
    cols = {}
    for key, (low, high) in bounds.items():
        values = (rng.permutation(count) + rng.random(count)) / count
        cols[key] = low + (high - low) * values
    return pd.DataFrame(cols)


def moments(panel, threshold=1000):
    p = panel.copy().sort_values(["id", "age"])
    if "triplezero" not in p:
        p["triplezero"] = False
    p["state"] = states(p, threshold)
    rows = []
    def add(sec, age, group, name, value, scale, n):
        if np.isfinite(value):
            rows.append(dict(sector=sec, age=int(age), group=group, moment=name,
                             value=float(value), scale=max(float(scale), .01), n=int(n)))
    for (sector, age), g in p.groupby(["sector", "age"]):
        n = len(g)
        known = g.state.notna()
        for k in range(5):
            add(sector, age, "state", f"state{k}", g.loc[known, "state"].eq(k).mean(), .15, known.sum())
        add(sector, age, "missing", "missing_financial", (g.rev.isna() | g.profit.isna()).mean(), .15, n)
        add(sector, age, "closure", "closed", g.closed.mean(), .08, n)
        for column in ("rev", "profit"):
            x = g.loc[~g.closed, column].dropna()
            if not len(x):
                continue
            transformed = np.arcsinh(x / threshold)
            for quantile in (.1, .5, .9):
                add(sector, age, "financial", f"{column}_asinh_q{quantile}", transformed.quantile(quantile), .5, len(x))
            add(sector, age, "zero", f"{column}_zero", x.eq(0).mean(), .15, len(x))
        prev = p.groupby("id")[["age", "state"]].shift()
        pair = g[g.age.eq(prev.loc[g.index, "age"] + 1) & g.state.notna() & prev.loc[g.index, "state"].notna()]
        if len(pair):
            changed = pair.state.ne(prev.loc[pair.index, "state"])
            add(sector, age, "transition", "state_change", changed.mean(), .2, len(pair))
            for k in range(4):
                src = pair[prev.loc[pair.index, "state"].eq(k)]
                if len(src):
                    add(sector, age, "transition", f"from{k}_to3", src.state.eq(3).mean(), .2, len(src))
    return pd.DataFrame(rows, columns=["sector", "age", "group", "moment", "value", "scale", "n"])


def discrepancies(target, simulated, min_n=10):
    keys = ["sector", "age", "group", "moment"]
    eligible = target[target.n.ge(min_n)].copy()
    join = eligible.merge(simulated[keys + ["value"]], on=keys, how="left", suffixes=("_target", "_sim"))
    if join.empty:
        return float("inf"), pd.DataFrame(), join
    join["error"] = (join.value_sim - join.value_target) / join.scale
    # Missing simulated patterns cannot disappear from the objective.
    join["squared_error"] = join.error.pow(2).fillna(1e6)
    groups = join.groupby("group", as_index=False).squared_error.mean()
    groups["rmse"] = np.sqrt(groups.squared_error)
    return float(np.sqrt(groups.squared_error.mean())), groups, join


def calibrate(bundle, config, count=60, repetitions=5, tolerance=1.5, min_n=10, progress=None):
    from .reporting import code_hash
    if count < 1 or repetitions < 1 or tolerance <= 0:
        raise ValueError("Candidate count, repetitions and tolerance must be positive")
    target = moments(bundle.train, bundle.threshold)
    candidates = lhs(NUISANCE, count, config.seed + 701)
    trials, accepted, diagnostics = [], [], []
    for i, row in candidates.iterrows():
        params = row.to_dict()
        cfg = replace(config, **params, horizon=max(5, config.horizon))
        try:
            patterns = []
            for rep in range(repetitions):
                out = simulate(bundle, cfg, Policy(), rep, keep_panel=True)
                panel = out["panel"]
                observed = survey_view(panel[panel.target], bundle, config.seed + rep + 5000)
                patterns.append(moments(observed[observed.age.le(2)], bundle.threshold))
            keys = ["sector", "age", "group", "moment"]
            simulated = pd.concat(patterns).groupby(keys, as_index=False).agg(value=("value", "mean"))
            loss, groups, detail = discrepancies(target, simulated, min_n)
            passed = bool(len(groups) and np.isfinite(loss) and groups.rmse.le(tolerance).all())
            error = ""
        except Exception as exc:
            loss, passed, detail, error = float("inf"), False, pd.DataFrame(), repr(exc)
        item = dict(candidate=int(i), loss=loss, accepted=passed, error=error, **params)
        trials.append(item)
        if passed:
            accepted.append(dict(id=f"set{i:04}", parameters=params, loss=loss))
        detail["candidate"] = i
        diagnostics.append(detail)
        if progress:
            progress(i + 1, count, item)
    return dict(trials=pd.DataFrame(trials), accepted=accepted, target=target,
                discrepancies=pd.concat(diagnostics, ignore_index=True) if diagnostics else pd.DataFrame(),
                specification=dict(config=asdict(config), data_hash=bundle.hash, code_hash=code_hash(), threshold=bundle.threshold,
                                   nuisance_bounds=NUISANCE, tolerance=tolerance, min_n=min_n,
                                   repetitions=repetitions, candidates=count, groups_equal_weight=True,
                                   selection="all eligible groups RMSE <= tolerance; no best-only fallback"))


def diagnostic_splits(bundle, config, repetitions=5):
    """All splits were previously inspected: these are transport diagnostics, not blind validation."""
    parts = []
    for name, frame in (("calibration_0_2", bundle.train),
                        ("mature_3_5", bundle.panel[bundle.panel.co.le(2019) & bundle.panel.age.between(3, 5)]),
                        ("recent_0_2", bundle.panel[bundle.panel.co.between(2020, 2022) & bundle.panel.age.le(2)]),
                        ("older_6_8", bundle.panel[bundle.panel.co.le(2016) & bundle.panel.age.between(6, 8)])):
        target = moments(frame, bundle.threshold)
        samples = []
        for rep in range(repetitions):
            out = simulate(bundle, replace(config, horizon=max(8, config.horizon)), Policy(), rep, True)
            p = out["panel"]
            obs = survey_view(p[p.target], bundle, config.seed + rep + 5000)
            samples.append(moments(obs, bundle.threshold))
        keys = ["sector", "age", "group", "moment"]
        average = pd.concat(samples).groupby(keys, as_index=False).value.mean()
        loss, groups, detail = discrepancies(target, average)
        detail["split"], detail["overall_rmse"] = name, loss
        parts.append(detail)
    return pd.concat(parts, ignore_index=True)


def save_calibration(result, path):
    path = Path(path); path.mkdir(parents=True, exist_ok=True)
    for name in ("trials", "target", "discrepancies"):
        result[name].to_csv(path / f"{name}.csv", index=False)
    payload = dict(accepted=result["accepted"], specification=result["specification"])
    (path / "accepted.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path / "accepted.json"


def load_accepted(path, bundle, config):
    from .reporting import code_hash
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    spec = value["specification"]
    if spec.get("code_hash") != code_hash():
        raise ValueError("Calibration code hash differs. Preserve the original checkout or recalibrate.")
    if spec["data_hash"] != bundle.hash or spec["threshold"] != bundle.threshold:
        raise ValueError("Calibration data/threshold differs from current input")
    # Structural and observation assumptions are frozen within a calibration world.
    runtime_only = {"seed", "cohorts", "horizon", "metric", "discount", "unit_cost"}
    for key, v in spec["config"].items():
        current = getattr(config, key)
        if isinstance(current, tuple):
            current = list(current)
        if key not in runtime_only and key not in NUISANCE and current != v:
            raise ValueError(f"Calibration world mismatch: {key}; recalibrate this world")
    if not value["accepted"]:
        raise ValueError("No admissible parameter set. Revise model/data assumptions transparently; do not substitute best trial.")
    return [(x["id"], replace(config, **x["parameters"])) for x in value["accepted"]]
