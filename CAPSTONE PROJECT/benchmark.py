"""Generate deterministic workloads and benchmark planner components."""
import argparse
import csv
import json
from pathlib import Path
from random import Random
from statistics import median

from courier import plan


def workload(size, seed):
    rng = Random(seed)
    nodes = ["Depot"] + [f"N{i:03}" for i in range(1, size)]
    roads = [[nodes[i - 1], nodes[i], rng.randint(1, 9)] for i in range(1, size)]
    for i in range(size):
        for j in range(i + 2, min(i + 5, size)):
            if rng.random() < .65:
                roads.append([nodes[i], nodes[j], rng.randint(2, 20)])
    parcels = [
        {"id": f"P{i:04}", "stop": rng.choice(nodes[1:]), "weight": rng.randint(1, 25),
         "priority": rng.randint(1, 40), "deadline": f"2026-12-{rng.randint(1, 28):02}"}
        for i in range(size * 4)
    ]
    return dict(depot=nodes[0], capacity=size * 3, nodes=nodes, roads=roads, parcels=parcels)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=Path("data"))
    parser.add_argument("--output", type=Path, default=Path("evidence/runtime.csv"))
    parser.add_argument("--runs", type=int, default=9)
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be positive")
    args.data.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for size in [12, 32, 64, 128]:
        data = workload(size, 4100 + size)
        (args.data / f"synthetic_{size}.json").write_text(json.dumps(data, indent=2) + "\n")
        plan(data)
        results = [plan(data) for _ in range(args.runs)]
        last = results[-1]
        rows.append(dict(nodes=size, roads=len(data["roads"]), parcels=len(data["parcels"]),
                         capacity=data["capacity"], selected=len(last["selected"]),
                         stops=len(last["deliveries"]), distance=last["distance"],
                         runs=args.runs, **{
                             f"{key}_ms": median(result["runtime_ms"][key] for result in results)
                             for key in last["runtime_ms"]
                         }))
    with args.output.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(args.output)


if __name__ == "__main__":
    main()
