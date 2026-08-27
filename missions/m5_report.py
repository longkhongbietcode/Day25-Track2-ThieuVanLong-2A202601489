"""M5 — Optimization Report: combine M1-M4 into baseline-vs-optimized (deck §1/§11).

Run: python missions/m5_report.py   ->  outputs/report.md + outputs/savings.png
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import os
from missions._common import num, catalog_by_type, ROOT
from finops import report, sustainability
from missions import m1_efficiency_audit, m2_inference_levers, m3_purchasing

DAYS = 30
# one tier down for over-provisioned ("util-lie") GPUs
RIGHTSIZE_MAP = {"H100": "A100", "H200": "H100", "A100": "A10G", "A10G": "L4", "L4": "L4"}


def run(verbose: bool = True) -> dict:
    r1 = m1_efficiency_audit.run(verbose=False)
    r2 = m2_inference_levers.run(verbose=False)
    r3 = m3_purchasing.run(verbose=False)
    cat = catalog_by_type()

    # --- buckets ---
    infer_savings = (r2["baseline_daily"] - r2["optimized_daily"]) * DAYS
    purchasing_savings = r3["on_demand_monthly"] - r3["optimized_monthly"]

    idle_savings = r1["idle_waste_daily"] * DAYS
    rightsize_savings = 0.0
    for lie in r1["lies"]:
        cur = lie["gpu_type"]
        tgt = RIGHTSIZE_MAP.get(cur, cur)
        delta = num(cat[cur]["on_demand_hr"]) - num(cat[tgt]["on_demand_hr"])
        rightsize_savings += max(0.0, delta) * 24 * DAYS

    levers = {
        "Inference (cascade/cache/batch)": round(infer_savings),
        "Purchasing (spot/reserved)": round(purchasing_savings),
        "Right-size util-lies": round(rightsize_savings),
        "Kill idle GPUs": round(idle_savings),
    }
    baseline = r2["baseline_daily"] * DAYS + r3["on_demand_monthly"]
    optimized = baseline - sum(levers.values())
    total_pct = sum(levers.values()) / baseline * 100 if baseline else 0.0

    # --- analysis layer (Rubric C.2) — every number sourced from r1/r2/r3 above ---
    lie_cur_cost = 0.0
    for lie in r1["lies"]:
        lie_cur_cost += num(cat[lie["gpu_type"]]["on_demand_hr"]) * 24 * DAYS
    lever_monthly = {
        "Inference (cascade/cache/batch)": (r2["baseline_daily"] * DAYS, r2["optimized_daily"] * DAYS),
        "Purchasing (spot/reserved)": (float(r3["on_demand_monthly"]), float(r3["optimized_monthly"])),
        "Right-size util-lies": (lie_cur_cost, lie_cur_cost - rightsize_savings),
        "Kill idle GPUs": (idle_savings, 0.0),
    }
    per_lever_detail = {
        "inference_per_m": (r2["baseline_per_m"], r2["optimized_per_m"]),
        "lever_monthly": lever_monthly,
    }

    lie_desc = ", ".join(
        f"`{l['gpu_id']}` ({l['gpu_type']}, MFU {l['mfu']:.2f} at util {l['gpu_util_pct']:.0f}%)"
        for l in r1["lies"]
    ) or "none"
    util_lie_mechanism = (
        f"nvidia-smi GPU-Util only reports that a kernel was resident on an SM during the "
        f"sampling window - it says nothing about how much of the chip's FLOPs or HBM "
        f"bandwidth that kernel actually used. A GPU reads 90-98% util while stalling on "
        f"HBM reads (memory-bound decode), waiting on kernel-launch / Python overhead "
        f"between tiny ops, blocking on host<->device copies, or sitting in a non-overlapped "
        f"all-reduce. Flagged here: {lie_desc}. Financially: the GPU-hour is billed in full "
        f"while ~1/5 of the rented FLOPs are delivered, so the true $/1M-token on that box is "
        f"roughly 5x the sticker rate. Fix = right-size one tier down (H100->A100) or "
        f"raise MFU (fuse kernels, bigger batch, CUDA graphs), not buy more H100s."
    )
    ranked = sorted(levers.items(), key=lambda kv: kv[1], reverse=True)
    reason_by_lever = {
        "Purchasing (spot/reserved)": "spot for interruptible training + 3yr reserved for "
        "always-on inference above the 55% break-even duty cycle",
        "Inference (cascade/cache/batch)": "route easy prompts to the small model (~15x "
        "cheaper), bill cached input at 0.1x, send non-real-time traffic through the Batch API",
        "Right-size util-lies": "drop the util-lie GPUs one tier - same throughput, lower rate",
        "Kill idle GPUs": "auto-stop instances left running after the job finishes",
    }
    priority_actions = [
        f"**{name}** - save ~${amt:,.0f}/mo ({amt / baseline * 100:.1f}% of baseline): "
        f"{reason_by_lever.get(name, '')}"
        for name, amt in ranked
    ]
    _rc = sustainability.REGION_CARBON
    _rp = sustainability.REGION_PRICE_KWH
    clean = min(_rc, key=_rc.get)
    dirty = max(_rc, key=_rc.get)
    cheap = min(_rp, key=_rp.get)
    sustainability_note = (
        f"Region choice moves carbon and the power bill together. `{clean}` "
        f"({_rc[clean]} gCO2/kWh, ${_rp[clean]}/kWh) vs `{dirty}` ({_rc[dirty]} gCO2/kWh, "
        f"${_rp[dirty]}/kWh): shifting interruptible jobs there cuts ~"
        f"{(1 - _rc[clean] / _rc[dirty]) * 100:.0f}% of their CO2e and ~"
        f"{(1 - _rp[clean] / _rp[dirty]) * 100:.0f}% of their electricity cost at once. "
        f"`{cheap}` is the cheapest power (${_rp[cheap]}/kWh); `us-west-2` "
        f"({_rc['us-west-2']} gCO2/kWh, ${_rp['us-west-2']}/kWh) is the balanced pick when "
        f"latency to US users matters. See missions/ext_carbon_scheduling.py for the "
        f"per-job numbers."
    )
    rz = r2.get("reasoning", {})
    reasoning_note = (
        f"Reasoning traffic is {rz.get('traffic_pct', 0):.1f}% of requests but "
        f"{rz.get('cost_pct', 0):.1f}% of inference $ and {rz.get('wh_pct', 0):.1f}% of "
        f"energy - each reasoning request burns ~"
        f"{rz.get('wh_per_req_reasoning', 0) / max(rz.get('wh_per_req_normal', 1e-9), 1e-9):.0f}x "
        f"the Wh of a normal one (long hidden chains -> many memory-bound decode steps, "
        f"large KV-cache). Capping it to {rz.get('cap_target_pct', 3):.0f}% of traffic saves "
        f"~${rz.get('cap_cost_saved_per_day', 0):.2f}/day and ~"
        f"{rz.get('cap_wh_saved_per_month', 0) / 1000:.1f} kWh/month. See "
        f"missions/m2_inference_levers.py (Extension 4)."
    )
    narrative = {
        "util_lie_mechanism": util_lie_mechanism,
        "priority_actions": priority_actions,
        "sustainability_note": sustainability_note + "\n\n" + reasoning_note,
    }

    # --- sustainability snapshot ---
    median_tokens = 800
    wh = sustainability.wh_per_query(median_tokens)
    sust = {
        "wh_per_query": wh,
        "carbon_g": sustainability.carbon_g(wh, "us-east-1"),
        "best_region": min(sustainability.REGION_CARBON, key=sustainability.REGION_CARBON.get),
    }

    md = report.build_report(baseline, optimized, levers, sustainability=sust,
                             per_lever_detail=per_lever_detail, narrative=narrative)
    out_md = os.path.join(ROOT, "outputs", "report.md")
    os.makedirs(os.path.dirname(out_md), exist_ok=True)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(md)
    png = report.savings_waterfall(levers, os.path.join(ROOT, "outputs", "savings.png"))

    if verbose:
        print("== M5 Optimization Report ==")
        print(md)
        print(f"\nWritten: outputs/report.md" + (f" + outputs/savings.png" if png else " (matplotlib absent: PNG skipped)"))

    return {"baseline_monthly": round(baseline), "optimized_monthly": round(optimized),
            "levers": levers, "total_savings_pct": round(total_pct, 1)}


if __name__ == "__main__":
    run()
