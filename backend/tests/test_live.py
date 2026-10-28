"""Optional smoke test against the real Elexon API. Run with: pytest -m live"""

from datetime import date, datetime, timezone

import pytest

from app.services.elexon_client import ElexonClient
from app.services.normalize import normalize_actuals, normalize_forecasts

pytestmark = pytest.mark.live


def test_live_elexon_january_sample():
    with ElexonClient("https://data.elexon.co.uk/bmrs/api/v1") as c:
        a, _ = normalize_actuals(c.fetch_wind_actuals(date(2026, 1, 15), date(2026, 1, 15)))
        f, _ = normalize_forecasts(
            c.fetch_wind_forecasts(datetime(2026, 1, 14, tzinfo=timezone.utc), datetime(2026, 1, 15, tzinfo=timezone.utc))
        )
    assert len(a) == 48
    assert not f.empty and (f.start_time_utc.dt.minute == 0).all()
