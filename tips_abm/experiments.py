"""E1–E6 orchestration, paired repetitions, resumable files, no implicit large runs."""
from dataclasses import asdict, replace
from pathlib import Path
import json
import time
import traceback
import numpy as np
import pandas as pd
from .config import Config, Policy, digest, policy_grid, structural_worlds
from .model import simulate, quotas, softmax, random_stream
from .calibration import lhs
from .reporting import manifest, summary_tables, export_zip, code_hash


def presets():
    return [Policy(), Policy("common2", 2, .75), Policy("common5", 5, .75),
            Policy("speed_adjusted", 3, .75, 0, True), Policy("gentle", 2, .25),
            Policy("exploration", 2, .75, .25), Policy("equal", equal=True)]


def variants(config, family="main", samples=12):
    if family == "main":
        return [("base", config)]
    if family == "worlds":
        return structural_worlds(config)
    if family == "ablation":
        changes = {"no_adaptation": {"adaptation": 0}, "homogeneous_ability": {"homogeneous_abilities": True},
                   "no_support": {"support_effect": 0}, "no_dilution": {"dilution": False},
                   "no_delay": {"delay_effect": 0}, "complete_online": {"online_missing": 0, "closure_detection": 1}}
    elif family == "information":
        changes = {"exact_speed": {"misclassification": 0}, "better_signal": {"signal_noise": .25},
                   "complete_online": {"online_missing": 0, "closure_detection": 1},
                   "archive": {"erase_after_exit": False}, "no_archive": {"erase_after_exit": True}}
    elif family == "sensitivity":
        settings = {"horizon": [5, 10], "warmup": [0, 10], "unknown_credit": [0, 1],
                    "observed_only": [True], "misclassification": [0, .5], "candidate_ratio": [1, 5],
                    "operators": [6, 24], "ability_correlation": [-.5, .5], "tail_entries": [True],
                    "shock_ar": [0, .9], "emission_family": ["independent", "lognormal"],
                    "beta": [0, 5], "prior_strength": [0, 20], "support_years": [2, 8],
                    "discount": [.03, .05], "sector_tilt": [-1, 1], "metric": ["profit", "sustained_profit"]}
        changes = {f"{k}_{v}": {k: v} for k, values in settings.items() for v in values if getattr(config, k) != v}
        changes["sector_delay_illustration"] = {"sector_delay_shift": (.4, -.4, .2, -.2, 0.0)}
    elif family == "lhs":
        bounds = {"misclassification": (0, .5), "signal_noise": (.2, 2), "quality_delay": (-.5, .5),
                  "support_effect": (0, .5), "adaptation": (0, 2), "online_missing": (0, .4),
                  "ability_correlation": (-.5, .5), "delay_effect": (0, .7)}
        return [(f"lhs_{i:03}", replace(config, **r.to_dict())) for i, r in lhs(bounds, samples, config.seed + 900).iterrows()]
    else:
        raise ValueError("Unknown experiment family")
    return [("base", config)] + [(name, replace(config, **changes_)) for name, changes_ in changes.items()]


def run_batch(bundle, worlds, policies, repetitions, output=None, progress=None, keep_panel=False):
    """worlds = [(world_name, parameter_set_name, Config)]. Hash-addressed completed jobs resume."""
    if repetitions < 1:
        raise ValueError("At least one repetition is required")
    if bundle.threshold != worlds[0][2].threshold:
        raise ValueError("Rebuild the input bundle at the requested revenue threshold")
    directory = Path(output) if output else None
    if directory:
        directory.mkdir(parents=True, exist_ok=True)
    meta = manifest(bundle, {"policies": [asdict(p) for p in policies],
                            "worlds": [dict(world=w, parameter_set=s, config=asdict(c)) for w, s, c in worlds],
                            "repetitions": repetitions, "uncertainty": "MC within each structural world and parameter set",
                            "run_type": "pilot" if repetitions < 200 else "research_repetition_count"})
    total = len(worlds) * len(policies) * repetitions
    raw, histories, failures = [], [], []
    started = time.perf_counter()
    done = 0
    for world, parameter_set, config in worlds:
        config.validate()
        if config.threshold != bundle.threshold:
            raise ValueError("Threshold changes require rebuilding and recalibrating input bundles")
        for rep in range(repetitions):
            for policy in policies:
                spec = dict(world=world, parameter_set=parameter_set, config=asdict(config), policy=asdict(policy),
                            replicate=rep, input=bundle.hash, code=meta["code_hash"], keep_panel=keep_panel)
                run_id = digest(spec)
                dest = directory / run_id if directory else None
                try:
                    if dest and (dest / "complete.json").exists():
                        value = json.loads((dest / "complete.json").read_text(encoding="utf-8"))
                        # A completion marker is committed only after its detail files are written.
                        history = pd.read_csv(dest / "history.csv")
                    else:
                        result = simulate(bundle, config, policy, rep, keep_panel)
                        value = {**result["summary"], "world": world, "parameter_set": parameter_set, "run_id": run_id}
                        history = result["history"].assign(world=world, parameter_set=parameter_set, policy=policy.name, replicate=rep)
                        if dest:
                            dest.mkdir(exist_ok=True)
                            history.to_csv(dest / "history.csv", index=False)
                            result["allocations"].to_csv(dest / "allocations.csv", index=False)
                            if keep_panel:
                                result["panel"].to_csv(dest / "panel.csv", index=False)
                            (dest / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
                            temporary = dest / "complete.tmp"
                            temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
                            temporary.replace(dest / "complete.json")
                    raw.append(value); histories.append(history)
                except Exception as exc:
                    failure = dict(run_id=run_id, world=world, parameter_set=parameter_set, policy=policy.name,
                                   replicate=rep, error=str(exc), traceback=traceback.format_exc())
                    failures.append(failure)
                    if directory:
                        with (directory / "failures.jsonl").open("a", encoding="utf-8") as f:
                            f.write(json.dumps(failure, ensure_ascii=False) + "\n")
                done += 1
                if progress:
                    progress(done, total)
    meta.update(elapsed_seconds=time.perf_counter() - started, completed=len(raw), failures=len(failures), planned=total)
    raw = pd.DataFrame(raw)
    if raw.empty:
        first_error = failures[0]["error"] if failures else "No jobs scheduled"
        raise RuntimeError(f"No completed simulations: {first_error}. Inspect failures.jsonl when using CLI.")
    # Paired comparison is restricted to complete blocks; a failed policy is not silently dropped.
    block = ["world", "parameter_set", "replicate"]
    complete_keys = raw.groupby(block).policy.nunique().eq(len(policies))
    indexed = raw.set_index(block)
    paired_input = indexed.loc[indexed.index.isin(complete_keys[complete_keys].index)].reset_index()
    tables = {"raw": raw, "history": pd.concat(histories, ignore_index=True), "failures": pd.DataFrame(failures)}
    if len(paired_input):
        tables.update(summary_tables(paired_input))
    meta["complete_comparison_blocks"] = int(complete_keys.sum())
    if directory:
        for name, frame in tables.items():
            frame.to_csv(directory / f"{name}.csv", index=False)
        (directory / "manifest.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        (directory / "report.zip").write_bytes(export_zip(tables, meta))
    return tables, meta


def replay(bundle, config, policies=None):
    """E1: fixed historical outcomes; allocation path is hypothetical, never causal."""
    policies = policies or [p for p in presets() if not p.differentiated]
    p = bundle.panel[bundle.panel.co.le(2019)].copy()
    operators = sorted(p.op.unique()); j = len(operators)
    op_code = {op: i for i, op in enumerate(operators)}
    initial = p[p.age.eq(0)].op.value_counts().reindex(operators, fill_value=0).to_numpy(float)
    initial = initial / initial.sum()
    rows = []
    for policy in policies:
        if policy.differentiated:
            raise ValueError("Historical speed labels are unobserved; E1 cannot use differentiated speed policy")
        w = initial.copy()
        due = p[p.age.eq(policy.horizon)].copy()
        value = due.rev.ge(config.threshold) if config.metric == "revenue" else due.profit.gt(0)
        known = due.rev.notna() if config.metric == "revenue" else due.profit.notna()
        if config.metric == "sustained_profit":
            prior = p[p.age.eq(policy.horizon - 1)].set_index("id").profit
            before = due.id.map(prior)
            value &= before.gt(0)
            known &= before.notna()
        due["value"] = np.where(known, value, np.nan)
        due.loc[due.closed, "value"] = 0
        for year in range(int(p.co.min()) + 1, int(p.year.max()) + 2):
            eligible = due[due.year.between(year - config.score_window, year - 1)]
            numerator = np.full(j, config.prior_strength * config.prior_mean)
            denominator = np.full(j, config.prior_strength)
            for op, g in eligible.groupby("op"):
                k = op_code[op]
                numerator[k] += g.value.fillna(0 if config.observed_only else config.unknown_credit).sum()
                denominator[k] += g.value.count() if config.observed_only else len(g)
            scores = np.divide(numerator, denominator, out=np.full(j, config.prior_mean), where=denominator > 0)
            target = (1 - policy.exploration) * softmax(config.beta * scores) + policy.exploration / j
            w = np.full(j, 1 / j) if policy.equal else (1 - policy.response) * w + policy.response * target
            allocation = quotas(w, config.slots, random_stream(config.seed, 0, 77, year))
            for k, op in enumerate(operators):
                rows.append(dict(policy=policy.name, year=year, operator_code=op, score=scores[k],
                                 weight=w[k], hypothetical_slots=allocation[k], outcome_path="fixed historical records"))
    return pd.DataFrame(rows)


def precision_plan(raw, metric="profit_per_budget", half_width=.1, minimum=200, maximum=2000):
    keys = [k for k in ("world", "parameter_set", "replicate") if k in raw]
    pair = raw.merge(raw[raw.policy.eq("fixed")][keys + [metric]], on=keys, suffixes=("", "_fixed"))
    pair["delta"] = pair[metric] - pair[metric + "_fixed"]
    group = [k for k in ("world", "parameter_set", "policy") if k in pair]
    if half_width <= 0:
        raise ValueError("Target half width must be positive")
    out = pair.groupby(group, as_index=False).agg(sd=("delta", "std"), pilot_repetitions=("delta", "count"))
    required = np.ceil((1.96 * out["sd"] / half_width)**2)
    out["requested_repetitions"] = required.clip(minimum, maximum)
    out["exceeds_cap"] = required > maximum
    out["target_half_width"] = half_width
    return out
