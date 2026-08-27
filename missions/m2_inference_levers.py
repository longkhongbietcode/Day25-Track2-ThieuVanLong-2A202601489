"""M2 — Inference Cost Levers: $/1M-token, batch x cache x cascade (deck §7).

Run: python missions/m2_inference_levers.py

Extension 4 (Rubric §D.4 — Reasoning Budget): splits $ and Wh by is_reasoning and
estimates the saving from capping reasoning traffic. All numbers printed, sourced
from token_usage.csv — see run()["reasoning"].
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num
from finops import pricing, sustainability

# $/1M tokens (input, output) — illustrative 2026.
MODEL_PRICES = {"small": (0.20, 0.40), "large": (3.00, 15.00)}

# Extension 4 knob: target share of traffic still allowed to use reasoning.
REASONING_CAP_FRAC = 0.03


def run(verbose: bool = True) -> dict:
    rows = load_csv("token_usage.csv")
    base_cost = opt_cost = 0.0
    total_tokens = 0

    # Extension 4 accumulators
    rb = {
        1: {"n": 0, "tok": 0, "cost": 0.0, "wh": 0.0},
        0: {"n": 0, "tok": 0, "cost": 0.0, "wh": 0.0},
    }

    for r in rows:
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        cached = int(num(r["cached_input_tokens"]))
        is_batch = bool(int(num(r["is_batch"])))
        is_reasoning = bool(int(num(r["is_reasoning"])))
        total_tokens += inp + out
        # BASELINE: naive deployment — everything on the large model, no cache, no batch
        lin, lout = MODEL_PRICES["large"]
        base_cost += pricing.request_cost(inp, out, lin, lout)
        # OPTIMIZED: cascade (route_tier), prompt caching, batch API
        pin, pout = MODEL_PRICES[r["route_tier"]]
        rcost = pricing.request_cost(inp, out, pin, pout, cached_in=cached, batch=is_batch)
        opt_cost += rcost

        b = rb[1 if is_reasoning else 0]
        b["n"] += 1
        b["tok"] += inp + out
        b["cost"] += rcost
        b["wh"] += sustainability.wh_per_query(inp + out, is_reasoning=is_reasoning)

    base_pm = pricing.dollars_per_million(base_cost, total_tokens)
    opt_pm = pricing.dollars_per_million(opt_cost, total_tokens)
    savings_pct = (1 - opt_cost / base_cost) * 100 if base_cost else 0.0

    # --- Extension 4: reasoning budget -------------------------------------
    n_total = rb[1]["n"] + rb[0]["n"]
    cost_total = rb[1]["cost"] + rb[0]["cost"]
    wh_total = rb[1]["wh"] + rb[0]["wh"]
    reasoning = {
        "traffic_pct": rb[1]["n"] / n_total * 100 if n_total else 0.0,
        "token_pct": rb[1]["tok"] / (rb[1]["tok"] + rb[0]["tok"]) * 100 if (rb[1]["tok"] + rb[0]["tok"]) else 0.0,
        "cost_pct": rb[1]["cost"] / cost_total * 100 if cost_total else 0.0,
        "wh_pct": rb[1]["wh"] / wh_total * 100 if wh_total else 0.0,
        "reasoning_cost": round(rb[1]["cost"], 4),
        "reasoning_wh": round(rb[1]["wh"], 1),
        "wh_per_req_reasoning": rb[1]["wh"] / rb[1]["n"] if rb[1]["n"] else 0.0,
        "wh_per_req_normal": rb[0]["wh"] / rb[0]["n"] if rb[0]["n"] else 0.0,
    }
    # Scenario: cap reasoning share to REASONING_CAP_FRAC. The excess requests are
    # answered without the reasoning path -> lose the ~80x energy multiplier and
    # (assumed) drop to small-model output pricing on the reasoned tokens.
    cur_frac = rb[1]["n"] / n_total if n_total else 0.0
    if cur_frac > REASONING_CAP_FRAC and rb[1]["n"]:
        excess_frac = (cur_frac - REASONING_CAP_FRAC) / cur_frac  # share of reasoning reqs demoted
        wh_saved = rb[1]["wh"] * excess_frac * (1 - 1 / sustainability.REASONING_ENERGY_MULTIPLIER)
        cost_saved = rb[1]["cost"] * excess_frac * 0.5  # rough: half the reasoned spend avoided
    else:
        excess_frac = wh_saved = cost_saved = 0.0
    reasoning["cap_target_pct"] = REASONING_CAP_FRAC * 100
    reasoning["cap_wh_saved_per_day"] = round(wh_saved, 1)
    reasoning["cap_cost_saved_per_day"] = round(cost_saved, 4)
    reasoning["cap_wh_saved_per_month"] = round(wh_saved * 30, 0)

    if verbose:
        print("== M2 Inference Cost Levers ==")
        print(f"requests={len(rows)}  tokens={total_tokens:,}")
        print(f"baseline  : ${base_cost:,.2f}/day   ${base_pm:.3f}/1M-token")
        print(f"optimized : ${opt_cost:,.2f}/day   ${opt_pm:.3f}/1M-token")
        print(f"savings   : {savings_pct:.1f}%  (cascade + caching + batch)")
        print(f"discount stack (batch + 100% cache): {pricing.discount_stack(batch=True, cache_hit_frac=1.0):.3f} of naive")
        print()
        print("-- Extension 4: Reasoning Budget --")
        print(f"reasoning traffic : {reasoning['traffic_pct']:.1f}% of requests, "
              f"{reasoning['token_pct']:.1f}% of tokens")
        print(f"reasoning share   : {reasoning['cost_pct']:.1f}% of $ , {reasoning['wh_pct']:.1f}% of Wh")
        print(f"energy per request: reasoning {reasoning['wh_per_req_reasoning']:.2f} Wh  vs  "
              f"normal {reasoning['wh_per_req_normal']:.3f} Wh  "
              f"(~{reasoning['wh_per_req_reasoning'] / max(reasoning['wh_per_req_normal'], 1e-9):.0f}x)")
        print(f"cap to {reasoning['cap_target_pct']:.0f}% -> save ~${reasoning['cap_cost_saved_per_day']:.3f}/day "
              f"and ~{reasoning['cap_wh_saved_per_day']:.0f} Wh/day "
              f"(~{reasoning['cap_wh_saved_per_month']/1000:.1f} kWh/month)")
        print("routing rule: only take the reasoning path when a task-complexity score "
              "clears a threshold OR the fast-path answer's self-confidence is low.")

    return {
        "baseline_daily": round(base_cost, 2), "optimized_daily": round(opt_cost, 2),
        "baseline_per_m": round(base_pm, 3), "optimized_per_m": round(opt_pm, 3),
        "savings_pct": round(savings_pct, 1), "total_tokens": total_tokens,
        "reasoning": reasoning,
    }


if __name__ == "__main__":
    run()
