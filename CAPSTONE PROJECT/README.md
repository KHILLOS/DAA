# Mini-Courier Planner

Design & Analysis of Algorithms (ETCCDA302) · K.R. Mangalam University

Plan one courier trip from a JSON road network and parcel manifest. The planner ranks parcels by deadline, chooses an exact maximum-priority payload within the weight limit, computes shortest road paths, and builds a nearest-neighbor tour that returns to the depot.

## Run the project

Requires Python 3.10 or newer. The planner, benchmark and tests use only the standard library.

```sh
python3 courier.py data/demo.json --json evidence/demo_plan.json
python3 courier.py data/synthetic_128.json
python3 -m unittest -v
python3 benchmark.py --runs 9
```

For an unseen dataset, copy the demo schema to a new JSON file and pass its path as the first argument. The output JSON is optional and includes per-stage runtimes, the full final DP row, deferred reasons, stop manifests, service order, expanded road paths and total distance.

## Input contract

| Field | Meaning |
| --- | --- |
| depot | Name of a node used for departure and return |
| capacity | Positive integer weight limit in a consistent unit |
| nodes | Unique nonempty string identifiers |
| roads | Triples [node A, node B, positive integer distance], undirected |
| parcels | Objects with unique string id, customer stop, positive integer weight and priority, and ISO date deadline |

Roads may include transit nodes with no parcels. Multiple parcels at one stop share a scheduled delivery. The model assumes one vehicle, one trip and static road weights. A deadline ranks the manifest and resolves some equal-priority choices through input order. The model does not enforce time windows. Packing is subset selection by weight, without geometric loading constraints.

## Algorithms

1. Sort by ascending deadline, descending priority, then ascending identifier, using Python's adaptive stable sort.
2. Run heap-based Dijkstra from the depot and exclude unreachable parcels from loading.
3. Optimize the total loaded priority with 0/1 knapsack. Descending capacity updates prevent reusing an item. Decision rows support reconstruction. Strict improvement resolves ties consistently.
4. Compute point-to-point distances from selected stops using Dijkstra. For the nearest-neighbor tour, repeatedly choose the closest pending service stop by road distance and return to the depot. A shortest road path can pass through a customer before its scheduled service.

For P reachable parcels, integer capacity C, V nodes, E roads and K delivery stops, sorting costs O(P log P) for the ranked input size (including unreachable records). Knapsack takes O(PC) time and O(PC) decision bytes plus O(C) score entries. Dijkstra scans adjacency lists and uses a lazy binary heap, with a per-run bound O((V+E) log(V+E)) on this simple graph. Up to K+1 runs are used. Nearest-neighbor selection is O(K²), plus the cost of expanding the actual paths.

## Expected demonstration

The demo chooses P02, P03 and P04, using 12/12 weight units for a score of 30. The service sequence Depot → B → C → D → Depot has a distance of 18. The first leg uses Depot → A → B for distance 6. P06 is unreachable and P07 is too heavy for any trip with the demo capacity.

## Evidence

| File | Contents |
| --- | --- |
| data/demo.json | Hand-checkable manifest, including a disconnected stop |
| data/synthetic_*.json | Four deterministic workloads with 48 to 512 parcels |
| evidence/demo_trace.txt | Actual CLI output |
| evidence/demo_plan.json | DP values and expanded travel paths |
| evidence/runtime.csv | Five stage medians from nine runs per workload |
| evidence/runtime.png | Log-scale runtime comparison |
| evidence/demo_output.png | Rendered capture of the recorded terminal output |
| evidence/tests.txt | Actual results for seven automated tests |
| Capstone Report.pdf | 25-page report and demonstration guide |

Benchmarks are machine-dependent. Data generation, parsing, file I/O and console printing are outside the stage timings. The report explains the guarantees, limits and performance results.
