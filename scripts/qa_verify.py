"""Phase 7 QA: independently recompute selection + metrics from the raw cache and compare with the running API.

Uses only the standard library (no app code, no pandas), so it is a genuine second implementation.
Scope is decision dates in January 2026; delivery day = decision day + offset. January/early February and late
December are GMT, so Europe/London wall time == UTC for every cutoff here.

Usage (backend running on :8000, live cache present):
    backend/.venv/Scripts/python scripts/qa_verify.py
"""

import json
import math
import random
import statistics
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

API = "http://127.0.0.1:8000"  # not "localhost": on Windows it tries IPv6 first and adds ~2 s
CACHE = Path(__file__).resolve().parent.parent / "backend" / ".cache" / "elexon_wind_decisions_2026-01-01_2026-01-31.json"
UTC = timezone.utc
failures: list[str] = []


def get(path: str) -> tuple[dict, float]:
    t0 = time.perf_counter()
    with urllib.request.urlopen(API + path, timeout=60) as r:
        body = json.load(r)
    return body, time.perf_counter() - t0


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{(' - ' + detail) if detail else ''}")
    if not ok:
        failures.append(name)


def parse(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def load():
    raw = json.loads(CACHE.read_text(encoding="utf-8"))
    actual = {parse(t): v for t, v in zip(raw["actuals"]["start_time_utc"], raw["actuals"]["actual_mw"])}
    versions: dict[datetime, list[tuple[datetime, float]]] = {}
    f = raw["forecasts"]
    for s, p, v in zip(f["start_time_utc"], f["publish_time_utc"], f["forecast_mw"]):
        versions.setdefault(parse(s), []).append((parse(p), v))
    return actual, versions


def independent(actual, versions, start_day: int, end_day: int, offset: int, hhmm: str):
    """start_day/end_day are January *decision* days; deliveries are offset days later."""
    h, m = map(int, hhmm.split(":"))
    rows = {}
    t = datetime(2026, 1, start_day, tzinfo=UTC) + timedelta(days=offset)
    end = datetime(2026, 1, end_day, tzinfo=UTC) + timedelta(days=offset + 1)
    while t < end:
        cutoff = datetime(t.year, t.month, t.day, h, m, tzinfo=UTC) - timedelta(days=offset)
        # usable = published by the cutoff AND by the start of the delivery hour
        eligible = [pv for pv in versions.get(t, []) if pv[0] <= cutoff and pv[0] <= t]
        best = max(eligible) if eligible else None
        rows[t] = {"cutoff": cutoff, "publish": best[0] if best else None, "forecast": best[1] if best else None,
                   "actual": actual.get(t), "eligible": len(eligible)}
        t += timedelta(hours=1)
    pairs = [(r["forecast"], r["actual"]) for r in rows.values() if r["forecast"] is not None and r["actual"] is not None]
    err = [f - a for f, a in pairs]
    n = len(err)
    metrics = {
        "matched_count": n,
        "expected_count": len(rows),
        "mae_mw": sum(abs(e) for e in err) / n if n else None,
        "rmse_mw": math.sqrt(sum(e * e for e in err) / n) if n else None,
        "mbe_mw": sum(err) / n if n else None,
        "wape_pct": (sum(abs(e) for e in err) / sum(abs(a) for _, a in pairs) * 100) if n and sum(abs(a) for _, a in pairs) else None,
    }
    return rows, metrics


def close(a, b) -> bool:
    return (a is None and b is None) or (a is not None and b is not None and abs(a - b) < 1e-6)


def main() -> int:
    actual, versions = load()
    print(f"Raw cache: {len(actual)} actual half-hours, {sum(map(len, versions.values()))} forecast rows")

    scenarios = [(1, 31, 1, "09:00"), (1, 31, 0, "07:00"), (1, 31, 0, "12:00"), (1, 31, 2, "09:00"), (1, 7, 1, "16:00"), (15, 15, 3, "09:00")]
    for sd, ed, off, hhmm in scenarios:
        q = f"decision_start_date=2026-01-{sd:02d}&decision_end_date=2026-01-{ed:02d}&cutoff_day_offset={off}&cutoff_time={hhmm}"
        print(f"\nScenario {q}")
        rows, ind = independent(actual, versions, sd, ed, off, hhmm)
        api, _ = get(f"/api/analysis/overview?{q}")
        for k, v in ind.items():
            check(f"overview.{k}", close(v, api["metrics"][k]), f"independent={v} api={api['metrics'][k]}")
        errs = [r["forecast"] - r["actual"] for r in rows.values() if r["forecast"] is not None and r["actual"] is not None]
        dist = api["error_distribution"]
        if len(errs) >= 2:
            qs = statistics.quantiles(errs, n=100, method="inclusive")  # same linear rule as numpy.percentile
            ok = close(qs[9], dist["percentiles_mw"]["p10"]) and close(qs[89], dist["percentiles_mw"]["p90"])
            check("error range P10/P90", ok, f"P10 {qs[9]:.0f} / P90 {qs[89]:.0f} MW")
        else:
            check("error range is null with no matched hours", dist is None)

        # every interval: API selection equals independent selection and never post-cutoff
        items = []
        page = 1
        while True:
            body, _ = get(f"/api/analysis/intervals?{q}&page={page}&page_size=500")
            items += body["items"]
            if page >= body["total_pages"]:
                break
            page += 1
        mism = [
            i["start_time_utc"]
            for i in items
            if (i["publish_time_utc"] and parse(i["publish_time_utc"]) != rows[parse(i["start_time_utc"])]["publish"])
            or (not i["publish_time_utc"] and rows[parse(i["start_time_utc"])]["publish"] is not None)
            or not close(i["forecast_mw"], rows[parse(i["start_time_utc"])]["forecast"])
        ]
        late = [i for i in items if i["publish_time_utc"] and parse(i["publish_time_utc"]) > parse(i["cutoff_utc"])]
        after_start = [i for i in items if i["publish_time_utc"] and parse(i["publish_time_utc"]) > parse(i["start_time_utc"])]
        check("every interval matches independent selection", not mism, f"{len(items)} intervals, {len(mism)} mismatches")
        check("no selected forecast published after its cutoff", not late, f"{len(late)} violations")
        check("no selected forecast published after its hour began", not after_start, f"{len(after_start)} violations")
        first = min(rows)
        check("delivery period follows decision dates", parse(body["period"]["start_utc"]) == first,
              f"decisions from 2026-01-{sd:02d}, deliveries from {first:%Y-%m-%d}")

    print("\nSpot checks via /forecast-history (default cutoff D-1 09:00)")
    rows, _ = independent(actual, versions, 1, 31, 1, "09:00")
    random.seed(7)
    picks = [datetime(2026, 1, 2, 6, tzinfo=UTC), datetime(2026, 2, 1, 18, tzinfo=UTC)] + random.sample(sorted(rows), 3)
    for t in picks:
        body, _ = get(f"/api/analysis/forecast-history?start_time={t:%Y-%m-%dT%H:%M:%SZ}")
        r = rows[t]
        sel = body["selected"]
        ok = (
            sel is not None
            and parse(sel["publish_time_utc"]) == r["publish"]
            and close(sel["forecast_mw"], r["forecast"])
            and close(body["actual_mw"], r["actual"])
            and body["eligible_versions"] == r["eligible"]
        )
        dec = " (decided 1 Jan)" if t.day == 2 and t.month == 1 else " (decided 31 Jan)" if t.month == 2 else ""
        check(f"{t:%d %b %H:%M}Z selected {r['publish']:%d %b %H:%M}Z = {r['forecast']:.0f} MW{dec}", ok,
              f"eligible {r['eligible']}/{body['total_versions']}, actual {r['actual']:.0f} MW")

    print("\nTimings (warm cache)")
    for path in ["/api/analysis/overview", "/api/analysis/timeseries", "/api/analysis/intervals?page_size=500",
                 "/api/analysis/overview?cutoff_time=10:15"]:
        get(path)
        _, dt = get(path)
        check(f"{path} < 2 s", dt < 2, f"{dt * 1000:.0f} ms")

    print(f"\n{'ALL CHECKS PASSED' if not failures else f'{len(failures)} FAILED: {failures}'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
