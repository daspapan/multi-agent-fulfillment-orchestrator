# Local Load Testing (Before a Staging Deploy)

Two scripts, both under `scripts/`, meant to be run locally before pushing
to staging: `load_test.py` generates throughput/latency data, and
`render_dashboard.py` turns one or more of those result files into a
single HTML dashboard you open directly in a browser.

## Why this exists

`config/dev.yaml`, `staging.yaml`, and `prod.yaml` set a
`max_concurrent_agents` value (3 / 6 / 12) but nothing in `src/` actually
enforces or benefits from that number yet -- it's a config placeholder for
whatever concurrency model eventually gets built around the orchestrator.
Before staging, it's worth actually measuring: does throughput improve as
concurrency rises, or does it plateau (or get worse) because of
Python's GIL, logging overhead, or contention elsewhere? This harness
answers that with real numbers instead of assumption.

It also surfaces a real limitation worth knowing before staging: each
concurrent worker in this harness gets its own `Orchestrator()` instance,
because `StateStore` is documented as not thread-safe, single-writer only
(`src/orchestrator/state_store.py`). That means duplicate-order detection
(`FulfillmentAgent._submitted_orders`) only works *within* one instance --
across instances (or across real ECS/Fargate tasks, today) it wouldn't
catch a duplicate. That's expected: it's exactly the gap
`ARCHITECTURE.md`'s roadmap already names ("move `StateStore` to the
DynamoDB-backed version"). This load test doesn't fix that, it just makes
sure you're not surprised by it in staging.

## Step 1: run the baseline (no induced failures)

```bash
PYTHONPATH=. python scripts/load_test.py \
  --orders 300 --concurrency 1 3 6 12 --failure-rate 0.0 \
  --out reports/load_test_baseline.json
```

This measures pure throughput -- how many orders/sec the orchestrator can
push through with everything succeeding on the first try. Since the model
client is stubbed (no real network calls) and no retries happen, this
number reflects overhead only: Pydantic validation, the state store's
dict writes, and Python's own threading/GIL behavior at each concurrency
level. Don't treat it as a real-world ceiling -- a live model call would
dominate the real latency completely. Treat it as a check for regressions
in your own code's overhead as concurrency rises.

## Step 2: run a stress scenario (induced transient failures)

```bash
PYTHONPATH=. python scripts/load_test.py \
  --orders 60 --concurrency 1 3 6 --failure-rate 0.25 \
  --out reports/load_test_stress.json
```

`--failure-rate 0.25` makes 25% of enrichment calls raise a simulated
`ConnectionError`, exercising the orchestrator's real retry/backoff path
(`src/orchestrator/orchestrator.py`'s `dispatch()`) under load. This is
the more realistic scenario for sizing `max_concurrent_agents`: each
retry costs real wall-clock time (`time.sleep(2 ** attempt)`), and this
run shows you how that backoff cost compounds -- or gets parallelized
away -- as concurrency increases. Keep `--orders` modest here (dozens,
not hundreds); every retry is a real sleep, not a mocked one.

## Step 3: build the dashboard

```bash
PYTHONPATH=. python scripts/render_dashboard.py \
  reports/load_test_baseline.json reports/load_test_stress.json \
  --out reports/load_test_dashboard.html
```

Pass as many result files as you want merged into one view -- run
`load_test.py` multiple times at different settings, then point
`render_dashboard.py` at all of them together. It automatically reads
`config/{dev,staging,prod}.yaml` and prints each environment's
`max_concurrent_agents` and model choice as a footnote, so you can eyeball
where each environment's setting lands relative to what you measured.

Open the file it writes:

```bash
open reports/load_test_dashboard.html   # macOS
# or just double-click it in Finder / your file browser
```

It's fully self-contained -- the data is embedded directly in the HTML,
so it opens and works offline (only the Chart.js library itself loads
from a CDN). No server, no build step.

## Reading the results

- **Throughput chart**: if baseline throughput drops noticeably as
  concurrency rises, that's thread contention in your own code (likely
  the GIL, given everything here is CPU-bound Python, not I/O-bound) --
  worth knowing before you assume higher `max_concurrent_agents` in
  staging automatically means more throughput.
- **Latency chart** (stress runs only): p95 latency climbing sharply at
  higher concurrency under failures usually means retries are queuing up
  behind each other rather than overlapping -- a signal to look at
  whether `time.sleep()` inside `dispatch()` should become non-blocking
  before you rely on this at real concurrency.
- **Retries column**: compare retry counts across concurrency levels at
  the same failure rate. Given the small sample sizes recommended above,
  expect some run-to-run noise -- re-run with more orders if a number
  looks surprising before trusting it.

## Before you actually deploy to staging

This is a local, single-machine, stubbed-model signal -- it tells you
about your own code's overhead, not about real Anthropic API latency,
network variance, or DynamoDB behavior once `StateStore` moves off
in-memory. Combine it with (not instead of) the real gaps already named
in `TESTING.md` and `ARCHITECTURE.md`: no load test yet exists against
the actual Anthropic API's rate limits, and `StateStore`'s in-memory
implementation hasn't been tested under real concurrent writers. This
harness is a useful first signal before staging, not a substitute for
those.
