"""
Runner
スクリプトを Docker コンテナ または subprocess で実行する。
Docker が利用できない場合は自動的に subprocess へフォールバック。
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import tempfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from registry import ScriptInfo

logger = logging.getLogger(__name__)


class Runner:
    def __init__(self, config: dict) -> None:
        self.config = config
        runner_cfg = config.get("runner", {})
        self._use_docker: bool = runner_cfg.get("use_docker", True)
        self._docker_cfg: dict = runner_cfg.get("docker", {})
        self._docker_client = None

        if self._use_docker:
            self._docker_client = self._init_docker()

    # ── Public ──────────────────────────────────────────────

    async def run(self, script: "ScriptInfo", arguments: dict) -> str:
        if self._docker_client:
            return await self._run_docker(script, arguments)
        return await self._run_subprocess(script, arguments)

    # ── Docker ──────────────────────────────────────────────

    def _init_docker(self):
        """Docker クライアントを初期化。失敗時は None を返す。"""
        try:
            import docker  # type: ignore
            client = docker.from_env()
            client.ping()
            logger.info("Docker is available.")
            return client
        except Exception as e:
            logger.warning(
                f"Docker not available ({e}). Falling back to subprocess."
            )
            return None

    async def _run_docker(self, script: "ScriptInfo", arguments: dict) -> str:
        """
        Docker コンテナでスクリプトを実行する。
        - スクリプトと入力 JSON を読み取り専用でマウント
        - 非 root ユーザーで実行（sandbox/Dockerfile を使う場合）
        - メモリ・CPU 制限あり
        """
        input_json = json.dumps(arguments, ensure_ascii=False)

        # ── 入力ファイルを一時ファイルに書き出す ──
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as f:
            f.write(input_json)
            input_file = f.name

        try:
            return await asyncio.get_event_loop().run_in_executor(
                None, self._docker_run_sync, script, input_file
            )
        finally:
            try:
                os.unlink(input_file)
            except OSError:
                pass

    def _docker_run_sync(self, script: "ScriptInfo", input_file: str) -> str:
        import docker  # type: ignore

        # パッケージインストールが必要な場合は pip install してから実行
        packages_cmd = ""
        if script.packages:
            pkgs = " ".join(f'"{p}"' for p in script.packages)
            packages_cmd = f"pip install -q {pkgs} 2>/dev/null && "

        command = [
            "sh", "-c",
            f"{packages_cmd}python /sandbox/script.py < /sandbox/input.json",
        ]

        # ネットワーク設定: スクリプト個別 → グローバル設定 → デフォルト "none"
        network = (
            script.docker_network
            or self._docker_cfg.get("network", "none")
        )

        run_kwargs = dict(
            image=script.docker_image,
            command=command,
            volumes={
                script.script_path: {"bind": "/sandbox/script.py", "mode": "ro"},
                input_file:         {"bind": "/sandbox/input.json",  "mode": "ro"},
            },
            detach=True,
            mem_limit=self._docker_cfg.get("memory_limit", "256m"),
            network_mode=network,
            read_only=True,
            tmpfs={"/tmp": "size=64m"},
        )

        container = None
        try:
            container = self._docker_client.containers.run(**run_kwargs)

            result = container.wait(timeout=script.timeout + 5)
            stdout = container.logs(stdout=True, stderr=False).decode(errors="replace").strip()
            stderr = container.logs(stdout=False, stderr=True).decode(errors="replace").strip()

            if result["StatusCode"] != 0:
                return f"Error (exit {result['StatusCode']}):\n{stderr or stdout}"

            return _format_output(stdout)

        except Exception as e:
            if "timed out" in str(e).lower():
                return f"Error: Script timed out after {script.timeout}s"
            return f"Docker error: {e}"
        finally:
            if container:
                try:
                    container.remove(force=True)
                except Exception:
                    pass

    # ── Subprocess (fallback) ────────────────────────────────

    async def _run_subprocess(self, script: "ScriptInfo", arguments: dict) -> str:
        """
        subprocess でスクリプトを実行するフォールバック実装。
        環境分離は行わないが、タイムアウトは守る。
        """
        input_data = json.dumps(arguments, ensure_ascii=False).encode()

        # パッケージインストール
        if script.packages:
            logger.info(f"Installing packages: {script.packages}")
            pip = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "pip", "install", "-q", *script.packages,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await pip.wait()

        proc = await asyncio.create_subprocess_exec(
            sys.executable, script.script_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input_data),
                timeout=script.timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            return f"Error: Script timed out after {script.timeout}s"

        if proc.returncode != 0:
            err = stderr.decode(errors="replace").strip()
            return f"Error (exit {proc.returncode}):\n{err}"

        return _format_output(stdout.decode(errors="replace").strip())


# ── ヘルパー ──────────────────────────────────────────────────

def _format_output(raw: str) -> str:
    """JSON なら整形、そうでなければそのまま返す"""
    try:
        parsed = json.loads(raw)
        return json.dumps(parsed, ensure_ascii=False, indent=2)
    except (json.JSONDecodeError, ValueError):
        return raw
