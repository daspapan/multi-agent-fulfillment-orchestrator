"""
Local throughput/load test harness for the Orchestrator.

Answers one question before a staging deploy: how does throughput and
latency change as concurrency increases, and where does config's
max_concurrent_agents number (see config/dev.yaml, staging.yaml,
prod.yaml) actually start to matter?

Each concurrent "worker" gets its OWN Orchestrator instance -- and
therefore its own in-memory StateStore and FulfillmentAgent idempotency
set. StateStore is explicitly documented as not thread-safe, single-writer
only (src/orchestrator/state_store.py). Sharing one Orchestrator across
threads would violate that design and produce misleading numbers. This
also mirrors how the real ECS/Fargate deployment behaves today: each task
has its own in-process state until StateStore moves to a shared DynamoDB
table (see ARCHITECTURE.md / infra/template.yaml) -- a real limitation
worth knowing before staging, not just a test-harness detail: duplicate
detection across concurrent orchestrator instances isn't guaranteed until
that migration happens.

Usage:
    PYTHONPATH=. python scripts/load_test.py
    PYTHONPATH=. python scripts/load_test.py --orders 300 --concurrency 1 3 6 12
    PYTHONPATH=. python scripts/load_test.py --failure-rate 0.15   # stress scenario w/ retries
"""

import argparse
import json
import random
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from src.orchestrator.orchestrator import Orchestrator


class FlakyEnrichmentAgent:
    """Wraps the real EnrichmentAgent, injecting a configurable transient
    failure rate so retry/backoff cost is visible under load too, not just
    the pure happy-path throughput number."""

    name = "enrichment"

    def __init__(self, inner, failure_rate: float):
        self._inner = inner
        self._failure_rate = failure_rate

    def run(self, task):
        if random.random() < self._failure_rate:
            raise ConnectionError("simulated transient failure")
        return self._inner.run(task)


def process_one(order_id: int, failure_rate: float) -> dict:
    orch = Orchestrator()
    if failure_rate > 0:
        orch.agents["enrichment"] = FlakyEnrichmentAgent(orch.agents["enrichment"], failure_rate)

    order = {"order_id": f"LOAD-{order_id}", "customer_id": f"C-{order_id}"}
    start = time.perf_counter()
    result = orch.process_order(order)
    elapsed = time.perf_counter() - start

    # process_order()'s own decision_log only covers the fulfillment task --
    # a retry can also happen one stage earlier, in enrichment. Pull both so
    # the retry count reflects the whole order, not just its last stage.
    base_task_id = f"order-{order['order_id']}"
    enrich_log = orch.state.decision_log(f"{base_task_id}-enrich")
    fulfill_log = orch.state.decision_log(f"{base_task_id}-fulfill")
    retries = sum(1 for entry in enrich_log + fulfill_log if entry.get("status") == "retrying")

    return {
        "order_id": order["order_id"],
        "status": result["status"],
        "latency_s": elapsed,
        "retries": retries,
    }


def run_batch(num_orders: int, concurrency: int, failure_rate: float) -> dict:
    records = []
    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = [pool.submit(process_one, i, failure_rate) for i in range(num_orders)]
        for f in as_completed(futures):
            records.append(f.result())
    wall_time = time.perf_counter() - start

    latencies = sorted(r["latency_s"] for r in records)

    def pct(p):
        if not latencies:
            return 0.0
        idx = min(len(latencies) - 1, int(len(latencies) * p))
        return latencies[idx]

    status_counts: dict[str, int] = {}
    for r in records:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1

    return {
        "concurrency": concurrency,
        "num_orders": num_orders,
        "failure_rate": failure_rate,
        "wall_time_s": wall_time,
        "throughput_orders_per_s": num_orders / wall_time if wall_time > 0 else 0,
        "latency_p50_s": statistics.median(latencies) if latencies else 0,
        "latency_p95_s": pct(0.95),
        "latency_p99_s": pct(0.99),
        "latency_max_s": max(latencies) if latencies else 0,
        "total_retries": sum(r["retries"] for r in records),
        "status_counts": status_counts,
    }


def main():
    parser = argparse.ArgumentParser(description="Local throughput/load test for the Orchestrator")
    parser.add_argument("--orders", type=int, default=200, help="orders per concurrency level")
    parser.add_argument(
        "--concurrency", type=int, nargs="+", default=[1, 3, 6, 12],
        help="concurrency levels to test (defaults match dev/staging/prod max_concurrent_agents, plus 1 as a baseline)",
    )
    parser.add_argument(
        "--failure-rate", type=float, default=0.0,
        help="fraction of enrichment calls that transiently fail, to measure retry/backoff cost under load (0.0-1.0)",
    )
    parser.add_argument("--out", type=str, default="reports/load_test_results.json")
    args = parser.parse_args()

    results = []
    for c in args.concurrency:
        print(f"Running {args.orders} orders at concurrency={c} (failure_rate={args.failure_rate})...")
        r = run_batch(args.orders, c, args.failure_rate)
        results.append(r)
        print(
            f"  throughput={r['throughput_orders_per_s']:.1f} orders/s  "
            f"p50={r['latency_p50_s'] * 1000:.1f}ms  p95={r['latency_p95_s'] * 1000:.1f}ms  "
            f"retries={r['total_retries']}  statuses={r['status_counts']}"
        )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"runs": results}, indent=2))
    print(f"\nWrote results to {out_path}")


if __name__ == "__main__":
    main()
