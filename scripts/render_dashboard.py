"""
Builds a self-contained, offline-friendly HTML dashboard from one or more
scripts/load_test.py result files.

Run load_test.py first (as many times, at whatever concurrency and
failure-rate combinations you want to compare -- see LOAD_TESTING.md),
then point this script at all the resulting JSON files. Each run already
carries its own concurrency and failure_rate, so this just merges and
renders them; there's no separate "baseline vs stress" concept hardcoded
here, that split happens automatically in the chart based on failure_rate.

Usage:
    PYTHONPATH=. python scripts/load_test.py --orders 300 --concurrency 1 3 6 12 \
        --failure-rate 0.0 --out reports/load_test_baseline.json
    PYTHONPATH=. python scripts/load_test.py --orders 40 --concurrency 1 3 6 \
        --failure-rate 0.25 --out reports/load_test_stress.json
    PYTHONPATH=. python scripts/render_dashboard.py \
        reports/load_test_baseline.json reports/load_test_stress.json \
        --out reports/load_test_dashboard.html

Then open reports/load_test_dashboard.html directly in a browser -- no
server needed, the data is embedded in the file.
"""

import argparse
import json
from pathlib import Path

CONFIG_DIR = Path("config")


def load_config_summary() -> dict:
    """Best-effort read of config/{dev,staging,prod}.yaml so the dashboard
    can mark where each environment's max_concurrent_agents sits on the
    chart. Falls back to an empty dict if pyyaml or the files aren't
    available -- the dashboard still renders fine without this."""
    summary = {}
    try:
        import yaml
    except ImportError:
        return summary
    if not CONFIG_DIR.exists():
        return summary
    for name in ("dev", "staging", "prod"):
        path = CONFIG_DIR / f"{name}.yaml"
        if path.exists():
            try:
                summary[name] = yaml.safe_load(path.read_text())
            except Exception:  # noqa: BLE001 - dashboard rendering shouldn't die over a bad config file
                pass
    return summary


def merge_runs(paths: list[str]) -> list[dict]:
    runs = []
    for p in paths:
        data = json.loads(Path(p).read_text())
        runs.extend(data.get("runs", []))
    return runs


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Orchestrator load test dashboard</title>
<style>
  :root {
    --bg: #fafaf9; --surface: #ffffff; --border: #e3e2dd;
    --text: #16150f; --text-secondary: #5f5e58; --text-muted: #8b8a83;
    --blue: #2a78d6; --orange: #eb6834;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #171715; --surface: #201f1c; --border: #34332e;
      --text: #f2f1ec; --text-secondary: #c3c2b7; --text-muted: #8b8a83;
    }
  }
  body { font-family: -apple-system, "Segoe UI", sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 2rem; }
  h1 { font-size: 20px; font-weight: 500; margin: 0 0 4px; }
  p.sub { color: var(--text-secondary); font-size: 14px; margin: 0 0 1.5rem; }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-bottom: 2rem; }
  .card { background: var(--surface); border: 0.5px solid var(--border); border-radius: 10px; padding: 1rem; }
  .card .label { font-size: 12px; color: var(--text-secondary); margin: 0 0 4px; }
  .card .value { font-size: 22px; font-weight: 500; margin: 0; }
  .legend { display: flex; flex-wrap: wrap; gap: 16px; font-size: 12px; color: var(--text-secondary); margin-bottom: 8px; }
  .swatch { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; vertical-align: -1px; }
  .chart-wrap { position: relative; width: 100%; height: 280px; margin-bottom: 2rem; background: var(--surface); border: 0.5px solid var(--border); border-radius: 10px; padding: 1rem 1rem 0.5rem; box-sizing: border-box; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; background: var(--surface); border: 0.5px solid var(--border); border-radius: 10px; overflow: hidden; }
  th, td { text-align: left; padding: 8px 12px; border-bottom: 0.5px solid var(--border); }
  th { color: var(--text-secondary); font-weight: 500; }
  tr:last-child td { border-bottom: none; }
  .note { font-size: 12px; color: var(--text-muted); margin-top: 1rem; }
  code { font-family: ui-monospace, monospace; background: var(--border); padding: 1px 5px; border-radius: 4px; font-size: 12px; }
</style>
</head>
<body>
  <h1>Orchestrator load test dashboard</h1>
  <p class="sub">Generated from __NUM_RUNS__ run(s). Re-run <code>scripts/load_test.py</code> then this script to refresh.</p>

  <div class="cards" id="cards"></div>

  <div class="legend">
    <span><span class="swatch" style="background: var(--blue, #2a78d6);"></span>0% induced failures</span>
    <span><span class="swatch" style="background: var(--orange, #eb6834);"></span>&gt;0% induced failures</span>
  </div>
  <div class="chart-wrap"><canvas id="throughputChart" role="img" aria-label="Orders per second by concurrency level, split by failure rate"></canvas></div>
  <div class="chart-wrap"><canvas id="latencyChart" role="img" aria-label="p50 and p95 latency in seconds by concurrency level, for runs with induced failures"></canvas></div>

  <table id="table"></table>
  <p class="note" id="config-note"></p>

<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.js"></script>
<script>
const RUNS = __RUNS_JSON__;
const CONFIG = __CONFIG_JSON__;

const byConcurrency = {};
RUNS.forEach(r => {
  const key = r.concurrency;
  if (!byConcurrency[key]) byConcurrency[key] = [];
  byConcurrency[key].push(r);
});
const concurrencies = Object.keys(byConcurrency).map(Number).sort((a, b) => a - b);

const baseline = concurrencies.map(c => {
  const runs = byConcurrency[c].filter(r => r.failure_rate === 0);
  return runs.length ? runs[runs.length - 1].throughput_orders_per_s : null;
});
const stressThroughput = concurrencies.map(c => {
  const runs = byConcurrency[c].filter(r => r.failure_rate > 0);
  return runs.length ? runs[runs.length - 1].throughput_orders_per_s : null;
});
const stressP50 = concurrencies.map(c => {
  const runs = byConcurrency[c].filter(r => r.failure_rate > 0);
  return runs.length ? runs[runs.length - 1].latency_p50_s : null;
});
const stressP95 = concurrencies.map(c => {
  const runs = byConcurrency[c].filter(r => r.failure_rate > 0);
  return runs.length ? runs[runs.length - 1].latency_p95_s : null;
});

const bestBaseline = Math.max(...baseline.filter(v => v !== null), 0);
const worstStressP95 = Math.max(...stressP95.filter(v => v !== null), 0);
const totalRetries = RUNS.reduce((sum, r) => sum + (r.total_retries || 0), 0);
const totalOrders = RUNS.reduce((sum, r) => sum + (r.num_orders || 0), 0);

document.getElementById('cards').innerHTML = `
  <div class="card"><p class="label">Peak baseline throughput</p><p class="value">${bestBaseline.toLocaleString(undefined, {maximumFractionDigits: 0})}/s</p></div>
  <div class="card"><p class="label">Worst p95 latency (failures on)</p><p class="value">${worstStressP95.toFixed(2)}s</p></div>
  <div class="card"><p class="label">Total retries observed</p><p class="value">${totalRetries}</p></div>
  <div class="card"><p class="label">Total orders processed</p><p class="value">${totalOrders}</p></div>
`;

new Chart(document.getElementById('throughputChart'), {
  type: 'bar',
  data: {
    labels: concurrencies.map(c => 'c=' + c),
    datasets: [
      { label: '0% failures', data: baseline, backgroundColor: '#2a78d6', borderRadius: 4 },
      { label: '>0% failures', data: stressThroughput, backgroundColor: '#eb6834', borderRadius: 4 }
    ]
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false }, title: { display: true, text: 'Throughput (orders/s, log scale)' } },
    scales: { y: { type: 'logarithmic' } }
  }
});

new Chart(document.getElementById('latencyChart'), {
  type: 'bar',
  data: {
    labels: concurrencies.map(c => 'c=' + c),
    datasets: [
      { label: 'p50', data: stressP50, backgroundColor: '#2a78d6', borderRadius: 4 },
      { label: 'p95', data: stressP95, backgroundColor: '#eb6834', borderRadius: 4 }
    ]
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false }, title: { display: true, text: 'Latency under induced failures (seconds)' } }
  }
});

const rows = RUNS.map(r => `
  <tr>
    <td>${r.concurrency}</td>
    <td>${r.num_orders}</td>
    <td>${(r.failure_rate * 100).toFixed(0)}%</td>
    <td>${r.throughput_orders_per_s.toFixed(1)}</td>
    <td>${(r.latency_p50_s * 1000).toFixed(1)}</td>
    <td>${(r.latency_p95_s * 1000).toFixed(1)}</td>
    <td>${r.total_retries}</td>
    <td>${JSON.stringify(r.status_counts)}</td>
  </tr>
`).join('');
document.getElementById('table').innerHTML = `
  <thead><tr>
    <th>concurrency</th><th>orders</th><th>failure rate</th><th>throughput/s</th>
    <th>p50 ms</th><th>p95 ms</th><th>retries</th><th>statuses</th>
  </tr></thead>
  <tbody>${rows}</tbody>
`;

const configLines = Object.entries(CONFIG).map(([env, cfg]) =>
  `${env}: max_concurrent_agents=${cfg.max_concurrent_agents}, model=${cfg.model}`
).join(' · ');
document.getElementById('config-note').textContent = configLines
  ? 'Config reference -- ' + configLines
  : '';
</script>
</body>
</html>
"""


def render(runs: list[dict], config: dict, out_path: Path) -> None:
    html = (
        HTML_TEMPLATE
        .replace("__NUM_RUNS__", str(len(runs)))
        .replace("__RUNS_JSON__", json.dumps(runs))
        .replace("__CONFIG_JSON__", json.dumps(config))
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)


def main():
    parser = argparse.ArgumentParser(description="Render an HTML dashboard from load_test.py result files")
    parser.add_argument("inputs", nargs="+", help="one or more JSON files written by load_test.py")
    parser.add_argument("--out", type=str, default="reports/load_test_dashboard.html")
    args = parser.parse_args()

    runs = merge_runs(args.inputs)
    config = load_config_summary()
    out_path = Path(args.out)
    render(runs, config, out_path)
    print(f"Wrote dashboard to {out_path} ({len(runs)} runs merged from {len(args.inputs)} file(s))")


if __name__ == "__main__":
    main()
