"""Tushare client initialization and lifecycle."""

from __future__ import annotations

import os
import logging
from typing import Any

logger = logging.getLogger(__name__)

_TOKEN_PLACEHOLDERS = {"", "your-tushare-token"}


def get_tushare_token() -> str:
    """Return the TUSHARE_TOKEN from environment, or empty string."""
    return os.getenv("TUSHARE_TOKEN", "").strip()


def is_tushare_available() -> bool:
    """Check whether Tushare is configured and importable."""
    token = get_tushare_token()
    if not token or token in _TOKEN_PLACEHOLDERS:
        return False
    try:
        import tushare  # noqa: F401
        return True
    except ImportError:
        return False


def create_pro_api():
    """Create a Tushare Pro API instance.

    Returns:
        Tushare ``pro_api`` instance, or ``None`` if unavailable.

    Raises:
        RuntimeError: If ``TUSHARE_TOKEN`` is not set or placeholder.
        ImportError: If tushare package is not installed.
    """
    token = get_tushare_token()
    if not token or token in _TOKEN_PLACEHOLDERS:
        raise RuntimeError(
            "TUSHARE_TOKEN not set. "
            "Add it to agent/.env: TUSHARE_TOKEN=<your-token>"
        )
    import tushare as ts

    return ts.pro_api(token)


def resolve_name_to_code(name: str) -> list[dict[str, Any]]:
    """Resolve a Chinese stock/index name to candidate codes.

    Args:
        name: e.g. "创业板指", "招商银行", "宁德时代"

    Returns:
        List of candidate matches, each with ``ts_code``, ``name``, ``asset_type``.
        Empty list if no match found or data source unavailable.
    """
    api = create_pro_api()
    try:
        df = api.stock_basic(exchange="", list_status="L", fields="ts_code,symbol,name,industry")
        if df is None or df.empty:
            return []

        candidates: list[dict[str, Any]] = []
        name_lower = name.lower()
        for _, row in df.iterrows():
            row_name = str(row.get("name", "")).strip()
            row_code = str(row.get("symbol", "")).strip()
            row_ts_code = str(row.get("ts_code", "")).strip()
            if name_lower in row_name.lower() or name_lower in row_code:
                candidates.append({
                    "ts_code": row_ts_code,
                    "symbol": row_code,
                    "name": row_name,
                    "industry": str(row.get("industry", "")).strip(),
                    "type": "stock",
                })

        # Also try index_basic for index resolution
        try:
            idx_df = api.index_basic(market="" if not candidates else "dummy")
            if idx_df is not None and not idx_df.empty:
                for _, row in idx_df.iterrows():
                    row_name = str(row.get("name", "")).strip()
                    row_ts_code = str(row.get("ts_code", "")).strip()
                    if name_lower in row_name.lower() or name_lower in row_ts_code.split(".")[0]:
                        candidates.append({
                            "ts_code": row_ts_code,
                            "symbol": row_ts_code,
                            "name": row_name,
                            "type": "index",
                            "market": str(row.get("market", "")).strip(),
                        })
        except Exception:
            pass

        return candidates
    except Exception as exc:
        logger.warning("resolve_name_to_code failed for %r: %s", name, exc)
        return []
