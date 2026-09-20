"""CLI entrypoints. Planning is cheap; substantial computation requires --execute."""
import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import pandas as pd
from .config import Config, config_from_file, policy_grid
from .data import Bundle, prepare_excel, synthetic_panel, bootstrap_bundle
from .calibration import calibrate, save_calibration, load_accepted, diagnostic_splits
from .experiments import presets, variants, run_batch, replay, precision_plan
from .reporting import manifest, export_zip, summary_tables


def main():
    parser = argparse.ArgumentParser(description="TIPS intermediary ABM: E0–E7")
    parser.add_argument("command", choices=["synthetic", "prepare", "audit", "replay", "calibrate", "diagnose", "run", "precision", "rl", "report"])
    parser.add_argument("--data", default="synthetic", help="Synthetic or a private bundle directory")
    parser.add_argument("--source", help="Original Excel (prepare); raw.csv (precision/report)")
    parser.add_argument("--config", help="Config JSON; default demo dimensions")
    parser.add_argument("--set", default="{}", help="JSON configuration overrides")
    parser.add_argument("--out", default="results/run")
    parser.add_argument("--family", choices=["main", "worlds", "ablation", "sensitivity", "lhs", "information"], default="main")
    parser.add_argument("--grid", action="store_true", help="37 distinct policies instead of 7 presets")
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--candidates", type=int, default=60)
    parser.add_argument("--samples", type=int, default=12)
    parser.add_argument("--episodes", type=int, default=100)
    parser.add_argument("--tolerance", type=float, default=1.5)
    parser.add_argument("--half-width", type=float, default=.1)
    parser.add_argument("--accepted", help="accepted.json or directory with one world subdirectory per structural world")
    parser.add_argument("--strict-zero", action="store_true")
    parser.add_argument("--bootstrap", type=int, default=-1, help="Operator bootstrap index; use same index for calibration and policy run")
    parser.add_argument("--keep-panel", action="store_true")
    parser.add_argument("--execute", action="store_true", help="Run calibration / simulation / diagnostics / RL (otherwise plan only)")
    args = parser.parse_args()
    cfg = config_from_file(args.config) if args.config else Config()
    cfg = replace(cfg, **json.loads(args.set)).validate()
    out = Path(args.out)
    if args.command == "prepare":
        if not args.source:
            parser.error("prepare requires --source")
        print(json.dumps(prepare_excel(args.source, out, args.strict_zero), ensure_ascii=False, indent=2))
        return
    if args.command == "synthetic":
        out.mkdir(parents=True, exist_ok=True)
        synthetic_panel().to_csv(out / "panel.csv", index=False)
        (out / "metadata.json").write_text(json.dumps({"synthetic": True, "units": "arbitrary monetary units", "seed": 20260920}), encoding="utf-8")
        print(out.resolve()); return
    if args.command in ("precision", "report"):
        if not args.source:
            parser.error("--source raw.csv is required")
        raw = pd.read_csv(args.source)
        out.mkdir(parents=True, exist_ok=True)
        if args.command == "precision":
            precision_plan(raw, half_width=args.half_width).to_csv(out / "precision_plan.csv", index=False)
        else:
            (out / "report.zip").write_bytes(export_zip({"raw": raw, **summary_tables(raw)}, {"source": "user supplied raw.csv; consult original manifest"}))
        print(out.resolve()); return
    bundle = Bundle.load(args.data, cfg.threshold, args.strict_zero)
    if args.bootstrap >= 0:
        bundle = bootstrap_bundle(bundle, args.bootstrap, cfg.seed)
    if args.command == "audit":
        out.mkdir(parents=True, exist_ok=True)
        p = bundle.panel
        p.groupby(["co", "age", "sector"]).agg(n=("id", "size"), revenue_observed=("rev", "count"),
            profit_observed=("profit", "count"), closure=("closed", "sum"), triple_zero=("triplezero", "sum")).reset_index().to_csv(out / "coverage.csv", index=False)
        (out / "audit.json").write_text(json.dumps(manifest(bundle, bundle.metadata), ensure_ascii=False, indent=2), encoding="utf-8")
        print(out.resolve()); return
    if args.command == "replay":
        out.mkdir(parents=True, exist_ok=True)
        replay(bundle, cfg).to_csv(out / "fixed_path_replay.csv", index=False)
        print(out.resolve()); return
    worlds = variants(cfg, args.family, args.samples)
    policies = policy_grid() if args.grid else presets()
    plan = dict(command=args.command, synthetic=bundle.metadata["synthetic"], worlds=len(worlds),
                policies=len(policies), repetitions=args.repetitions,
                uncalibrated=args.accepted is None, output=str(out.resolve()),
                baseline_jobs=len(worlds) * len(policies) * args.repetitions,
                calibration_jobs=len(worlds) * args.candidates * args.repetitions,
                warning="Accepted sets multiply policy jobs; no causal interpretation")
    print(json.dumps(plan, ensure_ascii=False, indent=2), flush=True)
    if not args.execute:
        print("Plan only. Add --execute to run."); return
    progress = lambda current, total, *rest: print(f"{current}/{total}", flush=True)
    if args.command == "calibrate":
        for name, config in worlds:
            result = calibrate(bundle, config, args.candidates, args.repetitions, args.tolerance, progress=progress)
            location = save_calibration(result, out / name)
            print(f"{name}: admissible sets={len(result['accepted'])}; {location}", flush=True)
    elif args.command == "diagnose":
        if not args.accepted:
            parser.error("diagnose requires --accepted (all accepted sets are reported)")
        out.mkdir(parents=True, exist_ok=True)
        for name, config in load_accepted(args.accepted, bundle, cfg):
            diagnostic_splits(bundle, config, args.repetitions).to_csv(out / f"{name}_diagnostics.csv", index=False)
    elif args.command == "run":
        jobs = []
        frozen_sets = None
        if args.accepted and args.family in ("ablation", "sensitivity", "lhs", "information"):
            path = Path(args.accepted)
            if path.is_dir():
                path = path / "base" / "accepted.json"
            frozen_sets = load_accepted(path, bundle, cfg)
        for world, config in worlds:
            if frozen_sets:
                changed = {k: v for k, v in asdict(config).items() if v != asdict(cfg)[k]}
                sets = [(name, replace(fitted, **changed)) for name, fitted in frozen_sets]
            elif args.accepted:
                path = Path(args.accepted)
                if path.is_dir():
                    path = path / world / "accepted.json"
                sets = load_accepted(path, bundle, config)
            else:
                sets = [("uncalibrated", config)]
            jobs.extend((world, name, p) for name, p in sets)
        tables, meta = run_batch(bundle, jobs, policies, args.repetitions, out, progress, args.keep_panel)
        print(json.dumps(meta, ensure_ascii=False, indent=2))
    elif args.command == "rl":
        from .learning import train, evaluate
        if args.family != "main":
            parser.error("RL is a separately frozen extension; one specified world per run")
        out.mkdir(parents=True, exist_ok=True)
        sets = load_accepted(args.accepted, bundle, cfg) if args.accepted else [("uncalibrated", cfg)]
        for name, config in sets:
            learned, log = train(bundle, config, args.episodes, progress=progress)
            destination = out / name; destination.mkdir(exist_ok=True)
            (destination / "policy.json").write_text(json.dumps(learned, indent=2), encoding="utf-8")
            log.to_csv(destination / "training.csv", index=False)
            results = evaluate(bundle, config, learned, args.repetitions)
            results.to_csv(destination / "evaluation.csv", index=False)
            (destination / "report.zip").write_bytes(export_zip({"raw": results, **summary_tables(results)}, manifest(bundle, {"config": asdict(config), "extension": "E7"})))


if __name__ == "__main__":
    main()
