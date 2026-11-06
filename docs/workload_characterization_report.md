# Experiment A — workload characterization

**Mode:** `none` (no TVCache) · **Models:** `Qwen/Qwen3.5-9B` (A0–A2) · `Qwen/Qwen3.8-27B` (A3/A3b/B1/T1–T2) · `Qwen/Qwen3.8-Flash-Next-FP8` (B2 skipped) · **Reproduce:** root `README.md`  
**How to extend:** add one row to **Cells** (+ optional one-line note under **Notes**). Published pack: `artifacts/expA-traces-A0-A2.zip` (unzip at repo root). Local full runs stay in gitignored `jobs/` / `results/`.

### Stack (do not conflate)

| Layer | What it is | This report |
| --- | --- | --- |
| **Orchestrator** | Harbor (`harbor run`) | Always Harbor on the Mac |
| **Agent / harness** | Who emits tools inside the sandbox | **Pi** = `LoopbackPi` (default Exp A / **T1–T2**). **Mini-SWE** = `LoopbackMiniSwe` (**B1 only**) |
| **Task suite** | Benchmark folders Harbor loads | **DeepSWE** = `variants/deep-swe-setup/` (A0–A3b, B1). **TMax** = `variants/tmax-easy/` (**T1–T2** only) |

**DeepSWE is a task suite, not a harness.** Saying “DeepSWE failed” means those SWE tasks stayed reward 0 on the same Pi path — not that we used a DeepSWE agent. **T1/T2** = same **Harbor + Pi** path, different (easier) **TMax** tasks. Env: `SYSML_HARBOR_AGENT=pi` in `configs/models/qwen3.8-27b-tmax-easy*-pi.env.example`.

---

## Cells (summary)

| Cell | Prefix | Ctx / turns / tok | Think | TP×GPU | Scope | Sess | Rew>0 | Parallel-turn | Binding limit | Peak prompt | Notes |
| --- | --- | --- | --- | ---: | --- | ---: | ---: | --- | --- | --- | --- |
| **A0** | `char-setup-10t-k5` | 8K / 8 / 2K | off | 1×80GB | DeepSWE setup ×10 ×n=5 · **Pi** | 50/50 | **0** | **0.00** (0/199) | **8K context** | ~8K | final `length`×38 `error`×12; TCG prefix overlap ~10% |
| **A1** | `char-setup-10t-ctx256k-t100` | 256K / 100 / 2K | off | 4 | DeepSWE setup ×10 ×n=5 · **Pi** | 50/50 | **0** | **0.0008** (4/4989) | **turn ceiling** (+ mid-turn tok=2K trunc) | ~99K | mostly 101 turns; TCG overlap ~0.6%; f2p≈0 |
| **A2a** | `char-pilot1-clack-t500` | 256K / 500 / 16K | off | 4 | DeepSWE clack ×5 · **Pi** | 5/5 | **0** | ~0 | capability (clean `stop`) | ~147K | f2p≈0.2/82 |
| **A2b** | `char-think1b-clack-t250` | 256K / 250 / 32K | **high** | 4 | DeepSWE clack ×5 · **Pi** | 5/5 | **0** | ~0 | capability | ~144K | f2p≈5.6/82; KV~3–11% |
| **A2c** | `char-kvpack-tp2-think-high-n10` | 256K / 250 / 32K | **high** | **2** | DeepSWE clack ×5 · **Pi** (httpx Docker-fail) | 5/5 | **0** | ~0.002 | capability | ~131K | f2p≈7.0/82; KV peak **~27%**; prefer **TP=2** |
| **A3** | `char-qwen38-27b-clack-t250-xh` | 256K / 250 / 32K | **xhigh** | **4** | DeepSWE clack ×5 · **27B** · **Pi** | 5/5 | **0** | **0.048** (19/397) | capability | ~179K | f2p≈**48.4/82**; tools=412; 1 stream-end error (12-turn trial); invalid prior `thinking=high` wave quarantined |
| **A3b** | `char-qwen38-27b-happydom-t250-xh` | 256K / 250 / 32K | **xhigh** | **4** | DeepSWE happy-dom ×5 · **27B** · **Pi** | — | — | — | — | — | **Not completed** (no graded jobs). B1 ran without this Pi baseline. Env `qwen3.8-27b-happydom-pi`. |
| **B1** | `char-qwen38-27b-msa-happydom-t250-xh` | 256K / 250 / 32K | **xhigh** | **4** | DeepSWE happy-dom ×5 · **27B** · **Mini-SWE** | 5/5 | **0** (f2p 0/14; p2p 165/165) | **≈22.2%** (84/378) | harness isolation | — | All 5× `AgentTimeoutError` @ **10800s**; no submit/commit. Infra OK; incomplete fix. `LoopbackMiniSwe` (not Pi). |
| **B2** | Flash-Next-FP8 | — | — | — | DeepSWE happy-dom · Flash-Next · Pi (planned) | — | — | — | — | — | **Skipped** — Perlmutter 4×A100-40GB: Triton MoE unsupported; marlin then OOM + PLE `fp8e4nv`. Need Hopper/≥64–80GB. |
| **T1** | `tmax-qwen38-27b-easy1-t100-xh` | 256K / 100 / 32K | **xhigh** | **4** | **TMax** `task_004783_a0ba89ed` ×5 · **27B** · **Pi** | 5/5 | **5/5** | **0.241** (7/29) | pipeline OK | — | Reward **1.0** (~5–7 turns). Stock `LoopbackPi`; natural prompt (no Multitool). Not DeepSWE tasks; not Mini-SWE. |
| **T2** | `tmax-qwen38-27b-easy10-t100-xh` | 256K / 100 / 32K | **xhigh** | **4** | **TMax** short×10 × pass@5 · **27B** · **Pi** | **45** Pi / **50** trials | **40/50** | **0.147** (43/293) | DeepSWE **task** hardness (harness OK) | — | **Valid: 8/8 tasks = 40/40 reward 1.0.** Same Harbor+Pi path as A*; only task suite changed. Timeouts (not model fails): `001033` env-start×5 (no Pi session); `009942` agent 600s×5. |

Env examples: `configs/models/qwen3.5-9b-pilot.env.example` (A0) · `…-a1-tp4-256k.env.example` (A1) · `…-a2-pilot1-t500` / `…-think-pilot1-clack` / `…-kvpack-tp2-think-high` (A2*) · `…/qwen3.8-27b-pilot1-clack.env.example` (A3) · `…/qwen3.8-27b-happydom-pi` (A3b) · `…/qwen3.8-27b-happydom-miniswe` (B1) · `…/qwen3.8-flash-happydom-pi` (B2) · `…/qwen3.8-27b-tmax-easy-pi` (T1) · `…/qwen3.8-27b-tmax-easy10-pi` (T2) · `…/qwen3.8-27b-tmax-easy8-tvcache-seq.env.example` (Exp B).

Analyze: `bash scripts/analyze_characterization_wave.sh <prefix>` (optional `--benchmark TMax` — default label is `DeepSWE` and is **only a JSON tag**, not the harness). Artifacts: `results/characterization/<prefix>/` (`manifest.json`, `parallel_summary.json`, `run-batched.log`).

---

## Takeaways

1. **Pipeline works (Harbor + Pi unchanged):** T1/T2 kept **`LoopbackPi`** and only swapped the **task suite** to TMax short+bash-only → **T1 5/5**, **T2 40/40** reward 1.0 on 8 graded tasks. Prior DeepSWE reward 0 was **DeepSWE task hardness**, not a broken NERSC/Harbor/Pi path and not Mini-SWE.
2. **Within-turn parallel (natural Pi):** 9B ≈0 · A3 DeepSWE-tasks ~4.8% · T1 TMax ~24% · T2 ~15%. Forced Multitool stress (separate report) is not required for non-zero parallel on 27B+TMax.
3. **Walls moved:** A0 = context → A1 = turns/`max_tokens` → A2* = **9B hardness** → A3 = **27B still DeepSWE-task reward=0** but much stronger F2P → **T\*** = easier **TMax** tasks unlock reward 1 on the **same Pi harness**.
4. **thinking:** on Qwen3.8-27B use **`xhigh`** (not `high` — vLLM 400).
5. **Serve:** 9B 256K×n=5 fits **TP=2**; **27B** uses **TP=4** / 256K / n=5.
6. **TCG exact-prefix reuse** drops as traces lengthen (A0 ~10% → A1 ~0.6%) → Exp B may need softer / early-turn keys.
7. **T2 timeouts (not counted as model fails):** `task_001033_d7fd9ed7` = Docker env-start 600s×5 → **no Pi session** (explains 45 sessions vs 50 trials); `task_009942_0ca9b627` = Harbor agent wall 600s×5 (mid-rollout). No rerun planned.
8. **A3b gap:** happy-dom × Pi never finished; do not treat B1 Mini-SWE as a Pi baseline comparison.

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
- **A3b/B1/B2:** DeepSWE task list `configs/experiment-tasks-easy1.txt`; harness via `SYSML_HARBOR_AGENT` (`pi` vs `mini-swe-agent`) in `scripts/run_harbor_wave.sh`. **A3b not completed.** Flash-Next download: `scripts/download_qwen3_8_flash_next_fp8.py`.
- **T1/T2 (TMax tasks × Pi harness):** Not DeepSWE tasks; not Mini-SWE. Agent = stock Harbor **`LoopbackPi`** (`SYSML_HARBOR_AGENT=pi`). Tasks = `variants/tmax-easy/tasks/` (from HF `TMaxxx/TMax-15K-Harbor` short+bash-only). Reproduce T2: `set -a && source configs/models/qwen3.8-27b-tmax-easy10-pi.env.example && set +a` then `bash scripts/run_experiment.sh none` (**no** `--parallel-test`). Valid solve set (8): `configs/experiment-tasks-tmax-easy8.txt`. Evidence dir: `results/characterization/tmax-qwen38-27b-easy10-t100-xh/` (older `manifest.json` may still say `purpose=deep-swe-setup-variants-10task` — that string was hardcoded in the runner; fixed to follow `task_root`).

---

## Exp B — sequential TVCache (2026-11-05)

**Not** an Exp A cell. Same matched knobs as T2 / README Table 2 (Harbor+Pi · 27B · pass@5 · 256K/100/xhigh/TP4), mode `sequential` (`TvcacheLoopbackPi` + Mac `tvcache-rust` + TCP tool gateway).

| Wave | Prefix | Tasks | Reward | TVCache tools / Table 2 |
| --- | --- | --- | --- | --- |
| easy1 (pilot) | `tmax-qwen38-27b-easy1-tvcache-seq-t100-xh` | `004783` | **4/5** (+1 `AgentTimeoutError`) | 34 calls · 8 hits |
| easy2 (pilot) | `tmax-qwen38-27b-easy2-tvcache-seq-t100-xh` | `004205`, `004019` | **5/5** + **5/5** | 60 calls · 7 hits |
| **easy8 (handout)** | `tmax-qwen38-27b-easy8-tvcache-seq-t100-xh` | all 8 ids in `experiment-tasks-tmax-easy8.txt` | **40/40** (pass@5 **8/8**) | **256** calls · **23** hits · call **9.0%** · turn **8.7%** (18/208) · tool-wait saved **−5.2%** |

Handout Table 2 Exp B row = **easy8** (`tvcache-summary.json`). Pilot pooled ~16% hit was 3-task warm-up only. Tool-wait % is vs median clean miss (<5s); one ~76s labeled hit makes the counterfactual negative — typical hits are ~1ms. Ops: Pi↔gateway **TCP** `host.docker.internal:17878`; sandbox workdir **`/home/user`**; start TVCache via `screen` / `os.setsid` (Cursor-shell `nohup` can reap `:17878`). Teammate entry: root `README.md`.
