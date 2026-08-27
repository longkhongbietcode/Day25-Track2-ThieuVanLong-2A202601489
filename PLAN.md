# PLAN — Hoàn thành Lab 25 (GPU FinOps Optimization) đúng 100% Rubric

> Mục tiêu: đạt tối đa **100/100** theo `Rubric.md`.
> Ràng buộc gốc (không được vi phạm — xem §0).
> Trạng thái khởi điểm (đã kiểm tra ngày lập plan): `verify.py` 11/11 ✅ · `pytest` 15/15 ✅ · `report.md` sơ sài + lỗi encoding · `savings.png` chưa có · 0 extension · chưa có write-up.

---

## §0. Ràng buộc bắt buộc tuân thủ (trích từ Rubric.md)

| # | Ràng buộc | Nguồn (Rubric) | Cách plan này tuân thủ |
|---|---|---|---|
| R1 | **KHÔNG sửa bất kỳ file nào trong `tests/`.** Nếu test bị sửa để hardcode → **mất toàn bộ 20đ phần B.** | §B, ghi chú | Mọi bước dưới đây chỉ đọc `tests/`, không ghi. Sau mỗi thay đổi code chạy lại `pytest -q` để chứng minh 15/15 vẫn xanh với test gốc. |
| R2 | **KHÔNG hardcode kết quả** trong engine `finops/` để "lách" check. Check pass nhưng bản chất sai → phần C bị trừ. | §A ghi chú, "Dấu hiệu cần điều tra" | Mọi sửa đổi engine phải là công thức FinOps đúng bản chất, có giải thích trong report. Không gán số cố định. |
| R3 | **Savings tổng không được > 95%** (dấu hiệu hardcode). Các band bắt buộc: M2 ∈ [60,95]%, M5 tổng ∈ [40,95]%, M4 coverage ∈ [85,100]%. | §A bảng checks, "Dấu hiệu cần điều tra" | Không đụng tới logic tính savings lõi của M2/M3/M5. Extension chỉ *thêm* phân tích, không thay công thức tổng. Chạy `verify.py` sau mỗi bước. |
| R4 | **Số liệu trong `report.md` phải khớp output của missions** (không copy-paste sai, không chỉnh tay). | §C.3, "Dấu hiệu cần điều tra" | `report.md` do `m5_report.py` sinh tự động. Phần phân tích thêm vào phải lấy số **từ chính dict trả về của các `run()`**, không gõ tay. Có bước cross-check cuối. |
| R5 | `verify.py` phải chạy được, **không lỗi import** (lỗi import = 0đ phần A). | §A bảng điểm | Không đổi chữ ký hàm đang được `verify.py`/missions gọi. Extension mới đặt ở hàm/tham số *tùy chọn* hoặc file riêng. |
| R6 | Extension: chỉ tính điểm khi **code chạy được + có số đo cụ thể + so sánh trước/sau + giải thích insight**. Làm ≥3 vẫn tối đa 20đ. | §D bảng điểm | Làm đúng **2 extension** cho chắc (mục tiêu 20/20), có phương án extension thứ 3 dự phòng. Mỗi extension có output số + đoạn giải thích. |
| R7 | `flag_util_lies()` phải nhận `gpu_util_pct` thang 0–100, so sánh nội bộ chia 100; ngưỡng `util>=0.90 AND mfu<0.30`. | Guide §12, `test_metrics` | Không sửa `flag_util_lies` (đang đúng). |
| R8 | `recommend_tier` phải giữ 3 hành vi test khoá: `(2,True)->spot`, `(24,False)->reserved`, `(4,False)->on_demand`. | `tests/test_pricing.py::test_recommend_tier` | Nếu làm Extension 1, **chỉ thêm tham số keyword có default**, giữ nguyên 3 nhánh cơ bản. Verify bằng `pytest`. |
| R9 | `savings.png` phải là **waterfall/bar hiển thị đúng 4 lever**. | §C.3 | Không đổi danh sách 4 lever trong `m5_report.py` (`Inference`, `Purchasing`, `Right-size util-lies`, `Kill idle GPUs`). Chỉ cài `matplotlib` để hàm `savings_waterfall()` chạy. |
| R10 | Không được để `verify.py` M3 mất tier `spot` hoặc `reserved` (mỗi cái là 1 check). | `verify.py` L42–44 | Sau Extension 1, assert lại `{t for r in recs}` vẫn chứa cả `spot` và `reserved`. |

---

## §1. Phân rã điểm & việc cần làm

| Phần | Điểm | Hiện có | Việc cần làm |
|---|---|---|---|
| A — `verify.py` 11/11 | 30 | 30 ✅ | Giữ nguyên: chạy lại sau mỗi thay đổi. |
| B — `pytest` 15/15 | 20 | 20 ✅ | Giữ nguyên: chạy lại sau mỗi thay đổi; không chạm `tests/`. |
| C — `outputs/report.md` + `savings.png` | 30 | ~10 | Bước 2 → 5. |
| D — ≥2 Extensions | 20 | 0 | Bước 6 (Ext A) + Bước 7 (Ext B). |
| Write-up ngắn (điều kiện nộp) | — | 0 | Bước 8. |

Chi tiết mục C (30đ) theo Rubric §C:

- **C.1 Nội dung bắt buộc (15đ):**
  - (5) baseline spend + optimized spend + % tiết kiệm tổng — *đã có trong report auto-gen.*
  - (5) **bảng từng lever kèm số tiền tiết kiệm cụ thể** — *đã có bảng 4 lever.*
  - (5) Sustainability: năng lượng/query + carbon/query + **vùng tốt nhất đúng = `europe-north1`** — *đã có, cần xác nhận đúng.*
- **C.2 Phân tích chất lượng (10đ):**
  - (3) **Giải thích cơ chế** vì sao GPU-Util là "lie" (không chỉ nói MFU thấp — phải nêu memory stall / kernel-launch overhead / chờ I/O / non-overlapped comm) và ý nghĩa tài chính.
  - (4) **Đề xuất hành động có thứ tự ưu tiên theo ROI.**
  - (3) Nhận xét bền vững **liên kết carbon với chi phí điện cụ thể**.
- **C.3 Hình thức (5đ):**
  - (2) `savings.png` có mặt, đọc được, đúng 4 lever.
  - (3) Số liệu report ↔ output missions nhất quán.

→ Report auto-gen hiện chỉ đạt phần C.1. **Toàn bộ C.2 (10đ) và C.3 hình ảnh (2đ) đang thiếu.** Đó là trọng tâm Bước 3–5.

---

## §2. Các bước thực hiện (theo thứ tự)

### Bước 1 — Chuẩn bị môi trường
- `python -m venv .venv` → activate (`.venv\Scripts\activate` trên Windows).
- `pip install -r requirements.txt` — mục đích chính: có `matplotlib` để sinh `savings.png` (R9). `pandas` không được import trong path graded nhưng vẫn cài cho đúng `requirements.txt`.
- **Chấp nhận (Definition of Done):** `python -c "import matplotlib"` không lỗi.

### Bước 2 — Sửa lỗi encoding khi ghi `report.md` (chính đáng, không phạm R1/R2)
- File: `missions/m5_report.py`, dòng `with open(out_md, "w") as f:` → `with open(out_md, "w", encoding="utf-8") as f:`.
- Lý do: trên Windows dấu `—` trong tiêu đề bị ghi thành ký tự hỏng (`NimbusAI �`). Đây là bug I/O, không phải logic FinOps → không vi phạm R2.
- (Tùy chọn) đổi `—` thành `-` trong `finops/report.py` để an toàn tuyệt đối. Không bắt buộc.
- **Chấp nhận:** `outputs/report.md` mở ra hiển thị `# NimbusAI — GPU Cost Optimization Report` đúng.

### Bước 3 — Mở rộng engine báo cáo `finops/report.py::build_report` (đúng bản chất, R2)
Thêm **tham số tùy chọn** (giữ chữ ký cũ hoạt động — R5) để report chứa nội dung C.2:

- Thêm `per_lever_detail: dict | None` → render bảng **baseline → optimized theo `$/1M-token`** cho lever Inference (số lấy từ `r2` của M2: `baseline_per_m`, `optimized_per_m`) và **$/tháng before/after** cho từng lever.
- Thêm `narrative: dict | None` với các khoá:
  - `util_lie_mechanism` — đoạn văn giải thích cơ chế (memory-bound stalls, kernel launch overhead, chờ dữ liệu, communication không overlap) + tác động: *trả đủ giá GPU-giờ nhưng chỉ nhận ~1/5 FLOPs → `$/1M-token` thực tế cao gấp ~5×*.
  - `priority_actions` — list hành động sắp theo ROI giảm dần, mỗi mục kèm `$ tiết kiệm/tháng` và lý do.
  - `sustainability_note` — liên kết: `europe-north1` 30 gCO2/kWh & \$0.09/kWh **vs** `europe-central2` 660 gCO2/kWh & \$0.18/kWh → chuyển vùng cắt đồng thời ~95% carbon và ~50% tiền điện; `us-west-2` là lựa chọn cân bằng (120 g, \$0.07).
- **Toàn bộ số** truyền vào từ dict trả về của `m1/m2/m3/m5.run()` — **không gõ tay** (R4).
- **Chấp nhận:** `build_report()` cũ (không truyền tham số mới) vẫn trả về đúng chuỗi cũ → `tests/test_report.py::test_build_report` vẫn pass (R1).

### Bước 4 — Bơm dữ liệu phân tích vào `missions/m5_report.py`
- Tính sẵn 3 khối narrative từ kết quả `r1/r2/r3`:
  - `priority_actions` xếp hạng bằng cách **sort `levers.items()` theo giá trị giảm dần** (hiện dữ liệu: Purchasing \$10,040 > Inference \$1,212 > Right-size \$655 > Kill idle \$600) — sinh động, không hardcode thứ tự.
  - `per_lever_detail["inference_per_m"]` = `(r2["baseline_per_m"], r2["optimized_per_m"])`.
  - GPU bị "lie" và loại GPU lấy từ `r1["lies"]`.
- Gọi `report.build_report(..., per_lever_detail=..., narrative=...)`.
- Giữ nguyên `levers` 4 khoá và công thức `baseline/optimized/total_pct` (R3, R9).
- **Chấp nhận:** `python missions/m5_report.py` in ra report mới; `verify.py` vẫn 11/11; `r5["total_savings_pct"]` vẫn trong [40,95].

### Bước 5 — Sinh `savings.png` và cross-check số liệu
- Chạy `python missions/run_all.py` rồi `python missions/m5_report.py`.
- Xác nhận `outputs/savings.png` tồn tại, mở được, có **đúng 4 cột lever** (R9, C.3-2đ).
- **Cross-check (R4, C.3-3đ):** lập bảng đối chiếu trong write-up:
  | Số liệu | Nguồn mission (terminal) | Trong report.md |
  |---|---|---|
  | baseline monthly | `m5.run()` → `baseline_monthly` | dòng "Baseline spend" |
  | optimized monthly | `m5.run()` → `optimized_monthly` | dòng "Optimized spend" |
  | % tổng | `m5.run()` → `total_savings_pct` | ngoặc `(**x%**)` |
  | 4 lever $ | `m5.run()` → `levers` | bảng "Savings by lever" |
  | $/1M-token before/after | `m2.run()` → `baseline_per_m/optimized_per_m` | bảng inference detail |
  | best region | `min(REGION_CARBON)` = `europe-north1` | dòng "Cheapest+cleanest region" |
- **Chấp nhận:** mọi ô khớp tuyệt đối; `savings.png` hiển thị 4 lever.

### Bước 6 — Extension A: **Reasoning Budget** (Rubric §D.4, mục tiêu 9–10/10)
- **File sửa:** `missions/m2_inference_levers.py` (thêm khối tính, giữ `run()` trả thêm khoá mới — không xoá khoá cũ, R5) **và** `missions/m5_report.py` (thêm 1 mục trong report). Không sửa test.
- **Dữ liệu:** `token_usage.csv` có cột `is_reasoning` — 201/2400 request (**8.4% traffic**).
- **Tính toán (số cụ thể — R6):**
  1. Chi phí `$` của nhóm `is_reasoning=1` vs `is_reasoning=0` (dùng `pricing.request_cost` như M2).
  2. Năng lượng `Wh`: `sustainability.wh_per_query(tokens, is_reasoning=True)` (hệ số `REASONING_ENERGY_MULTIPLIER=80`) vs `is_reasoning=False`.
  3. In: *reasoning chiếm X% traffic nhưng Y% chi phí $ và Z% tổng Wh*.
  4. **So sánh trước/sau:** ước tính nếu cap reasoning từ 8.4% → 3% traffic (route theo độ phức tạp), tiết kiệm bao nhiêu `$` và `Wh`.
- **Insight (R6):** giải thích vì sao reasoning tốn ~80× năng lượng (sinh nhiều token ẩn/chain-of-thought, nhiều lượt decode memory-bound, KV-cache lớn) và đề xuất **routing rule**: chỉ bật reasoning khi `task_complexity_score > ngưỡng` hoặc khi câu trả lời fast-path có confidence thấp.
- **Chấp nhận:** `python missions/m2_inference_levers.py` in bảng reasoning; con số Y%, Z%, và \$/Wh tiết kiệm hiển thị rõ; `verify.py` 11/11; `pytest` 15/15.

### Bước 7 — Extension B: **Carbon-aware Scheduling** (Rubric §D.5, mục tiêu 9–10/10)
- **File mới:** `missions/ext_carbon_scheduling.py` (không đụng mission lõi → an toàn R3/R5). Thêm import vào `missions/run_all.py` (tùy chọn).
- **Dữ liệu:** `workloads.csv` có 5 job `interruptible=1`: `job-train-llm`, `job-train-embed`, `job-finetune`, `job-dev-sandbox`, `job-batch-eval`.
- **Tính toán (số cụ thể — R6):**
  1. Với mỗi job interruptible: ước lượng năng lượng `kWh` = `num_gpus × watts(gpu_type) × hours_per_day × days / 1000` (watts lấy từ `price_catalog.csv`).
  2. Carbon tại `us-east-1` (380 g/kWh) vs `europe-north1` (30 g/kWh) — dùng `sustainability.carbon_g`.
  3. Chi phí điện tại mỗi vùng — dùng `sustainability.energy_cost_usd`.
  4. **Bảng so sánh cả 5 vùng** (`REGION_CARBON` ∩ `REGION_PRICE_KWH`): cột `$/kWh`, `gCO2/kWh`, chi phí điện thực tế ($), carbon thực tế (kg CO2e).
  5. Tổng **gCO2e tiết kiệm** và **% giảm** nếu chuyển toàn bộ job interruptible sang vùng sạch nhất.
- **Insight (R6):** đề xuất vùng tối ưu theo từng tiêu chí (rẻ nhất `$` = `us-east-wa` \$0.055; sạch nhất = `europe-north1` 30 g; cân bằng = `us-west-2`); nhận xét trade-off **latency** (vùng sạch nhất ở Na Uy → xa user Mỹ/Á, chỉ hợp job batch/training không nhạy latency — đúng là các job `interruptible`).
- **Chấp nhận:** `python missions/ext_carbon_scheduling.py` in bảng 5 vùng + tổng kg CO2e tiết kiệm + %; `verify.py` 11/11; `pytest` 15/15.

### Bước 7b (DỰ PHÒNG) — Extension C: cải thiện `recommend_tier()` (Rubric §D.1)
Chỉ làm nếu còn thời gian / muốn chắc chắn 20đ. **Ràng buộc R8:**
- Giữ nguyên chữ ký gọi cũ; thêm `gpu_type: str | None = None`, `job_days: int | None = None`, `reserved_1yr_discount: float = 0.30`.
- Giữ 3 nhánh khoá: `(2,True)->spot`, `(24,False)->reserved`, `(4,False)->on_demand` phải vẫn đúng.
- Thêm: interruption-rate theo GPU (`H100/H200` spot an toàn hơn → ưu tiên spot; `A10G/L4` bị thu hồi nhiều hơn → cân nhắc on-demand); so sánh 1yr vs 3yr theo `job_days`.
- Chạy lại M3, in `savings_pct` **trước vs sau**; assert `{tier}` vẫn ⊇ `{spot, reserved}` (R10).
- Có thể thêm test **mới** ở file **mới** `tests/test_ext_recommend_tier.py`? → **KHÔNG**: R1 cấm đụng thư mục tests khi có rủi ro hiểu nhầm. Thay vào đó viết assertion trong chính file extension.

### Bước 8 — Write-up ngắn `outputs/writeup.md` (1–2 trang, điều kiện nộp — Guide §11)
Trả lời đủ 5 câu:
1. **Baseline vs Optimized:** \$ trước/sau, `$/1M-token` trước/sau, % tổng.
2. **Phân tích từng lever:** lever nào đóng góp nhiều nhất (Purchasing) và **tại sao** (spot cho job interruptible + reserved cho inference 24/7 duty ≥ 55%).
3. **GPU-Util Lie:** GPU nào (`gpu-h100-4`, và `gpu-a10g-1`), MFU ~0.20, **cơ chế** + tác động tài chính (idle waste \$/tháng + FLOPs mất).
4. **Extensions đã làm:** mô tả Ext A + Ext B, **bảng số đo trước/sau**, insight quan trọng nhất mỗi cái.
5. **3 khuyến nghị đầu tiên cho NimbusAI** theo thứ tự ROI.
+ Kèm **bảng cross-check số liệu** ở Bước 5.

### Bước 9 — Kiểm tra toàn bộ & nghiệm thu cuối
Chạy tuần tự và dán log vào write-up:
```
python data/generate.py
python missions/run_all.py
python missions/m2_inference_levers.py      # xem bảng reasoning
python missions/ext_carbon_scheduling.py    # xem bảng 5 vùng
python verify.py            # PHẢI: 11/11
pytest -q                   # PHẢI: 15 passed
```
Checklist nộp (Guide §11):
```
[ ] python verify.py  -> 11/11 checks passed
[ ] pytest -q         -> 15 passed
[ ] outputs/report.md  — có baseline/optimized/%, bảng 4 lever, $/1M-token before/after,
                          giải thích cơ chế util-lie, hành động ưu tiên theo ROI, sustainability
[ ] outputs/savings.png — waterfall 4 lever, đọc được
[ ] outputs/focus_export.csv — tồn tại (50 dòng)
[ ] outputs/writeup.md — 5 câu trả lời + bảng đo extension + cross-check
[ ] >=2 extension chạy được, có số đo trước/sau
[ ] git: không có thay đổi nào trong tests/
```

### Bước 10 — Commit
- `git add` tất cả trừ `.venv/` (đã trong `.gitignore`?), commit message mô tả: enrich report + 2 extensions + writeup.
- **Xác nhận `git status` không liệt kê file nào trong `tests/`** (R1).

---

## §3. Ma trận truy vết Rubric → Bước

| Tiêu chí Rubric | Điểm | Bước đáp ứng |
|---|---|---|
| A. verify 11/11 | 30 | B1, và re-check ở B2/B4/B6/B7/B9 |
| B. pytest 15/15 | 20 | Giữ test gốc; re-check ở B3/B4/B6/B7/B9 |
| C.1 baseline/optimized/% | 5 | B4 (đã có) + B5 cross-check |
| C.1 bảng lever + số tiền | 5 | B3/B4 (bảng 4 lever + chi tiết $/1M-token) |
| C.1 Sustainability (Wh, carbon, vùng đúng) | 5 | B4 (xác nhận `europe-north1`) |
| C.2 cơ chế GPU-Util lie | 3 | B3 `narrative.util_lie_mechanism` + B8 câu 3 |
| C.2 hành động ưu tiên ROI | 4 | B4 `priority_actions` (sort theo $) + B8 câu 5 |
| C.2 bền vững ↔ chi phí điện | 3 | B3 `sustainability_note` + B7 bảng 5 vùng + B8 |
| C.3 savings.png 4 lever | 2 | B1 (matplotlib) + B5 |
| C.3 số liệu nhất quán | 3 | B4 (số từ dict, không gõ tay) + B5 bảng cross-check |
| D Extension 1 | ≤10 | B6 (Reasoning Budget) |
| D Extension 2 | ≤10 | B7 (Carbon-aware Scheduling) |
| D dự phòng | — | B7b (recommend_tier) |
| Điều kiện nộp (write-up) | — | B8 |

---

## §4. Rủi ro & cách chặn

| Rủi ro | Hậu quả | Phòng ngừa |
|---|---|---|
| Sửa engine làm lệch band savings | Rớt check verify → mất phần A | Không đụng công thức tổng của M2/M3/M5; chạy `verify.py` sau *mỗi* bước |
| Vô tình chỉnh file trong `tests/` | Mất trọn 20đ phần B | Chỉ đọc `tests/`; `git status` kiểm ở B10 |
| Số report ≠ terminal | Trừ C.3 (3đ) + nghi copy-paste | Số truyền từ dict `run()`; bảng cross-check B5 |
| `matplotlib` không cài được | Mất C.3 (2đ) | Thử `pip install matplotlib`; nếu vẫn fail, ghi rõ trong writeup + đính kèm dữ liệu waterfall dạng bảng |
| Extension chỉ có comment, không có số | Rớt về 0–2đ/extension | Mỗi extension bắt buộc in ra bảng số + đoạn insight; nghiệm thu ở B6/B7 |
| `recommend_tier` mới làm mất tier spot/reserved trong M3 | Mất 2 check verify | B7b assert `{tiers} ⊇ {spot, reserved}` + `pytest` |
| Savings vọt > 95% | Nghi hardcode → trừ C | Không nhân chồng thêm discount vào tổng; extension tách riêng, không cộng vào `levers` |

---

## §5. Thứ tự thực thi gọn

```
B1 cài môi trường
B2 fix encoding  -> verify + pytest
B3 mở rộng finops/report.py (tham số tùy chọn)  -> pytest (test_report vẫn xanh)
B4 bơm narrative vào m5_report.py  -> verify 11/11
B5 run_all + m5 -> sinh savings.png + cross-check
B6 Extension A: Reasoning Budget  -> verify + pytest
B7 Extension B: Carbon-aware Scheduling  -> verify + pytest
(B7b tùy chọn Extension C)
B8 viết outputs/writeup.md
B9 nghiệm thu toàn bộ theo checklist
B10 commit (kiểm tra không đụng tests/)
```
