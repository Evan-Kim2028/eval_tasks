#!/usr/bin/env python3
"""Parse Harbor trial result.json files into a timings table and sqlite db."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def _seconds(started: str | None, finished: str | None) -> float | None:
    a = _parse_dt(started)
    b = _parse_dt(finished)
    if a is None or b is None:
        return None
    return (b - a).total_seconds()


def _phase(block: dict | None) -> float | None:
    if not isinstance(block, dict):
        return None
    return _seconds(block.get("started_at"), block.get("finished_at"))


def _reward(trial: dict) -> float | None:
    verifier = trial.get("verifier_result") or {}
    rewards = verifier.get("rewards") or {}
    value = rewards.get("reward")
    if value is None:
        return None
    return float(value)


def _model(trial: dict) -> str:
    agent = trial.get("agent_info") or {}
    info = agent.get("model_info") or {}
    name = info.get("name")
    if name:
        return str(name)
    cfg = ((trial.get("config") or {}).get("agent") or {}).get("model_name")
    return str(cfg or "")


def _agent(trial: dict) -> str:
    info = trial.get("agent_info") or {}
    if info.get("name"):
        return str(info["name"])
    cfg = ((trial.get("config") or {}).get("agent") or {}).get("name")
    return str(cfg or "")


def iter_trials(jobs_dir: Path) -> list[dict]:
    rows = []
    for path in sorted(jobs_dir.glob("*/*/result.json")):
        if path.parent.name.startswith("."):
            continue
        job = path.parent.parent.name
        trial_name = path.parent.name
        try:
            trial = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError) as exc:
            print(f"skip {path}: {exc}", file=sys.stderr)
            continue
        if not isinstance(trial, dict) or "task_name" not in trial:
            continue
        rows.append(
            {
                "job": job,
                "trial": trial_name,
                "agent": _agent(trial),
                "model": _model(trial),
                "reward": _reward(trial),
                "env_s": _phase(trial.get("environment_setup")),
                "setup_s": _phase(trial.get("agent_setup")),
                "exec_s": _phase(trial.get("agent_execution")),
                "verify_s": _phase(trial.get("verifier")),
                "total_s": _seconds(trial.get("started_at"), trial.get("finished_at")),
                "started_at": trial.get("started_at") or "",
            }
        )
    return rows


def write_sqlite(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("DROP TABLE IF EXISTS trials")
        conn.execute(
            """
            CREATE TABLE trials (
                job TEXT,
                trial TEXT,
                agent TEXT,
                model TEXT,
                reward REAL,
                env_s REAL,
                setup_s REAL,
                exec_s REAL,
                verify_s REAL,
                total_s REAL,
                started_at TEXT
            )
            """
        )
        conn.executemany(
            """
            INSERT INTO trials (
                job, trial, agent, model, reward,
                env_s, setup_s, exec_s, verify_s, total_s, started_at
            ) VALUES (
                :job, :trial, :agent, :model, :reward,
                :env_s, :setup_s, :exec_s, :verify_s, :total_s, :started_at
            )
            """,
            rows,
        )
        conn.commit()
    finally:
        conn.close()


def _fmt(value: float | None) -> str:
    if value is None:
        return "-"
    if value >= 100:
        return f"{value:.0f}"
    return f"{value:.1f}"


def print_table(rows: list[dict]) -> None:
    header = (
        f"{'job':<42} {'agent':<12} {'model':<22} "
        f"{'env':>6} {'setup':>6} {'exec':>6} {'verify':>6} {'total':>6} {'rwd':>5}"
    )
    print(header)
    for row in rows:
        print(
            f"{row['job'][:42]:<42} {row['agent'][:12]:<12} {row['model'][:22]:<22} "
            f"{_fmt(row['env_s']):>6} {_fmt(row['setup_s']):>6} {_fmt(row['exec_s']):>6} "
            f"{_fmt(row['verify_s']):>6} {_fmt(row['total_s']):>6} {_fmt(row['reward']):>5}"
        )


def print_summary(rows: list[dict]) -> None:
    groups: dict[str, list[dict]] = {}
    for row in rows:
        key = row["agent"] or "?"
        groups.setdefault(key, []).append(row)
    print("\nmean seconds by agent")
    print(f"{'agent':<16} {'n':>4} {'setup':>8} {'exec':>8} {'verify':>8} {'total':>8}")
    for agent, items in sorted(groups.items()):
        n = len(items)
        def mean(field: str) -> float | None:
            vals = [x[field] for x in items if x[field] is not None]
            if not vals:
                return None
            return sum(vals) / len(vals)

        print(
            f"{agent[:16]:<16} {n:>4} {_fmt(mean('setup_s')):>8} "
            f"{_fmt(mean('exec_s')):>8} {_fmt(mean('verify_s')):>8} "
            f"{_fmt(mean('total_s')):>8}"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jobs-dir", type=Path, default=Path("jobs"))
    parser.add_argument("--sqlite", type=Path, default=Path("jobs/timings.sqlite"))
    parser.add_argument("--match", default="", help="Substring filter on job name")
    args = parser.parse_args()
    if not args.jobs_dir.is_dir():
        raise SystemExit(f"missing jobs dir: {args.jobs_dir}")
    rows = iter_trials(args.jobs_dir)
    if args.match:
        rows = [row for row in rows if args.match in row["job"]]
    if not rows:
        raise SystemExit("no trial result.json files found")
    write_sqlite(args.sqlite, rows)
    print_table(rows)
    print_summary(rows)
    print(f"\nwrote {args.sqlite} ({len(rows)} trials)", file=sys.stderr)


if __name__ == "__main__":
    main()
