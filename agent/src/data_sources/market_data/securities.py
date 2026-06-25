"""Securities and calendar helpers backed by Tushare."""

from __future__ import annotations

import logging
from typing import Any
from datetime import date, datetime

from src.data_sources.market_data.client import create_pro_api

logger = logging.getLogger(__name__)


def get_trade_calendar(start_date: str, end_date: str) -> list[dict[str, Any]]:
    """Fetch trade calendar for a given date range.

    Args:
        start_date: YYYYMMDD or YYYY-MM-DD.
        end_date: YYYYMMDD or YYYY-MM-DD.

    Returns:
        List of {date, is_open} sorted ascending.
    """
    sd = start_date.replace("-", "")
    ed = end_date.replace("-", "")
    api = create_pro_api()
    try:
        df = api.trade_cal(exchange="SSE", start_date=sd, end_date=ed)
        if df is None or df.empty:
            return []
        result = []
        for _, row in df.iterrows():
            result.append({
                "date": str(row.get("cal_date", "")),
                "is_open": bool(row.get("is_open", 0)),
            })
        return result
    except Exception as exc:
        logger.warning("get_trade_calendar failed: %s", exc)
        return []


def is_trade_day(d: date | None = None) -> bool:
    """Check whether *d* (default today) is a trade day."""
    if d is None:
        d = date.today()
    ds = d.strftime("%Y%m%d")
    cal = get_trade_calendar(ds, ds)
    return bool(cal and cal[0].get("is_open"))


def get_current_price(ts_code: str) -> dict[str, Any] | None:
    """Fetch the latest daily bar for a symbol via ``pro.daily``.

    Args:
        ts_code: e.g. ``000001.SZ``, ``399006.SZ``.

    Returns:
        Dict with keys ``trade_date``, ``open``, ``high``, ``low``, ``close``,
        ``pre_close``, ``change``, ``pct_chg``, ``volume``, ``amount``,
        or ``None`` if unavailable.
    """
    api = create_pro_api()
    try:
        df = api.daily(ts_code=ts_code, start_date="", end_date="")
        if df is None or df.empty:
            return None
        row = df.iloc[0]
        return {
            "trade_date": str(row.get("trade_date", "")),
            "open": float(row.get("open", 0)),
            "high": float(row.get("high", 0)),
            "low": float(row.get("low", 0)),
            "close": float(row.get("close", 0)),
            "pre_close": float(row.get("pre_close", 0)),
            "change": float(row.get("change", 0)),
            "pct_chg": float(row.get("pct_chg", 0)),
            "volume": float(row.get("vol", 0)),
            "amount": float(row.get("amount", 0)),
        }
    except Exception as exc:
        logger.warning("get_current_price failed for %s: %s", ts_code, exc)
        return None
