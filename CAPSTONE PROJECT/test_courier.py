import copy
from itertools import combinations
import json
from pathlib import Path
from random import Random
import unittest

from benchmark import workload
from courier import dijkstra, pack, parse, plan, prioritize


class CourierTest(unittest.TestCase):
    def setUp(self):
        self.demo = json.loads((Path(__file__).parent / "data/demo.json").read_text())

    def test_demo(self):
        result = plan(self.demo)
        self.assertEqual(result["selected"], ["P02", "P03", "P04"])
        self.assertEqual(result["priority_total"], 30)
        self.assertEqual(result["loaded"], 12)
        self.assertEqual(result["delivery_order"], ["Depot", "B", "C", "D", "Depot"])
        self.assertEqual(result["distance"], 18)
        self.assertEqual(result["deferred"]["P06"], "unreachable")
        self.assertEqual(result["deferred"]["P07"], "over_capacity")

    def test_exhaustive_packing(self):
        rng = Random(168)
        for seed in range(30):
            data = workload(10, seed)
            data["parcels"] = data["parcels"][:9]
            _, _, parcels, _ = parse(data)
            capacity = rng.randint(1, 45)
            picked, row = pack(prioritize(parcels), capacity)
            feasible = [sum(p.priority for p in subset)
                        for count in range(10) for subset in combinations(parcels, count)
                        if sum(p.weight for p in subset) <= capacity]
            self.assertEqual(row[-1], max(feasible))
            self.assertEqual(sum(p.priority for p in picked), max(feasible))
            self.assertLessEqual(sum(p.weight for p in picked), capacity)
            self.assertEqual(len(picked), len({p.id for p in picked}))

    def test_distances_against_floyd_warshall(self):
        for seed in range(8):
            _, graph, _, _ = parse(workload(12, seed))
            distances = {(u, v): 0 if u == v else graph[u].get(v, float("inf"))
                         for u in graph for v in graph}
            for w in graph:
                for u in graph:
                    for v in graph:
                        distances[u, v] = min(distances[u, v], distances[u, w] + distances[w, v])
            for u in graph:
                actual, _ = dijkstra(graph, u)
                self.assertEqual(actual, {v: distances[u, v] for v in graph})

    def test_route_invariants(self):
        for seed in range(10):
            data = workload(24, seed)
            depot, graph, parcels, capacity = parse(data)
            result = plan(data)
            self.assertLessEqual(result["loaded"], capacity)
            self.assertEqual(result["delivery_order"][0], depot)
            self.assertEqual(result["delivery_order"][-1], depot)
            self.assertEqual(len(set(result["delivery_order"][1:-1])), len(result["legs"]) - 1)
            self.assertEqual({p for ps in result["deliveries"].values() for p in ps},
                             set(result["selected"]))
            self.assertEqual(set(result["selected"]) | result["deferred"].keys(),
                             {p.id for p in parcels})
            self.assertEqual(sum(leg["distance"] for leg in result["legs"]), result["distance"])
            for leg in result["legs"]:
                path = leg["path"]
                self.assertEqual((path[0], path[-1]), (leg["from"], leg["to"]))
                self.assertEqual(leg["distance"], sum(graph[u][v] for u, v in zip(path, path[1:])))

    def test_empty_and_unreachable_only(self):
        for parcels in [[], [self.demo["parcels"][5]]]:
            with self.subTest(parcels=parcels):
                self.demo["parcels"] = parcels
                result = plan(self.demo)
                self.assertEqual(result["delivery_order"], ["Depot"])
                self.assertEqual(result["legs"], [])
                self.assertEqual(result["distance"], 0)

    def test_equal_priority_tie(self):
        self.demo["capacity"] = 2
        self.demo["parcels"] = [
            dict(id="A", stop="A", priority=3, weight=2, deadline="2026-11-27"),
            dict(id="B", stop="C", priority=3, weight=2, deadline="2026-11-25"),
        ]
        self.assertEqual(plan(self.demo)["selected"], ["B"])

    def test_malformed_input(self):
        negative = copy.deepcopy(self.demo)
        negative["roads"][0][2] = -2
        duplicate = copy.deepcopy(self.demo)
        duplicate["parcels"].append(duplicate["parcels"][0])
        for data in [negative, duplicate, {**self.demo, "capacity": True}]:
            with self.assertRaises(ValueError):
                plan(data)


if __name__ == "__main__":
    unittest.main()
