"""Tool: query current positions from the trading adapter."""

from __future__ import annotations

import json
from typing import Any

from src.agent.tools import BaseTool
from src.trading_adapter.client import get_adapter


class PositionQueryTool(BaseTool):
    """Query current portfolio positions from the connected trading system."""

    name = "position_query"
    description = (
        "查询当前账户持仓列表，返回每只标的的代码、名称、持仓数量、可用数量、"
        "成本价、现价、市值、浮动盈亏和盈亏比例。"
        "适合回答'当前持有哪些股票''持仓情况'等问题。"
        "返回空列表表示没有持仓或查询失败。"
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    repeatable = True
    is_readonly = True

    def execute(self, **kwargs: Any) -> str:
        try:
            adapter = get_adapter()
            positions = adapter.get_positions()
            return json.dumps(
                {
                    "status": "ok",
                    "data": [
                        {
                            "symbol": p.symbol,
                            "name": p.name,
                            "quantity": p.quantity,
                            "available_qty": p.available_qty,
                            "cost_price": round(p.cost_price, 4),
                            "market_price": round(p.market_price, 4),
                            "market_value": round(p.market_value, 2),
                            "unrealized_pnl": round(p.unrealized_pnl, 2),
                            "unrealized_pnl_ratio": round(p.unrealized_pnl_ratio, 2),
                        }
                        for p in positions
                    ],
                    "count": len(positions),
                    "message": f"当前持有 {len(positions)} 只标的" if positions else "当前没有持仓数据",
                },
                ensure_ascii=False,
            )
        except RuntimeError as exc:
            return json.dumps(
                {"status": "error", "error": f"未连接到交易接口: {exc}"},
                ensure_ascii=False,
            )
        except Exception as exc:
            return json.dumps(
                {"status": "error", "error": f"查询持仓失败: {exc}"},
                ensure_ascii=False,
            )
