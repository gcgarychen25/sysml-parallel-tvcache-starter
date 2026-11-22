"""Trace-replay simulator: what would a given cache design have hit?

Rollouts of one task ran concurrently against one cache. We replay every
call in recorded start-time order and ask, for each call: had an earlier
rollout already finished the same key (HIT), is one running it right now
(WAIT, joins it), or must it execute (MISS)?

A design is a set of rules (``Policy``):
  * key normalization   - which calls count as "the same call"
  * mutation rule       - which calls extend the stateful history in the key
  * turn ordering       - whether state-changing calls in one turn are keyed
                          in emitted order or as an order-free set
  * in-flight sharing   - whether a call may wait on another rollout's
                          identical in-flight call instead of re-running it

Tool-wait accounting follows the handout: the calls in a turn run in
parallel, so a turn costs its slowest call. Baseline turn wait = max
duration. With the cache, HIT ~ 1 ms, WAIT = remaining time of the owner,
MISS = full duration. Saved % = 1 - cached / baseline over all turns.

Correctness proxy: a HIT is "stale" when the cached output differs from the
output this rollout actually got. Some tools are noisy (``ls -la`` times,
temp names), so a small stale rate is expected even for a correct key; a
jump in stale rate means the key is too loose.

Limits: recorded timing is used as-is (a faster rollout would change the
interleaving), and file-system state is not in the traces, so keys based on
file contents cannot be evaluated here.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

from parallel_tvcache.replay.traces import Call, Rollout, load_rollouts

HIT_COST_S = 0.001
TYPICAL_MISS_MAX_S = 5.0   # same cutoff as parallel_tvcache/cache/metrics.py

# ---- rules ------------------------------------------------------------------

READ_ONLY_TOOLS = {"read", "grep", "find", "ls"}
# bash programs that only read, when used without redirection or chaining
READ_ONLY_PROGRAMS = {"cat", "head", "tail", "ls", "grep", "rg", "find", "wc", "pwd",
                      "file", "stat", "tree", "which", "echo", "diff", "du"}
READ_ONLY_GIT = {"status", "log", "diff", "show", "branch", "rev-parse", "ls-files", "blame"}
UNSAFE = re.compile(r"(>|\btee\b|\|\s*sh\b|\bxargs\b|`|\$\(|\bsed\s+-i|-delete\b|-exec\b)")


def default_mutates(call: Call) -> bool:
    return call.tool not in READ_ONLY_TOOLS


def _strip_cd(cmd: str) -> str:
    return re.sub(r"^\s*cd\s+\S+\s*&&\s*", "", cmd)


def readonly_bash(call: Call) -> bool:
    """Conservative allowlist: a single read-only program, no redirects/chains."""
    if call.tool != "bash":
        return False
    cmd = _strip_cd(str(call.args.get("command", "")))
    if not cmd or UNSAFE.search(cmd):
        return False
    for segment in re.split(r"\s*(?:&&|\|\||;|\|)\s*", cmd):
        try:
            words = shlex.split(segment)
        except ValueError:
            return False
        if not words:
            continue
        prog = words[0].rsplit("/", 1)[-1]
        if prog == "git":
            sub = next((w for w in words[1:] if not w.startswith("-")), "")
            if sub not in READ_ONLY_GIT:
                return False
        elif prog not in READ_ONLY_PROGRAMS:
            return False
    return True


def mutates_with_readonly_bash(call: Call) -> bool:
    return default_mutates(call) and not readonly_bash(call)


def exact_key(call: Call) -> str:
    return call.tool + ":" + json.dumps(call.args, sort_keys=True, separators=(",", ":"))


IGNORED_ARGS = {"timeout"}


def normalized_key(call: Call) -> str:
    args = {k: v for k, v in call.args.items() if k not in IGNORED_ARGS}
    if call.tool == "bash" and "command" in args:
        args["command"] = " ".join(str(args["command"]).split())
    return call.tool + ":" + json.dumps(args, sort_keys=True, separators=(",", ":"))


@dataclass(frozen=True)
class Policy:
    name: str
    key: Callable[[Call], str] = exact_key
    mutates: Callable[[Call], bool] = default_mutates
    order_free_turns: bool = False
    share_in_flight: bool = False
    history_free: bool = False      # ignore prior commands entirely (unsafe ceiling)


POLICIES = {
    "sequential": Policy("Sequential (existing TVCache)"),
    "design_a": Policy("Design A (in-flight sharing)", share_in_flight=True),
    "c1_normalize": Policy("A + C1 normalized keys", key=normalized_key, share_in_flight=True),
    "c2_readonly_bash": Policy("A + C2 read-only bash", mutates=mutates_with_readonly_bash,
                               share_in_flight=True),
    "c3_order_free": Policy("A + C3 order-free turns", order_free_turns=True, share_in_flight=True),
    "ceiling_history_free": Policy("Ceiling: ignore history (unsafe)", key=normalized_key,
                                   share_in_flight=True, history_free=True),
    "design_c": Policy("Design C (C1+C2+C3)", key=normalized_key, mutates=mutates_with_readonly_bash,
                       order_free_turns=True, share_in_flight=True),
}

# ---- simulation -------------------------------------------------------------


@dataclass
class Event:
    rollout: int
    turn: int
    call: Call
    key: str


def keyed_events(rollouts: list[Rollout], policy: Policy) -> list[Event]:
    """Full cache key of every call, from its own rollout's history."""
    events: list[Event] = []
    for ri, r in enumerate(rollouts):
        chain: list[str] = []
        for turn in r.turns:
            if policy.history_free:
                events.extend(Event(ri, turn.index, c, policy.key(c)) for c in turn.calls)
                continue
            calls = turn.calls
            muts = [c for c in calls if policy.mutates(c)]
            if policy.order_free_turns:
                base = "|".join(chain)
                for c in calls:
                    events.append(Event(ri, turn.index, c, base + "#" + policy.key(c)))
                chain.extend(sorted(policy.key(c) for c in muts))
            else:
                for c in calls:
                    events.append(Event(ri, turn.index, c, "|".join(chain) + "#" + policy.key(c)))
                    if policy.mutates(c):
                        chain.append(policy.key(c))
    return events


@dataclass
class Result:
    policy: str
    calls: int = 0
    hits: int = 0
    waits: int = 0
    stale_hits: int = 0
    turns: int = 0
    turns_any_hit: int = 0
    turns_full_hit: int = 0
    baseline_wait_s: float = 0.0
    cached_wait_s: float = 0.0
    call_costs: list[tuple[float, str]] = field(default_factory=list)   # (cost, kind) per call
    decisions: list[tuple[str | None, str]] = field(default_factory=list)  # (live, simulated)
    per_task: dict[str, dict[str, float]] = field(default_factory=dict)

    def row(self) -> dict[str, Any]:
        c, t = max(self.calls, 1), max(self.turns, 1)
        return {
            "design": self.policy,
            "calls": self.calls,
            "call_hit_%": round(100 * (self.hits + self.waits) / c, 1),
            "of_which_wait": self.waits,
            "turns_any_hit_%": round(100 * self.turns_any_hit / t, 1),
            "turns_full_hit_%": round(100 * self.turns_full_hit / t, 1),
            "tool_wait_saved_%": round(100 * (1 - self.cached_wait_s / max(self.baseline_wait_s, 1e-9)), 1),
            "saved_team_%": self.team_saved_pct(),
            "stale_hits": self.stale_hits,
        }

    def team_saved_pct(self) -> float | None:
        """Poster formula (metrics.py): each reuse is credited a typical miss.

        typical = median miss time under 5 s; counterfactual replaces every
        hit/wait with ``typical``; saved = 1 - actual / counterfactual.
        """
        misses = [c for c, k in self.call_costs if k == "miss"]
        clean = [x for x in misses if x < TYPICAL_MISS_MAX_S] or misses
        if not clean:
            return None
        typical = statistics.median(clean)
        actual = sum(c for c, _ in self.call_costs)
        cf = sum(typical if k != "miss" else c for c, k in self.call_costs)
        return round(100 * (1 - actual / cf), 1) if cf > 0 else None

    def agreement(self) -> dict[str, Any] | None:
        """Simulated vs live decisions, for traces recorded with TVCache on."""
        pairs = [(("reuse" if l in ("hit", "inflight") else "miss"),
                  ("reuse" if s in ("hit", "wait") else "miss"))
                 for l, s in self.decisions if l is not None]
        if not pairs:
            return None
        both = sum(a == b == "reuse" for a, b in pairs)
        return {"calls": len(pairs), "agree_%": round(100 * sum(a == b for a, b in pairs) / len(pairs), 1),
                "live_reuse": sum(a == "reuse" for a, _ in pairs),
                "sim_reuse": sum(b == "reuse" for _, b in pairs), "both_reuse": both}


def simulate(rollouts: list[Rollout], policy: Policy) -> Result:
    res = Result(policy.name)
    by_task: dict[str, list[Rollout]] = defaultdict(list)
    for r in rollouts:
        by_task[r.task].append(r)

    for task, group in sorted(by_task.items()):
        events = sorted(keyed_events(group, policy), key=lambda e: e.call.start)
        done: dict[str, tuple[float, str]] = {}       # key -> (finish time, output hash)
        running: dict[str, float] = {}                # key -> finish time of the owner
        cost: dict[tuple[int, int, str], tuple[float, str]] = {}
        for e in events:
            c, t = e.call, e.call.start
            if e.key in done and done[e.key][0] <= t:
                cost[(e.rollout, e.turn, c.call_id)] = (HIT_COST_S, "hit")
                if done[e.key][1] != c.output_hash:
                    res.stale_hits += 1
                continue
            if policy.share_in_flight and e.key in running and running[e.key] > t:
                cost[(e.rollout, e.turn, c.call_id)] = (min(c.duration, running[e.key] - t), "wait")
                continue
            cost[(e.rollout, e.turn, c.call_id)] = (c.duration, "miss")
            if not c.is_error and e.key not in done:
                finish = t + c.duration
                running.setdefault(e.key, finish)
                done.setdefault(e.key, (finish, c.output_hash))

        t_base = t_cached = 0.0
        for ri, r in enumerate(group):
            for turn in r.turns:
                if not turn.calls:
                    continue
                kinds = [cost[(ri, turn.index, c.call_id)] for c in turn.calls]
                res.call_costs.extend(kinds)
                res.decisions.extend((c.live_source, k) for c, (_, k) in zip(turn.calls, kinds))
                res.turns += 1
                res.calls += len(kinds)
                n_hit = sum(k == "hit" for _, k in kinds)
                n_wait = sum(k == "wait" for _, k in kinds)
                res.hits += n_hit
                res.waits += n_wait
                res.turns_any_hit += (n_hit + n_wait) > 0
                res.turns_full_hit += (n_hit + n_wait) == len(kinds)
                b = max(c.duration for c in turn.calls)
                w = max(s for s, _ in kinds)
                t_base += b
                t_cached += w
        res.baseline_wait_s += t_base
        res.cached_wait_s += t_cached
        res.per_task[task] = {"rollouts": len(group),
                              "saved_%": round(100 * (1 - t_cached / max(t_base, 1e-9)), 1)}
    return res


def main() -> None:
    p = argparse.ArgumentParser(description="Replay Pi traces under cache designs")
    p.add_argument("jobs", help="jobs/ directory with Harbor trials")
    p.add_argument("--prefix", help="job-name prefix (one wave)")
    p.add_argument("--policies", default=",".join(POLICIES))
    p.add_argument("--json", help="write results here")
    a = p.parse_args()

    rollouts = load_rollouts(a.jobs, a.prefix)
    if not rollouts:
        raise SystemExit(f"No Pi sessions found under {a.jobs!r}"
                         + (f" with prefix {a.prefix!r}" if a.prefix else "")
                         + " - check the path, or unzip the traces into jobs/ first.")
    durs = [c.duration for r in rollouts for c in r.calls if not c.is_error]
    print(f"{len(rollouts)} rollouts, {len({r.task for r in rollouts})} tasks, "
          f"{sum(len(r.calls) for r in rollouts)} calls, "
          f"median call {statistics.median(durs) if durs else 0:.2f}s")
    results = [simulate(rollouts, POLICIES[n]) for n in a.policies.split(",")]
    rows = [r.row() for r in results]
    cols = list(rows[0])
    print(" | ".join(cols))
    for r in rows:
        print(" | ".join(str(r[c]) for c in cols))
    live = sum(c.live_source is not None for r in rollouts for c in r.calls)
    if live:
        print(f"\nValidation against the live cache ({live} calls with a recorded decision):")
        for res in results:
            print(f"  {res.policy}: {res.agreement()}")
    if a.json:
        with open(a.json, "w") as f:
            json.dump(rows, f, indent=2)


if __name__ == "__main__":
    main()