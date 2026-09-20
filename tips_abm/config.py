from dataclasses import asdict, dataclass, replace
import hashlib
import json


@dataclass(frozen=True)
class Config:
    operators: int = 12
    slots: int = 80
    cohorts: int = 10
    warmup: int = 5
    horizon: int = 8
    seed: int = 20260920
    candidate_ratio: float = 3.0
    support_years: int = 5
    support_effect: float = 0.25
    adaptation: float = 1.0
    quality_delay: float = 0.0
    misclassification: float = 0.25
    signal_noise: float = 1.0
    ability_correlation: float = 0.0
    homogeneous_abilities: bool = False
    dilution: bool = True
    delay_effect: float = 0.35
    quality_effect: float = 0.35
    age_effect: float = 0.08
    duration_effect: float = 0.08
    profit_intercept: float = 0.0
    revenue_intercept: float = 0.0
    exit_intercept: float = 0.0
    shock_ar: float = 0.6
    shock_scale: float = 0.15
    macro_scale: float = 0.1
    online_missing: float = 0.1
    closure_detection: float = 1.0
    erase_after_exit: bool = False
    unknown_credit: float = 0.5
    observed_only: bool = False
    score_window: int = 5
    prior_strength: float = 5.0
    prior_mean: float = 0.5
    beta: float = 2.0
    metric: str = "revenue"
    threshold: float = 1000.0
    discount: float = 0.0
    unit_cost: float = 1.0
    tail_entries: bool = False
    emission_family: str = "joint"
    sector_tilt: float = 0.0
    sector_delay_shift: tuple = (0.0, 0.0, 0.0, 0.0, 0.0)

    def validate(self):
        import math
        for key, value in asdict(self).items():
            if isinstance(value, (float, int)) and not math.isfinite(value):
                raise ValueError(f"{key} must be finite")
        for key in ("operators", "cohorts", "horizon", "support_years", "score_window"):
            if getattr(self, key) < 1:
                raise ValueError(f"{key} must be >= 1")
        if self.slots < 0 or self.warmup < 0 or self.candidate_ratio <= 0:
            raise ValueError("Invalid population or time configuration")
        for key in ("misclassification", "online_missing", "closure_detection", "unknown_credit", "prior_mean"):
            if not 0 <= getattr(self, key) <= 1:
                raise ValueError(f"{key} must be in [0,1]")
        if abs(self.quality_delay) > 1 or abs(self.ability_correlation) > 1 or abs(self.shock_ar) >= 1:
            raise ValueError("Invalid correlation")
        if self.threshold <= 0 or self.unit_cost <= 0 or self.discount < 0 or self.prior_strength < 0:
            raise ValueError("Invalid threshold, cost, discount or prior")
        if min(self.signal_noise, self.shock_scale, self.macro_scale, self.support_effect, self.adaptation) < 0:
            raise ValueError("Noise, effect and adaptation must be nonnegative")
        if self.metric not in ("revenue", "profit", "sustained_profit"):
            raise ValueError("Unknown metric")
        if self.emission_family not in ("joint", "independent", "lognormal"):
            raise ValueError("Unknown emission family")
        for key in ("operators", "slots", "cohorts", "warmup", "horizon", "seed", "support_years", "score_window"):
            if not isinstance(getattr(self, key), int):
                raise ValueError(f"{key} must be an integer")
        if self.seed < 0 or self.beta < 0:
            raise ValueError("Seed and beta must be nonnegative")
        if len(self.sector_delay_shift) != 5 or not all(math.isfinite(x) for x in self.sector_delay_shift):
            raise ValueError("sector_delay_shift must contain five finite sector offsets")
        return self


@dataclass(frozen=True)
class Policy:
    name: str = "fixed"
    horizon: int = 3
    response: float = 0.0
    exploration: float = 0.0
    differentiated: bool = False
    equal: bool = False

    def validate(self):
        if self.horizon < 1 or not 0 <= self.response <= 1 or not 0 <= self.exploration <= 1:
            raise ValueError("Invalid policy")
        return self


def policy_grid():
    result = [Policy()]
    for h in (2, 3, 5, "speed"):
        for lam in (0.25, 0.5, 1.0):
            for eps in (0.0, 0.1, 0.25):
                result.append(Policy(f"h{h}_l{lam:g}_e{eps:g}", 3 if h == "speed" else h,
                                     lam, eps, h == "speed"))
    return result


def structural_worlds(base):
    return [(f"rho{rho:g}_a{a:g}_s{s:g}", replace(base, quality_delay=rho, adaptation=a, support_effect=s))
            for rho in (-0.5, 0.0, 0.5) for a in (0.0, 1.0, 2.0) for s in (0.0, 0.25, 0.5)]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def config_from_file(path):
    from pathlib import Path
    return Config(**json.loads(Path(path).read_text(encoding="utf-8"))).validate()
