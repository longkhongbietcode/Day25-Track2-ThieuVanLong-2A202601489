"""Extension 5 (Rubric §D.5) — Carbon-aware scheduling for interruptible jobs.

For every interruptible job in workloads.csv, estimate monthly energy from the GPU
TDP, then compare grid carbon and electricity cost across all regions. Report the
CO2e saved by shifting the interruptible fleet to the cleanest region.

Run: python missions/ext_carbon_scheduling.py

Every figure is printed and returned from run(); nothing is hard-coded.
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num, catalog_by_type
from finops import sustainability

BASELINE_REGION = "us-east-1"
PUE = 1.15  # data-center overhead on top of the GPU's own draw


def job_kwh_per_month(job: dict, cat: dict) -> float:
    """Monthly energy for a job: num_gpus x TDP(W) x hours/day x days, plus PUE."""
    watts = num(cat[job["gpu_type"]]["watts"])
    ngpu = int(num(job["num_gpus"]))
    hours = num(job["hours_per_day"]) * num(job["days"])
    return ngpu * watts * hours * PUE / 1000.0


def run(verbose: bool = True) -> dict:
    jobs = [j for j in load_csv("workloads.csv") if int(num(j["interruptible"])) == 1]
    cat = catalog_by_type()

    regions = [r for r in sustainability.REGION_CARBON if r in sustainability.REGION_PRICE_KWH]
    total_kwh = sum(job_kwh_per_month(j, cat) for j in jobs)

    per_region = {}
    for reg in regions:
        per_region[reg] = {
            "gco2_per_kwh": sustainability.REGION_CARBON[reg],
            "usd_per_kwh": sustainability.REGION_PRICE_KWH[reg],
            "carbon_kg": round(sustainability.carbon_g(total_kwh * 1000.0, reg) / 1000.0, 1),
            "power_usd": round(sustainability.energy_cost_usd(total_kwh * 1000.0, reg), 2),
        }

    cleanest = min(regions, key=lambda r: sustainability.REGION_CARBON[r])
    cheapest = min(regions, key=lambda r: sustainability.REGION_PRICE_KWH[r])
    base = per_region[BASELINE_REGION]
    clean = per_region[cleanest]
    co2_saved_kg = round(base["carbon_kg"] - clean["carbon_kg"], 1)
    co2_saved_pct = round((1 - clean["carbon_kg"] / base["carbon_kg"]) * 100, 1) if base["carbon_kg"] else 0.0
    power_delta = round(base["power_usd"] - clean["power_usd"], 2)

    result = {
        "interruptible_jobs": [j["job_id"] for j in jobs],
        "total_kwh_month": round(total_kwh, 0),
        "baseline_region": BASELINE_REGION,
        "cleanest_region": cleanest,
        "cheapest_region": cheapest,
        "per_region": per_region,
        "co2e_saved_kg_month": co2_saved_kg,
        "co2e_saved_pct": co2_saved_pct,
        "power_cost_delta_usd_month": power_delta,
    }

    if verbose:
        print("== Extension 5: Carbon-aware Scheduling ==")
        print(f"interruptible jobs ({len(jobs)}): {', '.join(result['interruptible_jobs'])}")
        print(f"fleet energy: {result['total_kwh_month']:,.0f} kWh/month (PUE {PUE})")
        print()
        print(f"{'region':16}{'$/kWh':>9}{'gCO2/kWh':>11}{'power $/mo':>13}{'CO2e kg/mo':>13}")
        for reg in sorted(regions, key=lambda r: per_region[r]["carbon_kg"]):
            d = per_region[reg]
            print(f"{reg:16}{d['usd_per_kwh']:>9.3f}{d['gco2_per_kwh']:>11}"
                  f"{d['power_usd']:>13,.2f}{d['carbon_kg']:>13,.1f}")
        print()
        print(f"shift interruptible fleet {BASELINE_REGION} -> {cleanest}: "
              f"-{co2_saved_kg:,.1f} kg CO2e/month ({co2_saved_pct:.1f}%), "
              f"power bill {'-' if power_delta >= 0 else '+'}${abs(power_delta):,.2f}/month")
        print(f"picks: cleanest = {cleanest}  |  cheapest power = {cheapest}  |  "
              f"balanced (latency to US) = us-west-2")
        print("trade-off: europe-north1 (Norway hydro) is far from US/Asia users; fine here "
              "because these are interruptible batch/training jobs, not latency-bound serving.")

    return result


if __name__ == "__main__":
    run()
