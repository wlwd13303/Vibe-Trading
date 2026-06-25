"""Quick verification script for Phase-1 POC tool discovery & registration.

Usage:
    cd agent && python test_poc_discovery.py

This tests:
  1. Tool auto-discovery picks up the 3 new tools.
  2. Tushare is configured (token check).
  3. SecurityResolveTool returns candidates for "创业板指".
  4. PositionQueryTool and TodayExecutionTool are registered.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env before anything else
from dotenv import load_dotenv

dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path)

from src.tools import build_registry

OK = "[OK]"
WARN = "[WARN]"
FAIL = "[FAIL]"


def main():
    print("=" * 60)
    print("Phase 1 POC - Tool Discovery & Readiness Check")
    print("=" * 60)

    # 1) Build the full tool registry
    registry = build_registry()
    print(f"\n{OK} Tool registry built with {len(registry)} tools.")

    # 2) Check our 3 tools are registered
    expected_tools = ["security_resolve", "position_query", "today_execution"]
    for name in expected_tools:
        tool = registry.get(name)
        if tool:
            print(f"   {OK} {name} - registered")
        else:
            print(f"   {FAIL} {name} - NOT FOUND in registry")

    # 3) List all registered tools
    print(f"\nAll registered tools ({len(registry)} total):")
    for name in registry.tool_names:
        print(f"   - {name}")

    # 4) Test SecurityResolveTool with "创业板指"
    resolve_tool = registry.get("security_resolve")
    if resolve_tool:
        print('\n--- Testing security_resolve("创业板指") ---')
        try:
            result = resolve_tool.execute(name="创业板指")
            print(result[:500])
        except RuntimeError as e:
            print(f"{FAIL} {e}")
            print("   Set TUSHARE_TOKEN in agent/.env to enable this test.")

    # 5) Tushare token check
    token = os.getenv("TUSHARE_TOKEN", "")
    if token and token != "your-tushare-token":
        print(f"\n{OK} TUSHARE_TOKEN is set ({token[:4]}...{token[-4:]})")
    else:
        print(f"\n{WARN} TUSHARE_TOKEN not configured - market data features won't work")
        print("   Set it in agent/.env or environment, e.g.:")
        print("   TUSHARE_TOKEN=your_token_here")

    # 6) SDK config check
    sdk_url = os.getenv("SDK_BASE_URL", "")
    sdk_user = os.getenv("SDK_USERNAME", "")
    if sdk_url and sdk_user:
        print(f"{OK} SDK_BASE_URL and SDK_USERNAME are set")
    else:
        print(f"{WARN} SDK connection not configured - trading adapter will use defaults from subscription script")

    print("\n" + "=" * 60)
    print("Verification complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()
