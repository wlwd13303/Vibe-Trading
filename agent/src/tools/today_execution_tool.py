"""Tool: query today's trade executions from the trading adapter."""

from __future__ import annotations

import json
from typing import Any

from src.agent.tools import BaseTool
from src.trading_adapter.client import get_adapter


class TodayExecutionTool(BaseTool):
    """Query today's filled order executions."""

    name = "today_execution"
    description = (
        "查询今日已成交的订单记录，返回每笔的成交时间、标的名称、代码、方向、"
        "数量、价格、金额和费用。"
        "适合回答'今天成交了哪些''今日成交'等问题。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "detail": {
                "type": "string",
                "description": "可选，'brief' 返回汇总，'detail' 返回逐笔明细",
                "default": "detail",
            },
        },
        "required": [],
    }
    repeatable = True
    is_readonly = True

    def execute(self, **kwargs: Any) -> str:
        try:
            adapter = get_adapter()
            executions = adapter.get_today_executions()

            if not executions:
                return json.dumps(
                    {"status": "ok", "data": [], "count": 0, "message": "今日暂无成交"},
                    ensure_ascii=False,
                )

            buy_total = sum(e.amount for e in executions if e.side in ("buy", "B"))
            sell_total = sum(e.amount for e in executions if e.side in ("sell", "S"))
            total_fee = sum(e.fee for e in executions)

            detail = [
                {
                    "datetime": e.datetime,
                    "symbol": e.symbol,
                    "name": e.name,
                    "side": "买入" if e.side in ("buy", "B") else "卖出",
                    "quantity": e.quantity,
                    "price": round(e.price, 4),
                    "amount": round(e.amount, 2),
                    "fee": round(e.fee, 4),
                }
                for e in executions
            ]

            return json.dumps(
                {
                    "status": "ok",
                    "data": detail,
                    "count": len(executions),
                    "summary": {
                        "buy_amount": round(buy_total, 2),
                        "sell_amount": round(sell_total, 2),
                        "net_amount": round(sell_total - buy_total, 2),
                        "total_fee": round(total_fee, 4),
                    },
                    "message": f"今日成交 {len(executions)} 笔，买入 {buy_total:.2f}，卖出 {sell_total:.2f}",
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
                {"status": "error", "error": f"查询今日成交失败: {exc}"},
                ensure_ascii=False,
            )
