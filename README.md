<div align="center">

# 🐍 mcp-wrapper

**Drop a `.py` + `.yaml` → Instant MCP Tool**

Python スクリプトを置くだけで AI エージェントから呼び出せる MCP ツールになる汎用ラッパー

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-1.0%2B-blueviolet)](https://modelcontextprotocol.io/)
[![Docker](https://img.shields.io/badge/Docker-Sandbox-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## ✨ 何ができるか

```
scripts/my_tool.yaml   ←  ツール名・説明・パラメータを定義
scripts/my_tool.py     ←  処理を書く（stdin JSON → stdout JSON）
```

この 2 ファイルを置くだけで MCP 対応エージェントから `my_tool` が使えるようになります。
再起動不要。Docker コンテナ内で安全に実行されます。

**対応クライアント:** [Hermes Agent](https://hermes-agent.nousresearch.com/) / [OpenClaw](https://docs.openclaw.ai/) / [Claude Desktop](https://claude.ai/download) など MCP stdio 対応のエージェント全般

---

## 🚀 クイックスタート

```bash
git clone https://github.com/zephel01/mcp-wrapper.git
cd mcp-wrapper
bash setup.sh
```

### Hermes Agent（推奨）

`~/.hermes/config.json` の `mcp_servers` に追記します。

```json
{
  "mcp_servers": {
    "python-scripts": {
      "command": "/path/to/mcp-wrapper/.venv/bin/python",
      "args": ["/path/to/mcp-wrapper/server.py"]
    }
  }
}
```

起動時に自動検出・登録されます。ツールの変更も hot-reload で即時反映。

### OpenClaw

`openclaw.config.json` に追記します。

```json
{
  "mcpServers": {
    "python-scripts": {
      "command": "/path/to/mcp-wrapper/.venv/bin/python",
      "args": ["/path/to/mcp-wrapper/server.py"]
    }
  }
}
```

### Claude Desktop

```json
// ~/Library/Application Support/Claude/claude_desktop_config.json
{
  "mcpServers": {
    "python-scripts": {
      "command": "/path/to/mcp-wrapper/.venv/bin/python",
      "args": ["/path/to/mcp-wrapper/server.py"]
    }
  }
}
```

---

## 📦 スクリプトの追加

**1. メタ情報を書く** (`scripts/my_tool.yaml`)

```yaml
name: my_tool
description: "テキストを大文字に変換する"
timeout: 10
packages: []          # pip パッケージ（任意）

parameters:
  type: object
  properties:
    text:
      type: string
      description: "変換するテキスト"
  required: [text]
```

**2. 処理を書く** (`scripts/my_tool.py`)

```python
import json, sys

def main(params):
    return {"result": params["text"].upper()}

if __name__ == "__main__":
    print(json.dumps(main(json.load(sys.stdin)), ensure_ascii=False))
```

**それだけ。** エージェントの再起動は不要です。

---

## 🗂 同梱スクリプト

| ツール | 説明 |
|---|---|
| `hello` | 動作確認用。名前と挨拶の言葉を指定してメッセージを生成 |
| `csv_analyze` | CSV テキストの行数・列名・基本統計量・欠損値を分析（pandas 使用） |
| `web_fetch` | 指定 URL のコンテンツをテキストで取得（ネットワーク接続あり） |

---

## 🔒 セキュリティモデル

スクリプトは Docker コンテナ内で実行されます。

```
コンテナの制約
├── ファイルシステム  read-only（/tmp のみ書き込み可 64MB）
├── ネットワーク      デフォルト遮断（network: none）
├── メモリ           256MB 上限
└── タイムアウト      YAML で指定した秒数
```

Docker が使えない環境では subprocess に自動フォールバックします。
ネットワークが必要なスクリプトは YAML に `docker: {network: bridge}` を追加します。

---

## 🗃 ディレクトリ構成

```
mcp-wrapper/
├── server.py               # MCP サーバー本体
├── registry.py             # scripts/ の自動検出
├── runner.py               # Docker / subprocess 実行エンジン
├── config.yaml             # グローバル設定
├── requirements.txt
├── setup.sh
├── sandbox/
│   └── Dockerfile          # スクリプト実行用ベースイメージ
├── scripts/
│   ├── hello.py / .yaml
│   ├── csv_analyze.py / .yaml
│   └── web_fetch.py / .yaml
└── docs/
    ├── architecture.md
    ├── adding-scripts.md
    └── yaml-reference.md
```

---

## ⚙️ 設定

`config.yaml` でサーバー全体の動作を変更できます。

```yaml
runner:
  use_docker: true        # false → subprocess モード（Docker 不要）
  docker:
    network: "none"       # "bridge" で外部通信を許可
    memory_limit: "256m"
```

---

## 📖 ドキュメント

- [アーキテクチャ詳細](docs/architecture.md) — データフロー・各コンポーネントの責務
- [スクリプト追加ガイド](docs/adding-scripts.md) — パターン別のサンプルコード
- [YAML リファレンス](docs/yaml-reference.md) — 全フィールドの説明

---

## 🛠 動作確認

```bash
# スクリプト単体テスト（Claude Desktop なし）
echo '{"name": "world"}' | .venv/bin/python scripts/hello.py

echo '{"csv_content": "a,b\n1,2\n3,4", "column": "a"}' | \
  .venv/bin/python scripts/csv_analyze.py
```

---

## 📄 ライセンス

MIT
