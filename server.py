"""
MCP Wrapper Server
任意のPythonスクリプトをMCPツールとして公開する汎用サーバー
"""

import asyncio
import logging
import sys
from pathlib import Path

import yaml
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from registry import ScriptRegistry
from runner import Runner

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── 設定読み込み ──────────────────────────────────────────────
_config_path = Path(__file__).parent / "config.yaml"
with open(_config_path, encoding="utf-8") as _f:
    config = yaml.safe_load(_f)

# ── レジストリ & ランナー初期化 ───────────────────────────────
_scripts_dir = Path(__file__).parent / config.get("scripts_dir", "scripts")
registry = ScriptRegistry(str(_scripts_dir))
runner = Runner(config)

# ── MCP Server ────────────────────────────────────────────────
app = Server(config.get("server", {}).get("name", "python-script-runner"))


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    """scripts/ ディレクトリを再スキャンしてツール一覧を返す（ホットリロード対応）"""
    registry.reload()
    tools = []
    for script in registry.scripts:
        tools.append(
            types.Tool(
                name=script.name,
                description=script.description,
                inputSchema=script.input_schema,
            )
        )
    logger.info(f"Loaded {len(tools)} tool(s): {[t.name for t in tools]}")
    return tools


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """指定ツール（スクリプト）を実行して結果を返す"""
    script = registry.get(name)
    if not script:
        raise ValueError(f"Unknown tool: '{name}'")

    logger.info(f"Calling tool '{name}' with args: {arguments}")
    try:
        result = await runner.run(script, arguments)
        return [types.TextContent(type="text", text=result)]
    except Exception as e:
        logger.exception(f"Error running tool '{name}'")
        return [types.TextContent(type="text", text=f"Error: {e}")]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
