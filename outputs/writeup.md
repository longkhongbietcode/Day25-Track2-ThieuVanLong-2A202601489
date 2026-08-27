# NimbusAI — GPU FinOps: Bài viết ngắn (Lab 25)

**Tác giả:** Thiều Văn Long · **Ngày:** 2026-08-27
**Kèm theo:** `outputs/report.md`, `outputs/savings.png`, `outputs/focus_export.csv`

> Toàn bộ số liệu dưới đây lấy trực tiếp từ output của `missions/` (seed=25). Bảng đối chiếu ở §6.

---

## 1. Baseline vs. Optimized

| Chỉ số | Baseline | Optimized | Thay đổi |
|---|---|---|---|
| Chi tiêu GPU / tháng | **$27,133** | **$14,626** | **−$12,507 (−46%)** |
| `$/1M-token` (inference, blended) | **$6.488** | **$1.126** | **−82.6%** |
| Inference $/ngày (M2) | $48.87 | $8.48 | −82.6% |
| Purchasing $/tháng (M3) | $25,667 | $15,627 | −39.1% |

**Điểm cốt lõi:** đo bằng `$/GPU-giờ` chỉ cho biết *trả bao nhiêu để thuê*; đo bằng `$/1M-token`
buộc tính cả *hiệu quả sử dụng*. Ở NimbusAI hai đơn vị này cho kết luận trái ngược trên
`gpu-h100-4`: giá thuê H100 "bình thường" nhưng `$/1M-token` thực tế cao gấp ~5× vì MFU chỉ 0.19.

---

## 2. Phân tích từng đòn bẩy

| Đòn bẩy | Tiết kiệm/tháng | % baseline | Vì sao |
|---|---|---|---|
| **Purchasing (spot/reserved)** | **$10,040** | 37.0% | Đòn bẩy lớn nhất. 5 job `interruptible` → **spot** + checkpoint (H100 spot ~$1.5 vs on-demand $2.5, interrupt rate <5%). 3 job inference chạy 24/24 → duty cycle 100% ≥ điểm hòa vốn 55% → **reserved 3yr** ($1.4/h). |
| **Inference (cascade/cache/batch)** | $1,212 | 4.5% | Cascade: route request "small" sang model rẻ ~15×. Cache: input đã cache tính 0.1×. Batch: −50% cho traffic không real-time. 3 chiết khấu **nhân nhau** → batch + 100% cache = 0.05 của giá gốc. |
| **Right-size util-lies** | $655 | 2.4% | Hạ `gpu-h100-4` H100→A100 và `gpu-a10g-1` A10G→L4. Cùng throughput thực tế (MFU/MBU vốn đã thấp) nhưng rate thấp hơn. |
| **Kill idle GPUs** | $600 | 2.2% | `gpu-h100-5` để chạy không 8h/ngày sau khi job xong → auto-stop. |
| **Tổng** | **$12,507** | **46.1%** | Nằm trong band 40–95% theo verify. |

**Đòn bẩy đóng góp nhiều nhất = Purchasing**, vì nó tác động lên phần chi lớn nhất (thuê GPU
cho training/inference), trong khi cascade/cache/batch chỉ tác động lên hóa đơn inference API
vốn nhỏ hơn nhiều so với hóa đơn thuê hạ tầng.

---

## 3. GPU-Util Lie

**GPU bị "lie" (util ≥ 90% nhưng MFU < 30%):**

| GPU | Loại | GPU-Util | MFU | MBU |
|---|---|---|---|---|
| `gpu-h100-4` | H100 | 98.2% | **0.194** | 0.207 |
| `gpu-a10g-1` | A10G | 96.9% | **0.268** | 0.302 |

**Cơ chế — vì sao "bận 98%" mà chỉ dùng 1/5 FLOPs:**
`nvidia-smi` "GPU-Util %" chỉ đo *có kernel nào đang chiếm SM trong cửa sổ lấy mẫu hay không* —
nó **không** đo phần FLOPs/băng thông HBM thực sự được dùng. GPU vẫn hiện 98% khi nó đang:

- **Stall chờ đọc HBM** (decode LLM là memory-bound, arithmetic intensity ~1–2 FLOP/byte, xa dưới ridge point ~295 của H100);
- **Chờ kernel-launch / overhead Python** giữa hàng loạt op nhỏ chưa được fuse;
- **Nghẽn copy host↔device** (data loader chậm, không prefetch);
- **Ngồi trong all-reduce không overlap** với compute.

**Tác động tài chính:** GPU-giờ vẫn bị tính **đủ giá**, nhưng chỉ ~20% FLOPs thuê được giao ra
→ `$/1M-token` thực trên máy đó **gấp ~5×** giá niêm yết. Với `gpu-h100-4` (on-demand $2.5/h),
đó là ~$2/h "bốc hơi". **Hành động đúng:** right-size xuống 1 bậc (H100→A100) *hoặc* nâng MFU
(fuse kernel, tăng batch, CUDA graphs) — **không** phải mua thêm H100.

---

## 4. Phần mở rộng đã làm

### Extension 4 — Reasoning Budget (`missions/m2_inference_levers.py`, Rubric §D.4)

| Nhóm | % request | % token | % chi phí $ | % năng lượng Wh | Wh / request |
|---|---|---|---|---|---|
| `is_reasoning = 1` | **8.4%** | 16.5% | 16.5% | **94.0%** | **148.2** |
| `is_reasoning = 0` | 91.6% | 83.5% | 83.5% | 6.0% | 0.858 |

**Số đo:** reasoning chỉ chiếm 8.4% traffic nhưng nuốt **94% tổng Wh**. Mỗi request reasoning
tốn **~173×** năng lượng của request thường — do **2 yếu tố nhân nhau**:
(a) hệ số năng lượng/token của chế độ reasoning ~80× (chain-of-thought ẩn → nhiều bước decode
memory-bound, KV-cache lớn), và (b) request reasoning sinh trung bình ~6× nhiều output token hơn
(3,875 vs 641).

**So sánh trước/sau — cap reasoning 8.4% → 3% traffic** (route theo độ phức tạp task /
confidence của fast-path): tiết kiệm **~$0.45/ngày** và **~566 kWh/tháng** (~$50–100 tiền điện
tùy vùng, và ~215 kg CO2e/tháng ở us-east-1).

**Insight:** đây là "quả bom năng lượng" bị che khuất trong hóa đơn $ (chỉ 16.5%) — chỉ lộ ra
khi nhìn trục Wh. Routing rule đề xuất: **chỉ bật reasoning khi `task_complexity_score > ngưỡng`
HOẶC câu trả lời fast-path có self-confidence thấp.**

### Extension 5 — Carbon-aware Scheduling (`missions/ext_carbon_scheduling.py`, Rubric §D.5)

5 job `interruptible=1` → **2,057 kWh/tháng** (đã tính PUE 1.15).

| Vùng | $/kWh | gCO2/kWh | Tiền điện $/tháng | CO2e kg/tháng |
|---|---|---|---|---|
| europe-north1 (Na Uy, thủy điện) | 0.090 | 30 | 185.16 | **61.7** |
| us-east-wa | 0.055 | 90 | 113.15 | 185.2 |
| us-west-2 (Oregon hydro) | 0.070 | 120 | 144.01 | 246.9 |
| us-east-1 (baseline) | 0.120 | 380 | 246.88 | 781.8 |
| europe-central2 (Ba Lan, than) | 0.180 | 660 | 370.32 | 1,357.9 |

**Số đo — chuyển toàn bộ fleet interruptible `us-east-1 → europe-north1`:**
**−720 kg CO2e/tháng (−92.1%)** đồng thời **−$61.72/tháng tiền điện**.

**Insight & trade-off:**
- "Tối ưu" phụ thuộc tiêu chí: **sạch nhất** = europe-north1 (30 g); **rẻ điện nhất** =
  us-east-wa ($0.055); **cân bằng** = us-west-2 (gần user Mỹ, vẫn 120 g & $0.07).
- europe-north1 xa user Mỹ/Á → **latency cao**, nhưng đây đúng là các job batch/training
  gián đoạn được, **không nhạy latency** → không có trade-off thực tế. Không nên chuyển các
  job *serving* 24/7 (`job-infer-*`) sang đó.
- Carbon và tiền đi **cùng chiều** ở đây: vùng bẩn nhất (europe-central2) cũng là vùng đắt điện nhất.

---

## 5. Khuyến nghị cho NimbusAI — 3 hành động đầu tiên (theo ROI)

1. **Chuyển purchasing sang spot + reserved (ưu tiên #1, ~$10,000/tháng).** Bật spot +
   checkpoint cho toàn bộ job training/eval gián đoạn được; ký reserved 3yr cho 3 cụm inference
   chạy 24/24. Đây là 80% giá trị tiết kiệm với rủi ro thấp nhất.
2. **Dọn 2 nguồn lãng phí lộ liễu (~$1,255/tháng, làm trong tuần đầu).** Right-size
   `gpu-h100-4`→A100 và `gpu-a10g-1`→L4; bật auto-stop cho GPU idle như `gpu-h100-5`. Đồng
   thời gắn cảnh báo khi MFU < 0.30 kéo dài để không tái diễn.
3. **Đặt "ngân sách" cho inference & reasoning (~$1,200/tháng + 566 kWh/tháng).** Ép cascade
   theo `route_tier`, bật prompt caching + Batch API cho traffic offline; thêm cổng routing
   giới hạn reasoning ≤ 3% traffic. Song song, lên lịch job interruptible ở us-west-2/europe-north1
   để cắt ~720 kg CO2e/tháng.

---

## 6. Đối chiếu số liệu (report.md ↔ output missions)

| Số liệu | Nguồn (mission `run()`) | Giá trị | Trong `report.md` |
|---|---|---|---|
| Baseline monthly | `m5_report` → `baseline_monthly` | $27,133 | "Baseline spend: $27,133" ✅ |
| Optimized monthly | `m5_report` → `optimized_monthly` | $14,626 | "Optimized spend: $14,626" ✅ |
| Savings % tổng | `m5_report` → `total_savings_pct` | 46.1% | "(**46%**)" ✅ |
| Lever: Purchasing | `m5_report` → `levers` | $10,040 | bảng "Savings by lever" ✅ |
| Lever: Inference | `m5_report` → `levers` | $1,212 | bảng ✅ |
| Lever: Right-size | `m5_report` → `levers` | $655 | bảng ✅ |
| Lever: Kill idle | `m5_report` → `levers` | $600 | bảng ✅ |
| `$/1M-token` before/after | `m2_inference_levers` → `baseline_per_m` / `optimized_per_m` | 6.488 / 1.126 | bảng "Unit economics" ✅ |
| Best region | `min(sustainability.REGION_CARBON)` | europe-north1 | "Cheapest+cleanest region" ✅ |
| Reasoning % Wh | `m2` → `reasoning.wh_pct` | 94.0% | "Sustainability ↔ cost linkage" ✅ |
| Carbon saved (Ext5) | `ext_carbon_scheduling` → `co2e_saved_kg_month` | 720.1 kg | writeup §4 ✅ |

---

## 7. Kết quả kiểm tra tự động

```
python verify.py   ->  11/11 checks passed
pytest -q          ->  15 passed
```

Không sửa file nào trong `tests/`. Các sửa đổi engine (`finops/report.py`) chỉ **thêm tham số
tùy chọn** — chữ ký cũ giữ nguyên, `test_report.py` vẫn xanh với bản gốc.

**Câu hỏi Oral-check (Rubric phụ lục) — trả lời nhanh:**

1. *GPU-Util 98% có hiệu quả không?* Không. Nó chỉ đo clock bận, không đo FLOPs. Xem §3.
2. *Vì sao cần ≥80% tag coverage mới chargeback?* Dưới ngưỡng đó, phần chi chưa gắn tag bị
   phân bổ sai → tính tiền team dựa trên dữ liệu thiếu → mất niềm tin. NimbusAI hiện 92% → OK.
3. *70% workload interruptible thì tối ưu purchasing thế nào?* Mặc định spot + checkpoint cho
   toàn bộ nhóm đó; chỉ giữ on-demand làm "burst capacity" khi spot bị thu hồi hàng loạt;
   reserved chỉ cho phần 30% chạy ổn định 24/24.
4. *Khi nào `$/GPU-hr` và `$/1M-token` trái ngược?* Khi MFU thay đổi: cùng `$/GPU-hr` nhưng
   đội có MFU 0.4 phục vụ gấp đôi token so với đội MFU 0.2 → `$/1M-token` bằng nửa.
5. *Vì sao decode memory-bound, prefill compute-bound?* Prefill xử lý cả prompt song song →
   nhiều FLOP trên mỗi byte trọng số đọc về (~455 FLOP/byte). Decode sinh 1 token/bước, phải
   đọc lại toàn bộ trọng số + KV-cache cho mỗi token → ~1–2 FLOP/byte, nghẽn ở băng thông HBM.
