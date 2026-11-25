"""Single-vehicle courier planning and command-line interface."""
import argparse
from dataclasses import dataclass
from datetime import date
from heapq import heappop, heappush
import json
from math import inf
from pathlib import Path
from time import perf_counter_ns


@dataclass(frozen=True)
class Parcel:
    id: str
    stop: str
    weight: int
    priority: int
    deadline: date


def positive(value):
    if type(value) is not int or value <= 0:
        raise ValueError("Weights, distances, priorities and capacity must be positive integers")
    return value


def parse(data):
    depot = data["depot"]
    graph = {}
    for node in data["nodes"]:
        if not isinstance(node, str) or not node or node in graph:
            raise ValueError("Node names must be nonempty and unique")
        graph[node] = {}
    if depot not in graph:
        raise ValueError("Missing depot node")
    for a, b, distance in data["roads"]:
        if a not in graph or b not in graph or a == b or b in graph[a]:
            raise ValueError("Invalid or duplicate road")
        graph[a][b] = graph[b][a] = positive(distance)
    parcels = []
    ids = set()
    for item in data["parcels"]:
        ident, stop = item["id"], item["stop"]
        if not isinstance(ident, str) or not ident or ident in ids:
            raise ValueError("Parcel IDs must be nonempty and unique")
        if stop not in graph or stop == depot:
            raise ValueError("Parcel must reference a customer node")
        ids.add(ident)
        parcels.append(Parcel(ident, stop, positive(item["weight"]),
                              positive(item["priority"]), date.fromisoformat(item["deadline"])))
    return depot, graph, parcels, positive(data["capacity"])


def prioritize(parcels):
    return sorted(parcels, key=lambda p: (p.deadline, -p.priority, p.id))


def pack(parcels, capacity):
    """Return selected parcels and byte rows recording DP include decisions."""
    best = [0] * (capacity + 1)
    decisions = []
    for parcel in parcels:
        take = bytearray(capacity + 1)
        for weight in range(capacity, parcel.weight - 1, -1):
            candidate = best[weight - parcel.weight] + parcel.priority
            if candidate > best[weight]:
                best[weight] = candidate
                take[weight] = 1
        decisions.append(take)
    remaining = capacity
    selected = []
    for parcel, take in zip(reversed(parcels), reversed(decisions)):
        if take[remaining]:
            selected.append(parcel)
            remaining -= parcel.weight
    return list(reversed(selected)), best


def dijkstra(graph, source, targets=None):
    distances, previous = {source: 0}, {}
    queue = [(0, source)]
    outstanding = None if targets is None else set(targets)
    while queue:
        distance, node = heappop(queue)
        if distance != distances[node]:
            continue
        if outstanding is not None:
            outstanding.discard(node)
            if not outstanding:
                break
        for adjacent, length in sorted(graph[node].items()):
            candidate = distance + length
            if candidate < distances.get(adjacent, inf):
                distances[adjacent] = candidate
                previous[adjacent] = node
                heappush(queue, (candidate, adjacent))
    return distances, previous


def shortest_paths(graph, depot, stops, depot_result):
    return {depot: depot_result, **{
        stop: dijkstra(graph, stop, stops | {depot}) for stop in sorted(stops)
    }}


def route(depot, stops, paths):
    pending = set(stops)
    current = depot
    order, legs = [depot], []
    while pending or current != depot:
        distances, previous = paths[current]
        target = min(pending, key=lambda x: (distances[x], x)) if pending else depot
        walk = [target]
        while walk[-1] != current:
            walk.append(previous[walk[-1]])
        legs.append({"from": current, "to": target, "distance": distances[target],
                     "path": list(reversed(walk))})
        order.append(target)
        pending.discard(target)
        current = target
    return order, legs


def plan(data):
    depot, graph, parcels, capacity = parse(data)
    times = {}

    def measure(label, function, *args):
        start = perf_counter_ns()
        result = function(*args)
        times[label] = (perf_counter_ns() - start) / 1_000_000
        return result

    ranked = measure("sorting", prioritize, parcels)
    depot_result = measure("reachability", dijkstra, graph, depot)
    reachable = [p for p in ranked if p.stop in depot_result[0]]
    selected, dp = measure("knapsack", pack, reachable, capacity)
    stops = {p.stop for p in selected}
    paths = measure("shortest_paths", shortest_paths, graph, depot, stops, depot_result)
    order, legs = measure("nearest_neighbor", route, depot, stops, paths)
    picked = {p.id for p in selected}
    groups = {stop: [] for stop in order[1:-1]}
    for parcel in selected:
        groups[parcel.stop].append(parcel.id)
    weight = sum(p.weight for p in selected)
    return {
        "ranked": [p.id for p in ranked], "selected": [p.id for p in selected],
        "deferred": {p.id: ("unreachable" if p.stop not in depot_result[0]
                            else "over_capacity" if p.weight > capacity else "not_selected")
                     for p in ranked if p.id not in picked},
        "priority_total": dp[-1], "capacity": capacity, "loaded": weight,
        "unused": capacity - weight, "dp_final_row": dp,
        "delivery_order": order, "deliveries": groups, "legs": legs,
        "distance": sum(leg["distance"] for leg in legs), "runtime_ms": times,
    }


def trace(result):
    lines = [
        "Ranked parcels       " + ", ".join(result["ranked"]),
        "Selected parcels     " + ", ".join(result["selected"]),
        "Deferred             " + (", ".join(f"{p} ({r})" for p, r in result["deferred"].items()) or "none"),
        f"Capacity used        {result['loaded']} / {result['capacity']} weight units",
        f"Unused capacity      {result['unused']} weight units",
        f"Total priority       {result['priority_total']}",
        "Service order        " + " > ".join(result["delivery_order"]),
        f"Round trip distance  {result['distance']} distance units",
        "",
    ]
    lines += [f"{leg['from']} to {leg['to']}   {' > '.join(leg['path'])}   ({leg['distance']})"
              for leg in result["legs"]]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--json", type=Path, help="Write full planning evidence as JSON")
    args = parser.parse_args()
    try:
        result = plan(json.loads(args.dataset.read_text(encoding="utf-8")))
        print(trace(result))
        if args.json:
            args.json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    except (OSError, KeyError, TypeError, ValueError) as exc:
        parser.exit(2, f"Planning failed: {exc}\n")


if __name__ == "__main__":
    main()
