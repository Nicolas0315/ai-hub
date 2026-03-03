#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from statistics import mean


def load_csv(path: str) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append({
                "time_min": float(row["time_min"]),
                "bugs": float(row["bugs"]),
                "rework": float(row["rework"]),
            })
    if not rows:
        raise ValueError(f"no rows: {path}")
    return rows


def avg(rows: list[dict[str, float]], key: str) -> float:
    return mean(x[key] for x in rows)


def ratio(human: float, katala: float) -> float:
    if katala <= 0:
        return 300.0
    return (human / katala) * 100.0


def main() -> int:
    p = argparse.ArgumentParser(description="Compute Katala vs Human performance %")
    p.add_argument("--human", required=True, help="human metrics csv")
    p.add_argument("--katala", required=True, help="katala metrics csv")
    p.add_argument("--w-time", type=float, default=0.4)
    p.add_argument("--w-bugs", type=float, default=0.35)
    p.add_argument("--w-rework", type=float, default=0.25)
    args = p.parse_args()

    human = load_csv(args.human)
    katala = load_csv(args.katala)

    h_time = avg(human, "time_min")
    h_bugs = avg(human, "bugs")
    h_rework = avg(human, "rework")

    k_time = avg(katala, "time_min")
    k_bugs = avg(katala, "bugs")
    k_rework = avg(katala, "rework")

    p_time = ratio(h_time, k_time)
    p_bugs = ratio(h_bugs, k_bugs)
    p_rework = ratio(h_rework, k_rework)

    total_w = args.w_time + args.w_bugs + args.w_rework
    overall = (p_time * args.w_time + p_bugs * args.w_bugs + p_rework * args.w_rework) / total_w

    print("Katala vs Human performance")
    print(f"time     : {p_time:.1f}%")
    print(f"bugs     : {p_bugs:.1f}%")
    print(f"rework   : {p_rework:.1f}%")
    print(f"overall  : {overall:.1f}%")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
