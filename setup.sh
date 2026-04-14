#!/usr/bin/env bash
# setup.sh - MCP Wrapper セットアップスクリプト
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "=== MCP Python Script Wrapper セットアップ ==="

# ── 1. Python 仮想環境の作成 ──────────────────────────────────
echo ""
echo "[1/4] 仮想環境を作成: $VENV_DIR"
python3 -m venv "$VENV_DIR"

# ── 2. 依存パッケージのインストール ──────────────────────────
echo ""
echo "[2/4] 依存パッケージをインストール..."
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" -q
echo "  完了"

# ── 3. Docker イメージのビルド（任意）──────────────────────────
echo ""
echo "[3/4] Docker サンドボックスイメージのビルド..."
if command -v docker &>/dev/null; then
    docker build -t mcp-sandbox "$SCRIPT_DIR/sandbox" -q
    echo "  mcp-sandbox イメージをビルドしました"
    echo "  ヒント: config.yaml の docker.default_image を 'mcp-sandbox' に変更すると"
    echo "          このイメージが使われます"
else
    echo "  Docker が見つかりません。subprocess モード（use_docker: false）で動作します"
fi

# ── 4. Claude Desktop 設定ファイルの表示 ──────────────────────
PYTHON_PATH="$VENV_DIR/bin/python"
CLAUDE_CFG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"

echo ""
echo "[4/4] Claude Desktop の設定"
echo ""
echo "  以下を $CLAUDE_CFG の mcpServers に追加してください:"
echo ""
cat <<JSON
  "python-scripts": {
    "command": "$PYTHON_PATH",
    "args": ["$SCRIPT_DIR/server.py"]
  }
JSON

echo ""
echo "=== セットアップ完了 ==="
echo ""
echo "動作確認:"
echo "  echo '{\"name\": \"world\"}' | $PYTHON_PATH $SCRIPT_DIR/scripts/hello.py"
echo ""
