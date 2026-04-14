# アーキテクチャ詳細

## 全体構成

```
┌─────────────────────────────────────────────────────────────┐
│  Claude Desktop                                             │
│                                                             │
│   「csv_analyze ツールを呼び出して」                          │
└──────────────────┬──────────────────────────────────────────┘
                   │ MCP (stdio)
                   │ JSON-RPC 2.0
┌──────────────────▼──────────────────────────────────────────┐
│  server.py  ─  MCP Server                                   │
│                                                             │
│  ┌───────────────┐     ┌──────────────────────────────────┐ │
│  │ registry.py   │     │ runner.py                        │ │
│  │               │     │                                  │ │
│  │ scripts/ を   │     │ Docker SDK  ──→  コンテナ起動    │ │
│  │ スキャンして  │     │                  ↓               │ │
│  │ ツール一覧を  │     │ subprocess  ──→  プロセス起動    │ │
│  │ 構築する      │     │ (fallback)                       │ │
│  └───────────────┘     └──────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │  Docker コンテナ    │
        │  (サンドボックス)   │
        │                     │
        │  script.py          │
        │   ← stdin:  JSON    │
        │   → stdout: JSON    │
        └─────────────────────┘
```

---

## コンポーネント別の責務

### `server.py` — MCP サーバー本体

MCP プロトコルのエントリーポイントです。`mcp` ライブラリの低レベル `Server` クラスを使い、2 つのハンドラーを登録しています。

**`list_tools`ハンドラー**
Claude から「どんなツールが使えますか？」と聞かれたときに呼ばれます。`registry.reload()` でホットリロードしてから現在のツール一覧を返します。Claude Desktop 側の再起動なしにスクリプトを追加・変更できるのはこのためです。

**`call_tool`ハンドラー**
Claude がツールを実行するときに呼ばれます。ツール名で `registry.get()` してスクリプト情報を取得し、`runner.run()` に渡します。

---

### `registry.py` — スクリプトレジストリ

`scripts/` ディレクトリの `*.yaml` ファイルを走査して、各スクリプトのメタ情報を `ScriptInfo` データクラスに変換します。

```
scripts/my_tool.yaml + my_tool.py
           │
           ▼
ScriptInfo(
    name="my_tool",
    description="...",
    script_path="/abs/path/scripts/my_tool.py",
    input_schema={...},   ← JSON Schema として MCP に渡される
    timeout=30,
    packages=["pandas"],
    docker_image="python:3.12-slim",
    docker_network=None,
)
```

`input_schema` は MCP の `Tool.inputSchema` にそのまま渡るため、YAML の `parameters` フィールドは JSON Schema として書く必要があります。これにより Claude は各パラメータの型・説明・必須かどうかを正確に把握できます。

---

### `runner.py` — 実行エンジン

スクリプトをサンドボックスで実行する責務を持ちます。**Docker が利用可能かどうかを起動時に自動判定**し、どちらを使うかを切り替えます。

#### Docker モード（推奨）

```
1. 引数 JSON を一時ファイル (tmpfile) に書き出す
2. docker.containers.run() でコンテナ起動
   - script.py → /sandbox/script.py (読み取り専用マウント)
   - tmpfile   → /sandbox/input.json (読み取り専用マウント)
   - / は read_only=True
   - /tmp だけ tmpfs (64MB) で書き込み可能
3. container.wait(timeout=...) で完了を待つ
4. logs() で stdout/stderr を取得
5. コンテナを強制削除 (remove force=True)
```

セキュリティ上の制約をまとめると:

| 制約 | 設定 |
|---|---|
| ファイルシステム | 読み取り専用（/tmp のみ書き込み可） |
| ネットワーク | デフォルト遮断 (`network_mode: none`) |
| メモリ | 256MB 上限 |
| 実行ユーザー | コンテナ内のデフォルトユーザー（カスタムイメージでは非 root） |
| タイムアウト | YAML の `timeout` 値（デフォルト 30 秒） |

#### subprocess モード（フォールバック）

Docker が使えない環境（CI など）での代替実装です。`asyncio.create_subprocess_exec` でスクリプトを起動し、stdin で JSON を渡します。`asyncio.wait_for` でタイムアウトを守ります。環境の分離はされないため、ローカル開発・テスト用途に限定することを推奨します。

---

## データフロー

Claude からツールが呼び出されたときの流れを追います。

```
Claude Desktop
  │  tools/call { name: "csv_analyze", arguments: { csv_content: "..." } }
  ▼
server.py / call_tool()
  │  registry.get("csv_analyze") → ScriptInfo
  │  runner.run(script_info, arguments)
  ▼
runner.py / _run_docker()
  │  json.dumps(arguments) → /tmp/xxxxx.json
  │  docker.containers.run(
  │      image="python:3.12-slim",
  │      command=["sh","-c","pip install -q pandas && python /sandbox/script.py < /sandbox/input.json"],
  │      volumes={script_path: ro, input_file: ro},
  │      network_mode="none", read_only=True, mem_limit="256m"
  │  )
  ▼
Docker コンテナ内 / csv_analyze.py
  │  params = json.load(sys.stdin)  ← /sandbox/input.json
  │  result = main(params)
  │  print(json.dumps(result))       → stdout
  ▼
runner.py
  │  container.logs(stdout=True) → raw JSON 文字列
  │  _format_output() → 整形済み JSON
  ▼
server.py
  │  [TextContent(type="text", text="{...}")]
  ▼
Claude Desktop
  ← ツール実行結果
```

---

## スクリプトのインターフェース規約

すべてのスクリプトは以下の規約に従う必要があります。

**入力**: `sys.stdin` から JSON オブジェクトを読み込む

```python
params = json.load(sys.stdin)
```

**出力**: `sys.stdout` に JSON オブジェクトを出力する

```python
print(json.dumps(result, ensure_ascii=False))
```

**エラー**: ゼロ以外の終了コードで終了するか、`{"error": "説明"}` を返す

```python
# 方法 A: 例外を上げる（stderr に出力され runner がキャプチャ）
raise ValueError("Invalid input")

# 方法 B: エラー情報を JSON で返す
return {"error": "Invalid input: ..."}
```

出力が JSON として解析可能な場合、runner が自動的にインデント整形して Claude に返します。JSON 以外のプレーンテキストをそのまま返すことも可能です。

---

## ホットリロードの仕組み

`list_tools` ハンドラーは呼ばれるたびに `registry.reload()` を実行します。これにより Claude Desktop を再起動しなくても、`scripts/` にファイルを追加・変更するだけで即座に反映されます。

```
scripts/ にファイル追加
    ↓
次回 Claude がツール一覧を確認
    ↓
registry.reload() が走り新しいツールを検出
    ↓
Claude が新ツールを認識・使用可能に
```
