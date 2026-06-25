"""AssetSplit SDK implementation of TradingAdapter."""

from __future__ import annotations

import logging
from datetime import datetime, date
from typing import Any

from src.trading_adapter import (
    TradingAdapter,
    AccountSummary,
    Position,
    Execution,
)

logger = logging.getLogger(__name__)


class AssetSplitAdapter(TradingAdapter):
    """Adapter over the AssetSplit SDK for the POC phase.

    Replace this class when the production trading API is finalized.
    """

    def __init__(
        self,
        base_url: str = "",
        username: str = "",
        password: str = "",
    ) -> None:
        self._base_url = base_url
        self._username = username
        self._password = password
        self._sdk = None

    def connect(self) -> bool:
        """Initialize the AssetSplit SDK."""
        try:
            from assetsplit_sdk.sync_client import AssetSplitSyncSDK

            token = self._password or ""
            if not self._base_url:
                from dotenv import load_dotenv
                import os
                load_dotenv()
                self._base_url = os.getenv("SDK_BASE_URL", "http://38.76.216.46:27281/")
                self._username = os.getenv("SDK_USERNAME", "trader6978")
                token = os.getenv("SDK_PASSWORD", "503506")

            self._sdk = AssetSplitSyncSDK(
                base_url=self._base_url,
                username=self._username,
                password=token,
            )
            self._sdk.initialize()
            logger.info("AssetSplitAdapter connected to %s", self._base_url)
            return True
        except Exception as exc:
            logger.error("AssetSplitAdapter connect failed: %s", exc)
            return False

    def disconnect(self) -> None:
        if self._sdk is not None:
            try:
                self._sdk.close()
            except Exception:
                pass
            self._sdk = None

    def _ensure_connected(self):
        if self._sdk is None:
            raise RuntimeError("AssetSplitAdapter not connected. Call connect() first.")

    def get_account_summary(self) -> AccountSummary | None:
        self._ensure_connected()
        try:
            # 优先使用 trading.accounts.get_account_balance() (SDK 标准路径)
            result = self._sdk.trading.accounts.get_account_balance()
            if result is None:
                return None

            # 返回可能是对象或 dict，统一提取字段
            def _get(obj, keys: tuple[str, ...], default=0.0) -> float:
                for k in keys:
                    if isinstance(obj, dict):
                        if k in obj:
                            return float(obj[k])
                    else:
                        # 支持中文/英文属性名
                        if hasattr(obj, k):
                            v = getattr(obj, k)
                            return float(v) if v is not None else default
                return default

            # 总资产 / 可用 / 市值 可能用中文或英文命名
            total_asset = _get(result, ("总资产", "total_asset", "total"), 0.0)
            cash_available = _get(result, ("可用", "available_cash", "cash_available", "available", "available_funds"), 0.0)
            market_value = _get(result, ("市值", "market_value", "market"), 0.0)
            frozen_cash = _get(result, ("冻结", "frozen_cash", "frozen"), 0.0)
            unrealized_pnl = _get(result, ("浮动盈亏", "floating_profit_loss", "unrealized_pnl", "profit_loss"), 0.0)

            return AccountSummary(
                total_asset=total_asset,
                cash_available=cash_available,
                market_value=market_value,
                frozen_cash=frozen_cash,
                unrealized_pnl=unrealized_pnl,
            )
        except Exception as exc:
            logger.warning("get_account_summary failed: %s", exc)
            return None

    def get_positions(self) -> list[Position]:
        self._ensure_connected()
        try:
            positions_raw = self._sdk.trading.positions.get_positions_list()
            if positions_raw is None:
                return []
            raw_list = list(positions_raw) if not isinstance(positions_raw, (list, tuple)) else positions_raw

            def _val(item, key: str, default=0) -> float | str | int:
                """Try dict key, .dict()[key], or getattr in order."""
                if isinstance(item, dict):
                    return item.get(key, default)
                if hasattr(item, "dict"):
                    d = item.dict()
                    return d.get(key, default)
                return getattr(item, key, default)

            positions: list[Position] = []
            for item in raw_list:
                qty = float(_val(item, "quantity", 0))
                cost = float(_val(item, "cost_price", 0))
                price = float(_val(item, "current_price", 0))
                positions.append(Position(
                    symbol=str(_val(item, "stock_code", "")),
                    name=str(_val(item, "stock_name", "")),
                    quantity=qty,
                    available_qty=qty,
                    cost_price=cost,
                    market_price=price,
                    market_value=float(_val(item, "market_value", qty * price)),
                    unrealized_pnl=float(_val(item, "profit_loss", (price - cost) * qty)),
                    unrealized_pnl_ratio=float(_val(item, "profit_loss_percentage", ((price - cost) / cost * 100) if cost else 0.0)),
                    holding_days=int(_val(item, "holding_days", 0)),
                ))
            return positions
        except Exception as exc:
            logger.warning("get_positions failed: %s", exc)
            return []

    def _trade_to_execution(self, item) -> Execution:
        """统一把 SDK TradeResponse 转成 Execution 对象。"""
        side = str(getattr(item, "side", "BUY"))
        qty = float(getattr(item, "volume", 0))
        price = float(getattr(item, "price", 0))
        amount = float(getattr(item, "amount", qty * price))
        return Execution(
            datetime=str(getattr(item, "trade_time", "")),
            symbol=str(getattr(item, "stock_code", "")),
            name=str(getattr(item, "stock_name", "")),
            side=side,
            quantity=qty,
            price=price,
            amount=amount,
            fee=float(getattr(item, "fee", 0)),
        )

    def get_today_executions(self) -> list[Execution]:
        self._ensure_connected()
        try:
            result = self._sdk.trading.trades.get_trades_list()
            if result is None:
                return []
            raw_list = result if isinstance(result, (list, tuple)) else []
            return [self._trade_to_execution(item) for item in raw_list]
        except Exception as exc:
            logger.warning("get_today_executions failed: %s", exc)
            return []

    def get_trade_history(
        self,
        start_date: str = "",
        end_date: str = "",
        stock_code: str = "",
        limit: int = 100,
    ) -> list[Execution]:
        """按日期范围查询历史成交记录。

        Args:
            start_date: 开始日期 YYYY-MM-DD，空则从 2000-01-01 起
            end_date: 结束日期 YYYY-MM-DD，空则到当日
            stock_code: 股票代码过滤，空表示全部
            limit: 最多返回条数

        Returns:
            list[Execution]: 成交记录列表
        """
        self._ensure_connected()
        try:
            # SDK 默认只查当日，用户未指定日期时拓宽到全部历史
            effective_start = start_date or "2000-01-01"
            effective_end = end_date or date.today().strftime("%Y-%m-%d")

            result = self._sdk.trading.trades.get_trades_history(
                start_date=effective_start,
                end_date=effective_end,
                stock_code=stock_code or None,
                limit=limit,
            )
            if result is None:
                return []
            raw_list = result if isinstance(result, (list, tuple)) else []
            return [self._trade_to_execution(item) for item in raw_list]
        except Exception as exc:
            logger.warning("get_trade_history failed: %s", exc)
            return []

    def _order_to_dict(self, o) -> dict[str, Any]:
        """统一把 SDK 返回的订单对象或 dict 转成标准化 dict."""
        if isinstance(o, dict):
            return {
                "order_id": str(o.get("order_id", "")),
                "symbol": str(o.get("stock_code", "")),
                "name": str(o.get("stock_name", "")),
                "side": str(o.get("side", "")),
                "quantity": float(o.get("quantity", 0)),
                "price": float(o.get("price", 0)),
                "status": str(o.get("status", "")),
                "status_message": str(o.get("status_message", "")),
                "created_at": str(o.get("created_at", "")),
            }
        return {
            "order_id": str(getattr(o, "order_id", "")),
            "symbol": str(getattr(o, "stock_code", "")),
            "name": str(getattr(o, "stock_name", "")),
            "side": str(getattr(o, "side", "")),
            "quantity": float(getattr(o, "quantity", 0)),
            "price": float(getattr(o, "price", 0)),
            "status": str(getattr(o, "status", "")),
            "status_message": str(getattr(o, "status_message", "")),
            "created_at": str(getattr(o, "created_at", "")),
        }

    def get_open_orders(self) -> list[dict[str, Any]]:
        self._ensure_connected()
        # 优先尝试 SDK 标准路径 trading.orders.get_pending_orders()
        for ns_name, method_name in (
            ("trading.orders", "get_pending_orders"),
            ("trade", "get_orders"),
        ):
            ns = self._sdk
            for part in ns_name.split("."):
                ns = getattr(ns, part, None)
                if ns is None:
                    break
            if ns is None:
                continue
            fn = getattr(ns, method_name, None)
            if fn is None:
                continue
            try:
                if method_name == "get_orders":
                    result = fn(status="open")
                else:
                    result = fn()
                if result is None:
                    return []
                raw_list = result if isinstance(result, (list, tuple)) else []
                return [self._order_to_dict(o) for o in raw_list]
            except Exception as exc:
                logger.debug("get_open_orders via %s.%s failed: %s", ns_name, method_name, exc)
                continue
        logger.warning("get_open_orders: no available SDK method found")
        return []


    def create_order(
        self,
        stock_code: str,
        side: str,
        volume: int,
        price: float | None = None,
        price_type: str = "LIMIT",
    ) -> dict[str, Any]:
        """Place an order via SDK.

        Returns:
            dict with status="ok" / "error" and nested data/error fields.
        """
        self._ensure_connected()
        try:
            order = self._sdk.trading.orders.create_order(
                stock_code=stock_code,
                side=side.upper(),
                volume=volume,
                price=price,
                price_type=price_type.upper(),
            )
            # 兼容不同 SDK 版本的字段命名（order_id / id）
            order_id = getattr(order, "order_id", None) or getattr(order, "id", "")
            return {
                "status": "ok",
                "data": {
                    "order_id": str(order_id),
                    "stock_code": str(getattr(order, "stock_code", "")),
                    "side": str(getattr(order, "side", "")),
                    "quantity": float(getattr(order, "quantity", 0)),
                    "price": float(getattr(order, "price", 0)) if getattr(order, "price", None) else None,
                    "status": str(getattr(order, "status", "")),
                },
            }
        except AttributeError:
            return {"status": "error", "error": "下单接口不可用：SDK 版本不兼容"}
        except Exception as exc:
            logger.warning("create_order failed: %s", exc)
            return {"status": "error", "error": f"下单失败: {exc}"}

    def get_all_orders(self, limit: int = 50) -> list[dict[str, Any]]:
        """查询全部委托（含废单），返回最近 limit 条记录。"""
        self._ensure_connected()
        try:
            result = self._sdk.trading.orders.get_orders_list(limit=limit)
            if result is None:
                return []
            raw_list = result if isinstance(result, (list, tuple)) else []
            return [self._order_to_dict(o) for o in raw_list]
        except Exception as exc:
            logger.warning("get_all_orders failed: %s", exc)
            return []

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        """Cancel an open order. Tries known SDK namespaces."""
        self._ensure_connected()
        # Try several API patterns the SDK may use
        for method_name in ("cancel_order", "cancel"):
            for ns in (self._sdk.trading.orders, self._sdk.trade):
                cancel_fn = getattr(ns, method_name, None)
                if cancel_fn is None:
                    continue
                try:
                    result = cancel_fn(order_id=order_id)
                    return {"status": "ok", "data": {"order_id": order_id, "result": str(result)}}
                except TypeError:
                    # method exists but takes positional-only args
                    try:
                        result = cancel_fn(order_id)
                        return {"status": "ok", "data": {"order_id": order_id, "result": str(result)}}
                    except Exception as exc:
                        logger.debug("cancel via %s.%s failed: %s", type(ns).__name__, method_name, exc)
                        continue
                except Exception as exc:
                    logger.debug("cancel via %s.%s failed: %s", type(ns).__name__, method_name, exc)
                    continue
        return {"status": "error", "error": "撤单失败：未找到可用的撤单接口"}

    def get_realtime_price(
        self, stock_code: str, include_extended: bool = True
    ) -> dict[str, Any]:
        """通过 AssetSplit SDK 查询股票实时价格。

        Args:
            stock_code: 股票代码，如 "600036.SH"
            include_extended: 是否包含昨收/涨跌停价

        Returns:
            dict 包含 status、data（实时价格信息）、source="assetsplit_sdk"
            失败时 status="error"。
        """
        self._ensure_connected()
        try:
            price_data = self._sdk.data.get_stock_price(
                stock_code, include_extended=include_extended
            )
            if not price_data or not price_data.get("success"):
                return {"status": "error", "error": f"未获取到{stock_code}的实时行情"}
            result = {
                "status": "ok",
                "data": {
                    "stock_code": price_data.get("stock_code", stock_code.upper()),
                    "price": float(price_data["price"]),
                    "update_time": str(price_data.get("update_time", "")),
                },
                "source": "assetsplit_sdk",
            }
            if include_extended:
                result["data"]["pre_close"] = (
                    float(price_data["pre_close"]) if price_data.get("pre_close") else None
                )
                result["data"]["limit_up"] = (
                    float(price_data["limit_up"]) if price_data.get("limit_up") else None
                )
                result["data"]["limit_down"] = (
                    float(price_data["limit_down"]) if price_data.get("limit_down") else None
                )
            return result
        except Exception as exc:
            logger.warning("get_realtime_price failed for %s: %s", stock_code, exc)
            return {"status": "error", "error": f"实时行情查询失败: {exc}"}


# Module-level singleton (lazy)
_adapter: AssetSplitAdapter | None = None


def get_adapter() -> AssetSplitAdapter:
    """Return the shared AssetSplitAdapter instance, connecting on first call."""
    global _adapter
    if _adapter is None:
        _adapter = AssetSplitAdapter()
        _adapter.connect()
    return _adapter
