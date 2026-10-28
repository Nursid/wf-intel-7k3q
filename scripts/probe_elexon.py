"""Reproduce the Phase 1 API findings (docs/elexon-api-findings.md) against the live Elexon API.

Usage: backend/.venv/Scripts/python scripts/probe_elexon.py
"""

from collections import Counter

import httpx

BASE = "https://data.elexon.co.uk/bmrs/api/v1/datasets"


def main() -> None:
    with httpx.Client(timeout=60) as c:
        fuel = c.get(
            f"{BASE}/FUELHH/stream",
            params={"settlementDateFrom": "2025-12-31", "settlementDateTo": "2026-02-01", "fuelType": "WIND"},
        ).json()
        wind = c.get(
            f"{BASE}/WINDFOR/stream",
            params={"publishDateTimeFrom": "2025-12-25T00:00:00Z", "publishDateTimeTo": "2026-02-01T00:00:00Z"},
        ).json()

    starts = Counter(r["startTime"] for r in fuel)
    print(f"FUELHH WIND rows={len(fuel)} distinct startTime={len(starts)} duplicates={sum(v > 1 for v in starts.values())}")
    print(f"FUELHH fuelTypes={set(r['fuelType'] for r in fuel)}")

    pubs = sorted({r["publishTime"] for r in wind})
    minutes = Counter(r["startTime"][14:16] for r in wind)
    print(f"WINDFOR rows={len(wind)} publications={len(pubs)} first={pubs[0]} last={pubs[-1]}")
    print(f"WINDFOR startTime minute-of-hour distribution={dict(minutes)}  (00 only => hourly)")
    target = "2026-01-01T12:00:00Z"
    versions = sorted(r["publishTime"] for r in wind if r["startTime"] == target)
    print(f"Versions for {target}: {len(versions)}, earliest={versions[0]}")


if __name__ == "__main__":
    main()
