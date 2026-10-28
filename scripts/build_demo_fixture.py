"""Build backend/app/data/demo_fixture.json from the live Elexon cache.

The fixture is a slice (deliveries 1-3 Jan 2026) of real downloaded data, used only when
DATA_MODE=fixture for offline development. It is labelled source="fixture", so the UI shows it as
DEMO FIXTURE and never presents it as a live observation.

Usage (from repo root, after the backend has fetched live data once):
    backend/.venv/Scripts/python scripts/build_demo_fixture.py
"""

import json
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

import pandas as pd  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.services.data_repository import FIXTURE_PATH, DataRepository, _frames_to_payload  # noqa: E402

START, END = pd.Timestamp("2026-01-01", tz="UTC"), pd.Timestamp("2026-01-04", tz="UTC")
PUBLISH_FROM = pd.Timestamp("2025-12-28", tz="UTC")


def main() -> None:
    repo = DataRepository(Settings(data_mode="live", cache_dir=ROOT / "backend" / ".cache"))
    ds = repo.get()
    if ds.meta.source != "elexon-live":
        raise SystemExit("expected live data")
    a = ds.actuals[(ds.actuals.start_time_utc >= START) & (ds.actuals.start_time_utc < END)]
    f = ds.forecasts[
        (ds.forecasts.start_time_utc >= START)
        & (ds.forecasts.start_time_utc < END)
        & (ds.forecasts.publish_time_utc >= PUBLISH_FROM)
        & (ds.forecasts.publish_time_utc < END)
    ]
    meta = replace(
        ds.meta,
        source="fixture",
        fetched_at_utc=ds.meta.fetched_at_utc.astimezone(timezone.utc),
        actual_rows=len(a),
        forecast_rows=len(f),
        forecast_publications=int(f.publish_time_utc.nunique()),
        publish_from_utc=PUBLISH_FROM.isoformat(),
        publish_to_utc=END.isoformat(),
        normalization={},
    )
    payload = _frames_to_payload(a, f, meta)
    payload["notice"] = (
        f"DEMO FIXTURE built {datetime.now(timezone.utc).isoformat()} from an Elexon download; "
        "deliveries 2026-01-01..03 only. Not a live observation."
    )
    FIXTURE_PATH.write_text(json.dumps(payload), encoding="utf-8")
    print(f"wrote {FIXTURE_PATH} ({len(a)} actuals, {len(f)} forecasts)")


if __name__ == "__main__":
    main()
