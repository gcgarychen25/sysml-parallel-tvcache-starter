# Experiment A — workload characterization

**Mode:** `none` (no TVCache) · **Models:** `Qwen/Qwen3.5-9B` (A0–A2) · `Qwen/Qwen3.8-27B` (A3/A3b/B1/T1–T2) · `Qwen/Qwen3.8-Flash-Next-FP8` (B2 skipped) · **Reproduce:** root `README.md`  
**Tasks:** DeepSWE setup variants under `variants/deep-swe-setup/` · **TMax** short+bash-only under `variants/tmax-easy/` (`configs/experiment-tasks-tmax-easy10.txt`).  
**How to extend:** add one row to **Cells** (+ optional one-line note under **Notes**). Published pack: `artifacts/expA-traces-A0-A2.zip` (unzip at repo root). Local full runs stay in gitignored `jobs/` / `results/`.

---

## Cells (summary)

| Cell | Prefix | Ctx / turns / tok | Think | TP×GPU | Scope | Sess | Rew>0 | Parallel-turn | Binding limit | Peak prompt | Notes |
| --- | --- | --- | --- | ---: | --- | ---: | ---: | --- | --- | --- | --- |
| **A0** | `char-setup-10t-k5` | 8K / 8 / 2K | off | 1×80GB | 10 tasks × n=5 | 50/50 | **0** | **0.00** (0/199) | **8K context** | ~8K | final `length`×38 `error`×12; TCG prefix overlap ~10% |
| **A1** | `char-setup-10t-ctx256k-t100` | 256K / 100 / 2K | off | 4 | 10×n=5 | 50/50 | **0** | **0.0008** (4/4989) | **turn ceiling** (+ mid-turn tok=2K trunc) | ~99K | mostly 101 turns; TCG overlap ~0.6%; f2p≈0 |
| **A2a** | `char-pilot1-clack-t500` | 256K / 500 / 16K | off | 4 | clack ×5 | 5/5 | **0** | ~0 | capability (clean `stop`) | ~147K | f2p≈0.2/82 |
| **A2b** | `char-think1b-clack-t250` | 256K / 250 / 32K | **high** | 4 | clack ×5 | 5/5 | **0** | ~0 | capability | ~144K | f2p≈5.6/82; KV~3–11% |
| **A2c** | `char-kvpack-tp2-think-high-n10` | 256K / 250 / 32K | **high** | **2** | clack ×5 (httpx Docker-fail) | 5/5 | **0** | ~0.002 | capability | ~131K | f2p≈7.0/82; KV peak **~27%**; prefer **TP=2** |
| **A3** | `char-qwen38-27b-clack-t250-xh` | 256K / 250 / 32K | **xhigh** | **4** | clack ×5 · **27B** · Pi | 5/5 | **0** | **0.048** (19/397) | capability | ~179K | f2p≈**48.4/82**; tools=412; 1 stream-end error (12-turn trial); invalid prior `thinking=high` wave quarantined |
| **A3b** | `char-qwen38-27b-happydom-t250-xh` | 256K / 250 / 32K | **xhigh** | **4** | happy-dom ×5 · **27B** · Pi | TBD | TBD | TBD | harness baseline | TBD | easier-task Pi baseline for B1/B2; env `qwen3.8-27b-happydom-pi` |
| **B1** | `char-qwen38-27b-msa-happydom-t250-xh` | 256K / 250 / 32K | **xhigh** | **4** | happy-dom ×5 · **27B** · **Mini-SWE** | **0** | **0/14** f2p (p2p 165/165) | **≈22.2%** (84/378) | harness vs A3b | DONE | All 5× `AgentTimeoutError` @ **10800s**; no submit/commit; never touched `AsyncTeardown.test.ts`. Infra OK (API+tools); incomplete fix. `LoopbackMiniSwe`. |
| **B2** | Flash-Next-FP8 | — | — | — | — | — | — | — | — | **skipped** | Perlmutter 4×A100-40GB: Triton MoE unsupported; marlin loads then OOM + PLE `fp8e4nv`. Need Hopper/≥64–80GB. |
| **T1** | `tmax-qwen38-27b-easy1-t100-xh` | 256K / 100 / 32K | **xhigh** | **4** | TMax short `task_004783_a0ba89ed` ×5 · **27B** · Pi | 5/5 | **5/5** | **0.241** (7/29) | pipeline OK | DONE | Reward **1.0** all trials (~5–7 turns). Natural Pi (no Multitool). |
| **T2** | `tmax-qwen38-27b-easy10-t100-xh` | 256K / 100 / 32K | **xhigh** | **4** | TMax short×10 × pass@5 · **27B** · Pi | 50/50 | **40/50** | **0.147** (43/293) | DeepSWE hardness | DONE | **Valid: 8/8 tasks = 40/40 reward 1.0.** Exclude 2 tasks (timeouts, not model fails): `001033` env-start×5; `009942` agent 600s×5. |

Env examples: `configs/models/qwen3.5-9b-pilot.env.example` (A0) · `…-a1-tp4-256k.env.example` (A1) · `…-a2-pilot1-t500` / `…-think-pilot1-clack` / `…-kvpack-tp2-think-high` (A2*) · `…/qwen3.8-27b-pilot1-clack.env.example` (A3) · `…/qwen3.8-27b-happydom-pi` (A3b) · `…/qwen3.8-27b-happydom-miniswe` (B1) · `…/qwen3.8-flash-happydom-pi` (B2) · `…/qwen3.8-27b-tmax-easy10-pi` (T2).

Analyze: `bash scripts/analyze_characterization_wave.sh <prefix>`.

---

## Takeaways

1. **Pipeline works:** TMax short+bash-only × Qwen3.8-27B × Harbor Pi → **T1 5/5** and **T2 40/40** reward 1.0 on the 8 fully graded tasks. DeepSWE reward 0 was **task hardness**, not a broken NERSC/Harbor/Pi path.
2. **Within-turn parallel (natural Pi):** 9B ≈0 · A3 DeepSWE ~4.8% · T1 TMax ~24% · T2 ~15%. Forced Multitool stress (separate report) is not required for non-zero parallel on 27B+TMax.
3. **Walls moved:** A0 = context → A1 = turns/`max_tokens` → A2* = **9B hardness** → A3 = **27B still DeepSWE reward=0** but much stronger F2P → **T\*** = easier benchmark unlocks reward 1.
4. **thinking:** on Qwen3.8-27B use **`xhigh`** (not `high` — vLLM 400).
5. **Serve:** 9B 256K×n=5 fits **TP=2**; **27B** uses **TP=4** / 256K / n=5.
6. **TCG exact-prefix reuse** drops as traces lengthen (A0 ~10% → A1 ~0.6%) → Exp B may need softer / early-turn keys.
7. **T2 timeouts (not counted as model fails):** `task_001033_d7fd9ed7` = Docker env-start 600s×5; `task_009942_0ca9b627` = Harbor agent wall 600s×5 (mid-rollout). No rerun planned.

---

## Ops (shared)

| Issue | Fix |
| --- | --- |
| Harbor Pi base URL | `OPENAI_BASE_URL=http://127.0.0.1:18081/v1` + `OPENAI_API_KEY=EMPTY` (set in `run_harbor_wave.sh`) |
| Cursor reaps Harbor | Terminal.app / `screen`; optional `.local-smoke/*.command` |
| Mac dies, NERSC up | `SYSML_ATTACH_JOB` + `SYSML_ATTACH_NODE` |
| Mac Docker 2×n=5 | bind/subnet races → `TASK_PARALLEL=1` or n≤3; `SYSML_TASK_STAGGER_SEC` |
| Knobs | `MAX_MODEL_LEN`/`CONTEXT_WINDOW` = capacity; `MAX_TOKENS` = per completion; `MAX_TURNS` = turn ceiling |

---

## Notes (optional detail)

- **A0:** large setup `bash` → HTTP 400 / `length` at ≥8192; turns=8 not binding. Artifacts: `results/characterization/char-setup-10t-k5/`.
- **A1:** ~6 h wall; 5 Slurm recycles; 49/50 sessions hit turns=100 then stub `error`; 153× mid-turn `length` at output=2048. Artifacts: `…/char-setup-10t-ctx256k-t100/`.
- **A2c:** intended 2 Harbor tasks; only clack graded. Summary JSON: `…/char-kvpack-tp2-think-high-n10/tp2_pilot_summary.json`.
- **A3:** `Qwen/Qwen3.8-27B`, thinking=`xhigh`, ~4h wall (job `60724155`). Summary: `…/char-qwen38-27b-clack-t250-xh/pilot_summary.json`. Do not use quarantined `char-qwen38-27b-clack-t250` (`thinking=high` → turn-1 400s).
- **A3b/B1/B2:** task list `configs/experiment-tasks-easy1.txt`; agent switch via `SYSML_HARBOR_AGENT` in `scripts/run_harbor_wave.sh`. Flash-Next download: `scripts/download_qwen3_8_flash_next_fp8.py`.
- **T1/T2 (TMax):** local Harbor tasks in `variants/tmax-easy/tasks/` (extracted from HF `TMaxxx/TMax-15K-Harbor` short+bash-only). Reproduce T2: `set -a && source configs/models/qwen3.8-27b-tmax-easy10-pi.env.example && set +a` then `bash scripts/run_experiment.sh none` (stock Pi; **no** `--parallel-test`). Valid solve set (8): all easy10 ids except `task_001033_d7fd9ed7` and `task_009942_0ca9b627`.
