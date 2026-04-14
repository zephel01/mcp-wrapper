# YAML 設定リファレンス

`scripts/*.yaml` ファイルの全フィールドを説明します。

---

## 完全なサンプル

```yaml
# scripts/my_tool.yaml

# ── 必須フィールド ───────────────────────────────────────────
name: my_tool
description: "このツールが何をするかの説明。Claude がツール選択に使う"

# ── 任意フィールド ───────────────────────────────────────────
timeout: 30       # 実行タイムアウト（秒）。デフォルト: 30
packages:         # pip でインストールするパッケージ
  - pandas
  - requests

docker:
  image: python:3.12-slim  # 実行する Docker イメージ。デフォルト: python:3.12-slim
  network: none            # "none" (遮断) / "bridge" (外部通信可). デフォルト: none

# ── パラメータ定義（JSON Schema 形式）───────────────────────
parameters:
  type: object
  properties:
    param_name:
      type: string
      description: "パラメータの説明"
    optional_param:
      type: integer
      description: "省略可能なパラメータ"
      default: 10
  required:
    - param_name
```

---

## フィールド詳細

### `name` （必須）

MCP ツールとして公開される名前です。英数字とアンダースコアのみ使用できます。ファイル名と一致させることを推奨しますが、YAML の `name` が実際にツール名として使われます。

```yaml
name: csv_analyze
```

### `description` （必須）

Claude がツールを選択するときに読む説明文です。「何を入力すると何が返るか」を具体的に書くと精度が上がります。

```yaml
# 悪い例
description: "CSV ツール"

# 良い例
description: "CSV テキストを受け取り、行数・列名・基本統計量・欠損値を分析して返す"
```

### `timeout`

スクリプトの実行タイムアウト（秒）です。デフォルトは `30` 秒。パッケージインストールが必要なスクリプトは、初回実行でインストール時間が加算されるため余裕を持った値にしてください。

```yaml
timeout: 60   # pip install を含めた余裕のある値
```

### `packages`

Docker コンテナ内で実行前に `pip install` するパッケージのリストです。空の場合は省略できます。

```yaml
packages:
  - pandas>=2.0
  - "requests[security]"
  - pillow
```

> **パフォーマンスヒント**: よく使うパッケージは `sandbox/Dockerfile` にプリインストールしておくと毎回のインストール時間を省けます。

### `docker`

Docker 実行の個別設定です。`config.yaml` のグローバル設定を上書きします。

```yaml
docker:
  image: python:3.11-slim    # 使用する Docker イメージ
  network: bridge            # ネットワーク設定
```

**`docker.image`**

使用する Docker イメージを指定します。デフォルトは `python:3.12-slim`。特定のライブラリが必要な場合は専用イメージを指定できます。

```yaml
docker:
  image: pytorch/pytorch:2.3.0-cuda12.1-cudnn8-runtime  # GPU 対応イメージ
```

**`docker.network`**

| 値 | 説明 |
|---|---|
| `none` | ネットワーク完全遮断（デフォルト、最も安全） |
| `bridge` | 外部インターネットへのアクセスを許可 |

外部 API を呼び出すスクリプトには `bridge` が必要です。

```yaml
docker:
  network: bridge
```

### `parameters`

MCP の `inputSchema` として使われる [JSON Schema](https://json-schema.org/) です。Claude はこのスキーマを読んで適切な引数を組み立てます。

```yaml
parameters:
  type: object
  properties:

    # 文字列
    text:
      type: string
      description: "処理するテキスト"

    # 整数（デフォルト値あり）
    max_items:
      type: integer
      description: "最大件数"
      default: 10

    # 真偽値
    verbose:
      type: boolean
      description: "詳細出力するか"
      default: false

    # 配列
    keywords:
      type: array
      items:
        type: string
      description: "検索キーワードのリスト"

    # 列挙型（enum）
    format:
      type: string
      enum: [json, csv, text]
      description: "出力フォーマット"

  required:
    - text     # 必須パラメータ
               # 省略可能なパラメータは required に含めない
```

---

## グローバル設定（`config.yaml`）

サーバー全体のデフォルト動作を制御します。

```yaml
server:
  name: "python-script-runner"   # MCP サーバーの識別名

scripts_dir: "./scripts"         # スクリプトディレクトリのパス

runner:
  use_docker: true               # false: subprocess モード（Docker 不要）

  docker:
    default_image: "python:3.12-slim"
    network: "none"              # スクリプト個別設定で上書き可能
    memory_limit: "256m"         # コンテナのメモリ上限
```

スクリプト個別の `docker` 設定は、このグローバル設定より優先されます。

---

## よくある設定例

### データ分析スクリプト（ネットワーク不要）

```yaml
name: data_stats
description: "数値リストの統計量（平均・中央値・標準偏差）を計算する"
timeout: 15
packages:
  - numpy

parameters:
  type: object
  properties:
    values:
      type: array
      items:
        type: number
      description: "統計を計算する数値のリスト"
  required: [values]
```

### 外部 API 連携スクリプト

```yaml
name: translate
description: "テキストを指定言語に翻訳する"
timeout: 30
packages:
  - deep-translator

docker:
  network: bridge  # 翻訳 API へのアクセスに必要

parameters:
  type: object
  properties:
    text:
      type: string
      description: "翻訳するテキスト"
    target_lang:
      type: string
      description: "翻訳先の言語コード（例: ja, en, zh-CN）"
      default: "ja"
  required: [text]
```

### 重い処理（タイムアウト延長）

```yaml
name: pdf_extract
description: "PDF ファイルのテキストを抽出する"
timeout: 120      # PDF が大きい場合を考慮
packages:
  - pymupdf

parameters:
  type: object
  properties:
    pdf_base64:
      type: string
      description: "Base64 エンコードした PDF データ"
  required: [pdf_base64]
```
