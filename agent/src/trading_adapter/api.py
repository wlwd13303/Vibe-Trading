"""FastAPI router — VeADK Trading Agent (POC 智能账号管理 + 智能交易).

安全设计原则：
- LLM 只负责生成订单草案（理解自然语言、提取参数）
- 订单参数持久化到内存存储，赋予唯一 card_id
- LLM 不参与实际下单，后端从存储加载原始参数后直接调 SDK
- 防止 LLM 幻觉篡改价格/数量等关键参数

Mount in api_server.py:

    from src.trading_adapter.api import trading_router
    app.include_router(trading_router, prefix="/api/trading")
"""

from __future__ import annotations

import logging
import os
import uuid
import yaml
from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ── 环境初始化（同 veadk_chat.py） ──────────────────────────────
os.environ.setdefault("LITELLM_LOG", "ERROR")
os.environ.setdefault("VEADK_LOG_LEVEL", "WARNING")

import logging as _logging

_logging.getLogger("httpx").setLevel(_logging.WARNING)
_logging.getLogger("httpcore").setLevel(_logging.WARNING)
_logging.getLogger("assetsplit_sdk").setLevel(_logging.WARNING)
_logging.getLogger("veadk").setLevel(_logging.WARNING)

# ── 订单持久化存储（SQLite） ─────────────────────────────────────
# LLM 生成的订单草案存入 SQLite，通过 card_id 引用。
# 用户确认时后端直接从 SQLite 加载原始参数调 SDK，LLM 无法篡改。

import sqlite3 as _sqlite3
from pathlib import Path as _Path

_ORDER_DB_PATH = _Path(__file__).resolve().parent.parent.parent / "order_drafts.db"


def _get_order_db() -> _sqlite3.Connection:
    """获取订单数据库连接（线程级）。"""
    db = _sqlite3.connect(str(_ORDER_DB_PATH))
    db.row_factory = _sqlite3.Row
    db.execute("""
        CREATE TABLE IF NOT EXISTS order_drafts (
            card_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            status TEXT NOT NULL DEFAULT 'pending',
            payload TEXT NOT NULL
        )
    """)
    db.commit()
    return db


def _save_order_draft(order_data: dict[str, Any]) -> str:
    """保存订单草案到 SQLite，返回唯一 card_id。"""
    import json

    card_id = uuid.uuid4().hex[:12]
    order_data["card_id"] = card_id
    order_data["status"] = "pending"

    db = _get_order_db()
    db.execute(
        "INSERT INTO order_drafts (card_id, status, payload) VALUES (?, ?, ?)",
        (card_id, "pending", json.dumps(order_data, ensure_ascii=False)),
    )
    db.commit()
    logger.info("Order draft saved: card_id=%s, stock=%s side=%s qty=%s price=%s",
                card_id, order_data.get("stock_code"), order_data.get("side"),
                order_data.get("quantity"), order_data.get("price"))
    return card_id


def _get_order_draft(card_id: str) -> dict[str, Any] | None:
    """从 SQLite 加载订单草案。"""
    import json

    db = _get_order_db()
    row = db.execute(
        "SELECT payload, status FROM order_drafts WHERE card_id = ?", (card_id,)
    ).fetchone()
    if row is None:
        return None
    data = json.loads(row["payload"])
    data["status"] = row["status"]
    return data


def _update_order_status(card_id: str, status: str, extra: dict[str, Any] | None = None) -> None:
    """更新订单状态。"""
    import json

    db = _get_order_db()
    row = db.execute(
        "SELECT payload FROM order_drafts WHERE card_id = ?", (card_id,)
    ).fetchone()
    if row is None:
        return
    payload = json.loads(row["payload"])
    payload["status"] = status
    if extra:
        payload.update(extra)
    db.execute(
        "UPDATE order_drafts SET status = ?, payload = ? WHERE card_id = ?",
        (status, json.dumps(payload, ensure_ascii=False), card_id),
    )
    db.commit()


# ── Pydantic models ──────────────────────────────────────────────


class ChatRequest(BaseModel):
    """用户发送给交易助手的自然语言消息。"""
    message: str = Field(..., min_length=1, max_length=2000, description="自然语言问句")
    session_id: str = Field(
        default_factory=lambda: f"trading-poc-{date.today().isoformat()}",
        description="会话 ID，相同 ID 可维持多轮对话上下文",
    )


class ChatResponse(BaseModel):
    """交易助手的回复。"""
    text: str = Field(..., description="自然语言回答")
    cards: list[dict[str, Any]] = Field(default_factory=list, description="结构化卡片数据")
    session_id: str = Field(..., description="会话 ID")


# ── 环境变量修复（同 veadk_chat.py 的逻辑） ────────────────────


def _ensure_veadk_env():
    """加载 agent/.env + config.yaml，保障 VeADK/LiteLLM 使用正确的端点与密钥。"""
    from pathlib import Path

    agent_dir = Path(__file__).resolve().parent.parent.parent

    # 1) 加载 agent/.env
    dotenv_path = agent_dir / ".env"
    if dotenv_path.exists():
        from dotenv import load_dotenv
        load_dotenv(dotenv_path)

    # 2) 从 config.yaml 读取 api_base
    config_path = agent_dir.parent / "config.yaml"
    if config_path.exists():
        try:
            with open(config_path) as f:
                cfg = yaml.safe_load(f)
            model_cfg = cfg.get("model", {}).get("agent", {})
            api_base = model_cfg.get("api_base", "")
            if api_base:
                os.environ["OPENAI_API_BASE"] = api_base
                os.environ["OPENAI_BASE_URL"] = api_base
        except Exception:
            pass

    # 3) VeADK 使用 MODEL_AGENT_API_KEY 环境变量
    if not os.getenv("MODEL_AGENT_API_KEY") and os.getenv("DEEPSEEK_API_KEY"):
        os.environ["MODEL_AGENT_API_KEY"] = os.environ["DEEPSEEK_API_KEY"]


_ensure_veadk_env()


# ── VeADK Agent + Runner （惰性初始化） ────────────────────────

_veadk_agent = None
_veadk_runner = None


def _get_veadk_agent():
    global _veadk_agent
    if _veadk_agent is not None:
        return _veadk_agent
    _ensure_veadk_env()
    from veadk import Agent
    from veadk_chat import TOOLS, INSTRUCTION

    _veadk_agent = Agent(
        name="account_assistant",
        description="证券账户助手 — 查询持仓、成交和行情",
        instruction=INSTRUCTION,
        tools=TOOLS,
    )
    return _veadk_agent


def _get_veadk_runner():
    global _veadk_runner
    if _veadk_runner is not None:
        return _veadk_runner
    from veadk import Runner
    agent = _get_veadk_agent()
    _veadk_runner = Runner(agent=agent, app_name="vibe-trading-poc-api")
    return _veadk_runner


# ── Router ───────────────────────────────────────────────────────

trading_router = APIRouter()


@trading_router.post("/chat", response_model=ChatResponse)
async def trading_chat(req: ChatRequest):
    """发送自然语言查询到 VeADK 交易助手。

    LLM 负责理解自然语言、提取参数、生成订单草案。
    下单参数会持久化到存储中，LLM 不参与实际执行。
    """
    import asyncio

    runner = _get_veadk_runner()

    try:
        answer = await runner.run(
            messages=req.message,
            session_id=req.session_id,
        )
        text = answer or "抱歉，我没有理解你的问题，请再描述一下。"
    except asyncio.CancelledError:
        text = "请求被中断，请重试一次。"
    except Exception as exc:
        logger.error("VeADK runner.run failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"交易助手处理出错: {exc}")

    cards = _extract_cards(text)

    # 兜底推断交互式卡片（LLM 没输出 JSON 块时）
    if not cards:
        # 检测限价/市价选择
        type_card = _infer_order_type_card(text, req.message)
        if type_card:
            cards = [type_card]
        else:
            # 检测价格输入
            price_card = _infer_price_input_card(text, req.message)
            if price_card:
                cards = [price_card]
            else:
                # 检测下单预览
                preview_card = _build_order_preview_card(text, req.message)
                if preview_card:
                    cards = [preview_card]

    # 持久化订单草案（防止 LLM 篡改参数）
    cards = _persist_order_cards(cards)

    clean_text = _strip_json_blocks(text)
    return ChatResponse(text=clean_text, cards=cards, session_id=req.session_id)


@trading_router.post("/order/commit/{card_id}")
async def order_commit(card_id: str):
    """用户点击确认下单后，从存储加载原始订单参数，直接调 SDK 执行。

    LLM 完全不参与此过程，保证下单参数与用户确认时完全一致。
    """
    from src.trading_adapter.client import get_adapter

    # 1) 从存储加载订单参数
    order = _get_order_draft(card_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"订单不存在或已过期: {card_id}")
    if order.get("status") != "pending":
        raise HTTPException(status_code=400, detail=f"订单状态异常: {order.get('status')}")

    # 2) 检查参数完整性
    stock_code = order.get("stock_code")
    side = order.get("side", "BUY")
    volume = order.get("quantity", 0)
    price = order.get("price")
    price_type = order.get("price_type", "LIMIT")

    if not stock_code or volume <= 0:
        raise HTTPException(status_code=400, detail="订单参数不完整")

    # 3) 标记为执行中
    _update_order_status(card_id, "committing")

    # 4) 直接调 SDK 下单（不走 LLM）
    try:
        adapter = get_adapter()
        result = adapter.create_order(
            stock_code=stock_code,
            side=side,
            volume=volume,
            price=price if price and price_type == "LIMIT" else None,
            price_type=price_type,
        )
        _update_order_status(card_id, "committed", {"result": result})
        is_ok = result.get("status") == "ok"
        logger.info("Order committed: card_id=%s result=%s", card_id, result.get("status"))
        return {
            "status": result.get("status", "ok"),
            "order_id": result.get("data", {}).get("order_id"),
            "message": f"{'买入' if side == 'BUY' else '卖出'}{stock_code} {volume}股 下单{'成功' if is_ok else '失败'}",
        }
    except Exception as exc:
        _update_order_status(card_id, "failed", {"error": str(exc)})
        logger.error("Order commit failed: card_id=%s error=%s", card_id, exc)
        raise HTTPException(status_code=500, detail=f"下单执行失败: {exc}")


@trading_router.post("/order/preview")
async def order_preview(req: ChatRequest):
    """生成交易预览（不下单，仅预览草案）。"""
    preview_prompt = (
        f"请解析以下交易指令，以 JSON 格式返回交易预览，"
        f"包含：stock_code, stock_name, side, quantity, price, price_type, "
        f"estimated_amount, 风险提示。不要实际下单！\n\n用户指令：{req.message}"
    )
    runner = _get_veadk_runner()
    try:
        answer = await runner.run(messages=preview_prompt, session_id=req.session_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    cards = _extract_cards(answer)
    cards = _persist_order_cards(cards)
    clean_text = _strip_json_blocks(answer)
    return {"text": clean_text, "cards": cards, "session_id": req.session_id}


# ── 辅助 ─────────────────────────────────────────────────────────


def _persist_order_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """拦截 order_confirm 卡片，持久化到存储并注入 card_id。

    LLM 生成的订单参数存入 _order_store 后，前端卡片通过 card_id
    引用，用户确认时后端直接从存储加载原始参数，LLM 无法篡改。
    """
    for card in cards:
        if card.get("kind") == "order_confirm":
            card_id = _save_order_draft(card)
            card["card_id"] = card_id
    return cards


def _infer_order_type_card(text: str, user_msg: str) -> dict[str, Any] | None:
    """检测 LLM 是否在让用户选择限价/市价，注入 order_type_selector 卡片。"""
    import re

    has_limit = any(kw in text for kw in ("限价单", "限价"))
    has_market = any(kw in text for kw in ("市价单", "市价"))
    if not (has_limit and has_market):
        return None
    # 必须包含下单意图
    if not any(kw in user_msg for kw in ("买入", "卖出", "买", "卖")):
        return None

    code_match = re.search(r"(\d{6}\.(?:SH|SZ))", text)
    stock_code = code_match.group(1) if code_match else ""
    # 提取名称
    name_match = re.search(r"([一-鿿]{2,8})\(", text)
    stock_name = name_match.group(1) if name_match else stock_code
    return {
        "kind": "order_type_selector",
        "stock_code": stock_code,
        "stock_name": stock_name,
    }


def _infer_price_input_card(text: str, user_msg: str) -> dict[str, Any] | None:
    """检测 LLM 是否在让用户输入价格，注入 price_input 卡片。"""
    import re

    if not any(kw in text for kw in ("价格", "限价", "输入")):
        return None
    if not any(kw in user_msg for kw in ("买入", "卖出", "买", "卖")):
        return None
    # 如果已经指定了价格则不显示
    if re.search(r"\d+\.?\d*\s*元", user_msg):
        return None

    code_match = re.search(r"(\d{6}\.(?:SH|SZ))", text)
    if not code_match:
        return None
    stock_code = code_match.group(1)
    name_match = re.search(r"([一-鿿]{2,8})\(", text)
    stock_name = name_match.group(1) if name_match else stock_code

    return {
        "kind": "price_input",
        "stock_code": stock_code,
        "stock_name": stock_name,
    }


def _build_order_preview_card(text: str, user_msg: str) -> dict[str, Any] | None:
    """当 LLM 未输出 JSON 块时，从文字中尝试提取下单预览信息构建卡片。"""
    import re

    if not any(kw in text for kw in ("买入", "卖出", "下单", "确认", "预览")):
        return None
    if not any(kw in user_msg for kw in ("买入", "卖出", "买", "卖")):
        return None

    code_match = re.search(r"(\d{6}\.(?:SH|SZ))", text)
    if not code_match:
        code_match = re.search(r"(\d{6}\.(?:SH|SZ))", user_msg)
    if not code_match:
        return None
    stock_code = code_match.group(1)

    side = "BUY" if any(kw in text for kw in ("买入", "买")) else "SELL" if any(kw in text for kw in ("卖出", "卖")) else None
    if not side:
        return None

    qty_match = re.search(r"(\d+)\s*股", text)
    if not qty_match:
        qty_match = re.search(r"(\d+)\s*股", user_msg)
    quantity = int(qty_match.group(1)) if qty_match else 0

    price_match = re.search(r"(\d+\.?\d*)\s*元", text)
    if not price_match:
        price_match = re.search(r"限价\s*(\d+\.?\d*)", user_msg)
    price = float(price_match.group(1)) if price_match else 0

    name_match = re.search(r"([一-鿿]+)\(", text)
    stock_name = name_match.group(1) if name_match else stock_code

    if quantity <= 0:
        return None

    return {
        "kind": "order_confirm",
        "stock_code": stock_code,
        "stock_name": stock_name,
        "side": side,
        "quantity": quantity,
        "price": price,
        "price_type": "LIMIT" if price > 0 else "MARKET",
        "estimated_amount": round(quantity * price, 2) if price > 0 else 0,
    }


def _strip_json_blocks(text: str) -> str:
    import re
    return re.sub(r"```(?:json)?\s*\n?.*?```\s*", "", text, flags=re.DOTALL | re.IGNORECASE).strip()


def _extract_cards(text: str) -> list[dict[str, Any]]:
    import json
    import re

    cards: list[dict[str, Any]] = []
    for match in re.finditer(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL | re.IGNORECASE):
        block = match.group(1).strip()
        if not block:
            continue
        try:
            data = json.loads(block)
            if isinstance(data, dict):
                cards.append(data)
            elif isinstance(data, list):
                cards.extend(data)
        except json.JSONDecodeError:
            continue
    return cards
