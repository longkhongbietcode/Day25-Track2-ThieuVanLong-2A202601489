# NimbusAI - GPU Cost Optimization Report

**Period:** monthly  
**Baseline spend:** $27,133  
**Optimized spend:** $14,626  
**Projected savings:** $12,507  (**46%**)

## Savings by lever

| Lever | Savings (USD) |
|---|---|
| Inference (cascade/cache/batch) | $1,212 |
| Purchasing (spot/reserved) | $10,040 |
| Right-size util-lies | $655 |
| Kill idle GPUs | $600 |

## Unit economics: $/1M-token (the metric that matters)

| | Baseline | Optimized | Reduction |
|---|---|---|---|
| Blended $/1M-token | $6.488 | $1.126 | 82.6% |

_Two teams can pay the same $/GPU-hr yet differ 5x on $/1M-token. Only the per-token unit exposes wasted capacity._

## Baseline vs optimized, per lever (each lever's own scope, USD / month)

_Inference + Purchasing scopes sum to the headline baseline; Right-size and Kill-idle act on a separate under-utilized GPU pool surfaced in M1._

| Lever | Baseline | Optimized | Saved |
|---|---|---|---|
| Inference (cascade/cache/batch) | $1,466 | $254 | $1,212 |
| Purchasing (spot/reserved) | $25,667 | $15,627 | $10,040 |
| Right-size util-lies | $2,520 | $1,865 | $655 |
| Kill idle GPUs | $600 | $0 | $600 |

## Why GPU-Util is a lie (and what it costs)

nvidia-smi GPU-Util only reports that a kernel was resident on an SM during the sampling window - it says nothing about how much of the chip's FLOPs or HBM bandwidth that kernel actually used. A GPU reads 90-98% util while stalling on HBM reads (memory-bound decode), waiting on kernel-launch / Python overhead between tiny ops, blocking on host<->device copies, or sitting in a non-overlapped all-reduce. Flagged here: `gpu-h100-4` (H100, MFU 0.19 at util 98%), `gpu-a10g-1` (A10G, MFU 0.27 at util 97%). Financially: the GPU-hour is billed in full while ~1/5 of the rented FLOPs are delivered, so the true $/1M-token on that box is roughly 5x the sticker rate. Fix = right-size one tier down (H100->A100) or raise MFU (fuse kernels, bigger batch, CUDA graphs), not buy more H100s.

## Recommended actions (highest ROI first)

1. **Purchasing (spot/reserved)** - save ~$10,040/mo (37.0% of baseline): spot for interruptible training + 3yr reserved for always-on inference above the 55% break-even duty cycle
2. **Inference (cascade/cache/batch)** - save ~$1,212/mo (4.5% of baseline): route easy prompts to the small model (~15x cheaper), bill cached input at 0.1x, send non-real-time traffic through the Batch API
3. **Right-size util-lies** - save ~$655/mo (2.4% of baseline): drop the util-lie GPUs one tier - same throughput, lower rate
4. **Kill idle GPUs** - save ~$600/mo (2.2% of baseline): auto-stop instances left running after the job finishes

## Sustainability <-> cost linkage

Region choice moves carbon and the power bill together. `europe-north1` (30 gCO2/kWh, $0.09/kWh) vs `europe-central2` (660 gCO2/kWh, $0.18/kWh): shifting interruptible jobs there cuts ~95% of their CO2e and ~50% of their electricity cost at once. `us-east-wa` is the cheapest power ($0.055/kWh); `us-west-2` (120 gCO2/kWh, $0.07/kWh) is the balanced pick when latency to US users matters. See missions/ext_carbon_scheduling.py for the per-job numbers.

Reasoning traffic is 8.4% of requests but 16.5% of inference $ and 94.0% of energy - each reasoning request burns ~173x the Wh of a normal one (long hidden chains -> many memory-bound decode steps, large KV-cache). Capping it to 3% of traffic saves ~$0.45/day and ~566.4 kWh/month. See missions/m2_inference_levers.py (Extension 4).

## Sustainability

- Energy per query: 0.24 Wh
- Carbon per query: 0.091 gCO2e
- Cheapest+cleanest region: europe-north1

_Figures are June-2026 as-of snapshots; re-baseline before acting._