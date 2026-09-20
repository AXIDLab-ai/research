from pathlib import Path
import hashlib
import importlib.metadata
import json
import platform
import os
from datetime import datetime, timezone
import io
import zipfile
import numpy as np
import pandas as pd
from . import __version__

METRICS = ["profit_per_budget", "sustained_profit", "revenue_H", "exit_H", "slow_share", "hhi", "latent_quality"]


def code_hash():
    root = Path(__file__).resolve().parent
    h = hashlib.sha256()
    for p in sorted(root.glob("*.py")):
        h.update(p.name.encode()); h.update(p.read_bytes())
    return h.hexdigest()


def manifest(bundle, extra=None):
    versions = {}
    for name in ("numpy", "pandas", "streamlit", "openpyxl"):
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "not installed"
    return dict(version=__version__, created_utc=datetime.now(timezone.utc).isoformat(), code_hash=code_hash(),
                input_hash=bundle.hash, synthetic=bundle.metadata.get("synthetic", False),
                bootstrap=bundle.metadata.get("bootstrap"), parent_input_hash=bundle.metadata.get("parent_hash"),
                units=bundle.metadata.get("units"), python=platform.python_version(),
                platform=platform.platform(), dependencies=versions,
                logical_cpus=os.cpu_count(), processor=platform.processor(),
                inference="conditional ABM scenarios; not identified TIPS causal effects", **(extra or {}))


def summary_tables(raw):
    identifiers = [c for c in ("world", "parameter_set", "policy") if c in raw]
    long = raw.melt(id_vars=identifiers + ["replicate"], value_vars=METRICS, var_name="metric", value_name="value")
    summary = long.groupby(identifiers + ["metric"], as_index=False).agg(mean=("value", "mean"), sd=("value", "std"), repetitions=("value", "count"))
    summary["mcse"] = summary.sd / np.sqrt(summary.repetitions)
    summary["mc_lo"], summary["mc_hi"] = summary["mean"] - 1.96 * summary.mcse, summary["mean"] + 1.96 * summary.mcse
    keys = [c for c in ("world", "parameter_set", "replicate") if c in raw]
    baseline = raw[raw.policy.eq("fixed")][keys + METRICS]
    paired = raw.merge(baseline, on=keys, suffixes=("", "_fixed"), validate="many_to_one")
    for m in METRICS:
        paired[m] = paired[m] - paired[f"{m}_fixed"]
    paired_long = paired.melt(id_vars=identifiers + ["replicate"], value_vars=METRICS, var_name="metric", value_name="difference")
    paired_summary = paired_long.groupby(identifiers + ["metric"], as_index=False).agg(difference=("difference", "mean"), sd=("difference", "std"), repetitions=("difference", "count"))
    paired_summary["paired_mcse"] = paired_summary.sd / np.sqrt(paired_summary.repetitions)
    means = raw.groupby(identifiers, as_index=False)[["profit_per_budget", "sustained_profit"]].mean()
    world_keys = [c for c in ("world", "parameter_set") if c in means]
    pareto = []
    iterable = means.groupby(world_keys) if world_keys else [("all", means)]
    for _, group in iterable:
        a = group[["profit_per_budget", "sustained_profit"]].to_numpy()
        for pos, (_, row) in enumerate(group.iterrows()):
            dominated = np.any(np.all(a >= a[pos], axis=1) & np.any(a > a[pos], axis=1))
            pareto.append({**row.to_dict(), "pareto": not bool(dominated),
                           "profit_regret": float(np.nanmax(a[:, 0]) - a[pos, 0]),
                           "sustained_regret": float(np.nanmax(a[:, 1]) - a[pos, 1])})
    regret = pd.DataFrame(pareto)
    robust = regret.groupby("policy", as_index=False).agg(max_profit_regret=("profit_regret", "max"),
              max_sustained_regret=("sustained_regret", "max"), scenario_pareto_fraction=("pareto", "mean"))
    return dict(summary=summary, paired=paired_summary, regret=regret, robust=robust)


def report_html(tables, metadata):
    from html import escape
    sections = ["<html><meta charset='utf-8'><title>TIPS ABM report</title><style>body{font-family:sans-serif;max-width:1200px;margin:40px auto}td,th{padding:7px;border-bottom:1px solid #ddd}table{border-collapse:collapse;font-size:13px}</style>",
                "<h1>TIPS ABM — conditional scenario report</h1>",
                "<p>MC intervals quantify simulation randomness only. Parameter, data and structural uncertainty remain separate. Scenario fractions are not probabilities. No causal TIPS effectiveness estimate.</p>",
                "<pre>" + escape(json.dumps(metadata, ensure_ascii=False, indent=2)) + "</pre>"]
    for name, df in tables.items():
        sections += [f"<h2>{escape(name)}</h2>", df.to_html(index=False, escape=True)]
    return "\n".join(sections) + "</html>"


def export_zip(tables, metadata):
    memory = io.BytesIO()
    payload = {f"{name}.csv": frame.to_csv(index=False).encode("utf-8-sig") for name, frame in tables.items()}
    payload["report.html"] = report_html(tables, metadata).encode("utf-8")
    metadata = {**metadata, "output_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in payload.items()}}
    payload["manifest.json"] = json.dumps(metadata, ensure_ascii=False, indent=2).encode("utf-8")
    with zipfile.ZipFile(memory, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in payload.items():
            z.writestr(name, content)
    return memory.getvalue()
