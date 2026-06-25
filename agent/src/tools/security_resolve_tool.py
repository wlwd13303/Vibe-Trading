"""Tool: resolve a Chinese stock/index name to a standardized security code."""

from __future__ import annotations

import json
from typing import Any

from src.agent.tools import BaseTool
from src.data_sources.market_data.client import resolve_name_to_code


class SecurityResolveTool(BaseTool):
    """Resolve a Chinese stock/index name to candidate standardized codes."""

    name = "security_resolve"
    description = (
        "解析股票/指数名称到标准化代码，例如'创业板指'→399006.SZ、'招商银行'→600036.SH。"
        "返回匹配候选列表，包含代码、名称和类型。当出现多个候选时必须由用户确认。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "股票/指数名称或代码，如'创业板指'、'招商银行'、'宁德时代'",
            },
        },
        "required": ["name"],
    }
    repeatable = True
    is_readonly = True

    def execute(self, **kwargs: Any) -> str:
        name = str(kwargs.get("name", "")).strip()
        if not name:
            return json.dumps({"status": "error", "error": "名称不能为空"}, ensure_ascii=False)

        candidates = resolve_name_to_code(name)
        if not candidates:
            return json.dumps(
                {"status": "ok", "data": [], "message": f"未找到匹配'{name}'的标的"},
                ensure_ascii=False,
            )

        return json.dumps(
            {
                "status": "ok",
                "data": candidates,
                "count": len(candidates),
                "multiple": len(candidates) > 1,
                "message": f"找到 {len(candidates)} 个匹配候选，需要用户确认" if len(candidates) > 1
                           else "找到唯一匹配",
            },
            ensure_ascii=False,
        )
