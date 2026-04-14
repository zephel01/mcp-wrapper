"""
Script Registry
scripts/ ディレクトリを走査して ScriptInfo を構築する
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ScriptInfo:
    """スクリプト1本分のメタ情報"""

    name: str
    description: str
    script_path: str
    input_schema: dict          # JSON Schema (MCP inputSchema)
    timeout: int = 30           # 実行タイムアウト（秒）
    packages: list = field(default_factory=list)  # pip パッケージ
    docker_image: str = "python:3.12-slim"
    docker_network: Optional[str] = None  # None → グローバル設定を使用


class ScriptRegistry:
    """
    scripts/ 以下の *.yaml + *.py ペアを読み込む。

    ディレクトリ構成:
        scripts/
        ├── my_tool.yaml   # メタ情報（name, description, parameters, ...）
        └── my_tool.py     # 実際のスクリプト
    """

    def __init__(self, scripts_dir: str) -> None:
        self.scripts_dir = Path(scripts_dir)
        self._scripts: dict[str, ScriptInfo] = {}
        self._load()

    # ── Public ──────────────────────────────────────────────

    def reload(self) -> None:
        """ホットリロード: scripts/ を再スキャンする"""
        self._load()

    @property
    def scripts(self) -> list[ScriptInfo]:
        return list(self._scripts.values())

    def get(self, name: str) -> Optional[ScriptInfo]:
        return self._scripts.get(name)

    # ── Private ─────────────────────────────────────────────

    def _load(self) -> None:
        self._scripts.clear()

        if not self.scripts_dir.exists():
            logger.warning(f"scripts_dir not found: {self.scripts_dir}")
            return

        for yaml_file in sorted(self.scripts_dir.glob("*.yaml")):
            script_file = yaml_file.with_suffix(".py")
            if not script_file.exists():
                logger.warning(f"Script file not found for {yaml_file.name}, skipping.")
                continue

            try:
                info = self._parse_yaml(yaml_file, script_file)
                self._scripts[info.name] = info
                logger.debug(f"Registered tool: {info.name}")
            except Exception as e:
                logger.error(f"Failed to load {yaml_file.name}: {e}")

        logger.info(f"Registry loaded: {list(self._scripts.keys())}")

    def _parse_yaml(self, yaml_file: Path, script_file: Path) -> ScriptInfo:
        with open(yaml_file, encoding="utf-8") as f:
            meta: dict = yaml.safe_load(f) or {}

        name = meta.get("name") or yaml_file.stem
        description = meta.get("description", "")

        # parameters が未定義なら空スキーマ
        schema = meta.get("parameters") or {"type": "object", "properties": {}}

        # docker セクション（任意）
        docker_cfg = meta.get("docker") or {}

        return ScriptInfo(
            name=name,
            description=description,
            script_path=str(script_file.resolve()),
            input_schema=schema,
            timeout=int(meta.get("timeout", 30)),
            packages=list(meta.get("packages") or []),
            docker_image=docker_cfg.get("image", "python:3.12-slim"),
            docker_network=docker_cfg.get("network"),  # None → global
        )
