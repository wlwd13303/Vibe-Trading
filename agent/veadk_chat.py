"""
VeADK Agent 对话入口 — Phase 1 POC：智能账号管理

启动方式：
    cd agent && c:\developer\Vibe-Trading\.venv\Scripts\python veadk_chat.py

支持的自然语言问句：
    - "我当前持有哪些股票？"
    - "我在宁德时代上投了多少钱？成本多少？持仓数量多少？"
    - "今天成交了哪些？"
    - "帮我查一下招商银行的代码"
    - "创业板指的代码是什么？"
    - "退出" / "exit"
"""

from __future__ import annotations

import os
import sys

# ── 路径与 .env ──────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path)

# VeADK 使用 MODEL_AGENT_API_KEY 环境变量，从 DEEPSEEK_API_KEY 映射
if not os.getenv("MODEL_AGENT_API_KEY") and os.getenv("DEEPSEEK_API_KEY"):
    os.environ["MODEL_AGENT_API_KEY"] = os.environ["DEEPSEEK_API_KEY"]

# 屏蔽 LiteLLM 内部日志 worker 超时错误（不影响功能）
os.environ["LITELLM_LOG"] = "ERROR"
os.environ["VEADK_LOG_LEVEL"] = "WARNING"

import asyncio
import json
from datetime import date
from typing import Any

from veadk import Agent, Runner

# ── 工具函数：VeADK Tool = 带类型标注和 docstring 的函数 ─────


def security_resolve(name: str) -> dict[str, Any]:
    """解析A股股票或指数名称到标准代码。

    当用户提到股票名称（如"招商银行""宁德时代""创业板指"）时调用此函数。
    如果返回多个候选，必须询问用户确认。

    Args:
        name: 股票或指数名称，如 "招商银行"、"宁德时代"、"创业板指"、"平安"

    Returns:
        dict: 包含 status、data（候选列表）、count、multiple（是否多候选）
    """
    from src.data_sources.market_data.client import resolve_name_to_code

    if not name or not name.strip():
        return {"status": "error", "error": "名称不能为空"}

    candidates = resolve_name_to_code(name.strip())
    if not candidates:
        return {
            "status": "ok",
            "data": [],
            "count": 0,
            "multiple": False,
            "message": f"未找到匹配{name}的标的",
        }
    return {
        "status": "ok",
        "data": candidates,
        "count": len(candidates),
        "multiple": len(candidates) > 1,
        "message": f"找到 {len(candidates)} 个匹配" if len(candidates) > 1 else "找到唯一匹配",
    }


def get_positions() -> dict[str, Any]:
    """查询当前账户持仓列表。

    当用户问"当前持仓""持有股票""有哪些股票"时调用此函数。
    返回每只标的的代码、名称、数量、成本价、现价、浮动盈亏和盈亏比例。

    Returns:
        dict: 包含 status、data（持仓列表）、count
    """
    from src.trading_adapter.client import get_adapter

    try:
        adapter = get_adapter()
        positions = adapter.get_positions()
        return {
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
            "message": f"当前持有 {len(positions)} 只标的" if positions else "当前没有持仓",
        }
    except RuntimeError as e:
        return {"status": "error", "error": f"未连接到交易接口: {e}"}
    except Exception as e:
        return {"status": "error", "error": f"查询持仓失败: {e}"}


def get_position_detail(symbol_or_name: str) -> dict[str, Any]:
    """查询某只标的的持仓详情，包括投入金额、成本价、数量和盈亏。

    当用户问"我在XX上投了多少钱""XX的成本""XX的持仓"时调用。
    需要先调用 security_resolve 确认代码。

    Args:
        symbol_or_name: 标的名称或代码，如 "宁德时代" 或 "300750.SZ"

    Returns:
        dict: 持仓详情或错误信息
    """
    from src.trading_adapter.client import get_adapter

    try:
        adapter = get_adapter()
        positions = adapter.get_positions()

        # 先按代码匹配，再按名称匹配
        target = symbol_or_name.strip().upper()
        for p in positions:
            if p.symbol.upper() == target or target in p.symbol.upper():
                return _format_position_detail(p)

        # 名称匹配（大小写不敏感）
        for p in positions:
            if symbol_or_name.strip().lower() in p.name.lower():
                return _format_position_detail(p)

        return {
            "status": "ok",
            "data": None,
            "message": f"未找到{symbol_or_name}的持仓记录。请先确认该标的代码。",
        }
    except RuntimeError as e:
        return {"status": "error", "error": f"未连接到交易接口: {e}"}
    except Exception as e:
        return {"status": "error", "error": f"查询失败: {e}"}


def _format_position_detail(p) -> dict[str, Any]:
    total_cost = round(p.quantity * p.cost_price, 2)
    return {
        "status": "ok",
        "data": {
            "symbol": p.symbol,
            "name": p.name,
            "quantity": p.quantity,
            "available_qty": p.available_qty,
            "cost_price": round(p.cost_price, 4),
            "cost_amount": total_cost,
            "market_price": round(p.market_price, 4),
            "market_value": round(p.market_value, 2),
            "unrealized_pnl": round(p.unrealized_pnl, 2),
            "unrealized_pnl_ratio": round(p.unrealized_pnl_ratio, 2),
        },
        "message": (
            f"你持有{p.name} {int(p.quantity)} 股，"
            f"成本价 {p.cost_price:.2f} 元，"
            f"成本金额 {total_cost:.2f} 元。"
        ),
        "calculation_basis": "成本金额 = 持仓数量 × 持仓成本价，不含历史已卖出盈亏",
    }


def get_today_executions() -> dict[str, Any]:
    """查询今日成交记录。

    当用户问"今天成交了哪些""今日成交"时调用。
    返回每笔成交的时间、标的、方向、数量、价格、金额和费用汇总。

    Returns:
        dict: 包含 status、data（成交明细）、summary（汇总）
    """
    from src.trading_adapter.client import get_adapter

    try:
        adapter = get_adapter()
        executions = adapter.get_today_executions()
        if not executions:
            return {"status": "ok", "data": [], "count": 0, "message": "今日暂无成交"}

        buy_total = sum(e.amount for e in executions if e.side.lower() in ("buy", "b"))
        sell_total = sum(e.amount for e in executions if e.side.lower() in ("sell", "s"))

        return {
            "status": "ok",
            "data": [
                {
                    "time": e.datetime,
                    "symbol": e.symbol,
                    "name": e.name,
                    "side": "买入" if e.side.lower() in ("buy", "b") else "卖出",
                    "quantity": e.quantity,
                    "price": round(e.price, 4),
                    "amount": round(e.amount, 2),
                    "fee": round(e.fee, 4),
                }
                for e in executions
            ],
            "count": len(executions),
            "summary": {
                "buy_amount": round(buy_total, 2),
                "sell_amount": round(sell_total, 2),
                "total_fee": round(sum(e.fee for e in executions), 4),
            },
            "message": f"今日成交 {len(executions)} 笔，买入 {buy_total:.2f} 元，卖出 {sell_total:.2f} 元",
        }
    except RuntimeError as e:
        return {"status": "error", "error": f"未连接到交易接口: {e}"}
    except Exception as e:
        return {"status": "error", "error": f"查询今日成交失败: {e}"}


def get_current_price(ts_code: str) -> dict[str, Any]:
    """查询某只股票或指数的当前行情价格。

    当用户问"XX股价""XX多少钱""XX行情"时调用。
    需要先通过 security_resolve 确认代码。

    Args:
        ts_code: 标准代码，如 "600036.SH"、"300750.SZ"、"399006.SZ"

    Returns:
        dict: 最新行情数据，含收盘价、涨跌幅、成交量等
    """
    from src.data_sources.market_data.securities import get_current_price as _get_price

    result = _get_price(ts_code.strip().upper())
    if result is None:
        return {"status": "error", "error": f"未找到{ts_code}的行情数据"}
    return {"status": "ok", "data": result}


def get_account_summary() -> dict[str, Any]:
    """查询账户资产总览。

    当用户问"账户资产""我有多少钱""可用资金"时调用。
    返回总资产、可用资金、持仓市值、冻结资金和浮动盈亏。

    Returns:
        dict: 账户资产摘要
    """
    from src.trading_adapter.client import get_adapter

    try:
        adapter = get_adapter()
        summary = adapter.get_account_summary()
        if summary is None:
            return {"status": "error", "error": "无法获取账户资产信息"}
        return {
            "status": "ok",
            "data": {
                "total_asset": summary.total_asset,
                "cash_available": summary.cash_available,
                "market_value": summary.market_value,
                "frozen_cash": summary.frozen_cash,
                "unrealized_pnl": summary.unrealized_pnl,
            },
            "message": (
                f"总资产 {summary.total_asset:.2f} 元，"
                f"可用资金 {summary.cash_available:.2f} 元，"
                f"持仓市值 {summary.market_value:.2f} 元"
            ),
        }
    except RuntimeError as e:
        return {"status": "error", "error": f"未连接到交易接口: {e}"}
    except Exception as e:
        return {"status": "error", "error": f"查询账户资产失败: {e}"}


def get_open_orders() -> dict[str, Any]:
    """查询当前未成交的挂单列表。

    当用户问"挂单""未成交""我的委托"时调用。
    返回每笔挂单的代码、名称、方向、数量、价格、状态。

    Returns:
        dict: 未成交委托列表
    """
    from src.trading_adapter.client import get_adapter

    try:
        adapter = get_adapter()
        orders = adapter.get_open_orders()
        if not orders:
            return {"status": "ok", "data": [], "count": 0, "message": "当前没有未成交的挂单"}

        return {
            "status": "ok",
            "data": [
                {
                    "order_id": o["order_id"],
                    "symbol": o["symbol"],
                    "name": o["name"],
                    "side": "买入" if o["side"].upper() in ("BUY", "B") else "卖出",
                    "quantity": o["quantity"],
                    "price": o["price"],
                    "status": o["status"],
                    "created_at": o["created_at"],
                }
                for o in orders
            ],
            "count": len(orders),
            "message": f"当前有 {len(orders)} 笔未成交委托",
        }
    except RuntimeError as e:
        return {"status": "error", "error": f"未连接到交易接口: {e}"}
    except Exception as e:
        return {"status": "error", "error": f"查询挂单失败: {e}"}


def place_order(
    stock_code: str,
    side: str,
    volume: int,
    *,
    price: float | None = None,
    price_type: str = "LIMIT",
) -> dict[str, Any]:
    """**下单操作！** 买入或卖出股票。

    重要：
    - 调用此函数前，必须先通过 security_resolve 确认 stock_code。
    - 调用此函数前，必须向用户展示下单详情（标的、方向、数量、价格类型、价格），
      获得用户明确确认后才能调用。
    - BUY 买入时建议先查可用资金（get_account_summary）是否充足。
    - SELL 卖出时建议先查持仓可用数量（get_positions）。
    - price_type 为 'MARKET' 时不需要 price 参数。

    Args:
        stock_code: 标准代码，如 "600036.SH"、"300750.SZ"
        side: "BUY" 买入 或 "SELL" 卖出
        volume: 数量（股）
        price: 限价（price_type='LIMIT'时必须）
        price_type: "LIMIT"（限价单）或 "MARKET"（市价单）

    Returns:
        dict: 下单结果，含订单 ID、状态等
    """
    from src.trading_adapter.client import get_adapter

    try:
        adapter = get_adapter()
        kwargs = {
            "stock_code": stock_code,
            "side": side.upper(),
            "volume": volume,
            "price_type": price_type.upper(),
        }
        if price_type.upper() == "LIMIT":
            if price is None or price <= 0:
                return {"status": "error", "error": "限价单必须指定有效价格"}
            kwargs["price"] = price

        result = adapter.create_order(**kwargs)
        return result
    except RuntimeError as e:
        return {"status": "error", "error": f"未连接到交易接口: {e}"}
    except Exception as e:
        return {"status": "error", "error": f"下单失败: {e}"}


def cancel_order(order_id: str) -> dict[str, Any]:
    """**撤单操作！** 取消一笔未成交的挂单。

    重要：
    - 调用此函数前，必须获取用户明确确认才能执行。
    - 调用前可以通过 get_open_orders 确认挂单存在。

    Args:
        order_id: 要取消的订单 ID

    Returns:
        dict: 撤单结果
    """
    from src.trading_adapter.client import get_adapter

    try:
        adapter = get_adapter()
        result = adapter.cancel_order(order_id)
        return result
    except RuntimeError as e:
        return {"status": "error", "error": f"未连接到交易接口: {e}"}
    except Exception as e:
        return {"status": "error", "error": f"撤单失败: {e}"}


TOOLS = [
    security_resolve,
    get_positions,
    get_position_detail,
    get_today_executions,
    get_current_price,
    get_account_summary,
    get_open_orders,
    place_order,
    cancel_order,
]

# ── Agent 指令 ───────────────────────────────────────────────

INSTRUCTION = """你是证券交易助手，帮助用户管理账户、查询市场信息和执行交易。

## 可用的工具
— 账户查询 —
- get_account_summary: 查询账户总资产、可用资金、持仓市值
- get_positions: 查询全部持仓
- get_position_detail: 查询单只标的的持仓详情（成本、投入金额）
- get_open_orders: 查询当前未成交的挂单
- get_today_executions: 查询今日成交记录

— 市场数据 —
- security_resolve: 解析股票/指数名称到标准代码
- get_current_price: 查最新行情价格

— 交易操作 —
- place_order: **下单**（买入/卖出）
- cancel_order: **撤单**

## 重要规则

### 查询类规则（只读操作）
1. 查询某只标的的详情时，先用 security_resolve 确认代码，再用 get_position_detail。
2. 如果 security_resolve 返回多个候选，必须让用户确认，不能自行选择。
3. 回答盈亏、成本时必须说明计算口径。
4. 不要编造数据，如实告知用户。

### 交易类规则（写操作 — 高风险）
5. **下单前必须确认**：在调用 place_order 之前，必须向用户完整展示：
   - 标的代码和名称
   - 方向（买入/卖出）
   - 数量
   - 价格类型（限价/市价）
   - 限价单的价格
   获得用户明确确认后才能下单。
6. **撤单前必须确认**：必须告知用户要取消的订单详情，获得明确确认后才能执行。
7. **资金检查**：买入前建议先用 get_account_summary 确认可用资金是否充足。
8. **持仓检查**：卖出前建议先用 get_positions 检查可用持仓数量是否足够。
9. **代码确认**：下单前必须先通过 security_resolve 确认股票代码，不能直接使用用户输入的代码或名称。
10. 如果下单或撤单返回错误，如实展示错误信息，不要重试或修改参数。

### 数据分析类
11. 涉及条件筛选（如"最近一个月买入且浮亏超过10%"），先用 get_positions 获取全部持仓，再用 get_today_executions 获取今日成交，自己分析并回答。
"""

# ── 交互入口 ─────────────────────────────────────────────────


async def main():
    agent = Agent(
        name="account_assistant",
        description="证券账户助手 — 查询持仓、成交和行情",
        instruction=INSTRUCTION,
        tools=TOOLS,
    )
    runner = Runner(agent=agent, app_name="vibe-trading-poc")

    print("=" * 60)
    print("VeADK Agent — 智能交易助手")
    print("=" * 60)
    print("账户查询：")
    print("  • 我有多少钱？账户资产多少？")
    print("  • 我当前持有哪些股票？")
    print("  • 我在宁德时代上投了多少钱？成本多少？")
    print("  • 今天成交了哪些？")
    print("  • 当前有哪些挂单/委托？")
    print()
    print("行情查询：")
    print("  • 帮我查一下创业板指的代码")
    print("  • 招商银行现价多少？")
    print()
    print("交易操作（需要确认）：")
    print("  • 帮我买入100股招商银行，限价42.50")
    print("  • 帮我卖出500股宁德时代")
    print("  • 帮我撤单 order-xxx")
    print()
    print("输入 'exit' 或 '退出' 结束对话")
    print("=" * 60)

    session_id = f"poc-{date.today().isoformat()}"

    while True:
        try:
            user_input = input("\n你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "退出"):
            print("助手: 再见！")
            break

        print("\n助手: ", end="", flush=True)
        try:
            answer = await runner.run(
                messages=user_input,
                session_id=session_id,
            )
            print(answer)
        except Exception as e:
            print(f"抱歉，处理出错: {e}")


if __name__ == "__main__":
    asyncio.run(main())
