# スクリプト追加ガイド

## 最小構成

`scripts/` ディレクトリに 2 つのファイルを置くだけです。

```
scripts/
├── your_tool.yaml   ← メタ情報・パラメータ定義
└── your_tool.py     ← 実装
```

---

## Step 1: YAML を書く

```yaml
# scripts/your_tool.yaml

name: your_tool
description: "Claude に表示されるツールの説明。何ができるかを一言で"
timeout: 30          # 実行タイムアウト（秒）
packages: []         # pip でインストールするパッケージ

parameters:
  type: object
  properties:
    input_text:
      type: string
      description: "処理するテキスト"
  required:
    - input_text
```

`description` は Claude がツールを選ぶ判断基準になります。「何を入力すると何が返るか」を具体的に書くと精度が上がります。

---

## Step 2: Python スクリプトを書く

```python
# scripts/your_tool.py

import json
import sys


def main(params: dict) -> dict:
    text = params["input_text"]
    # ── ここに処理を書く ──
    result = text.upper()
    return {"output": result}


if __name__ == "__main__":
    params = json.load(sys.stdin)   # 入力: JSON (stdin)
    result = main(params)
    print(json.dumps(result, ensure_ascii=False))  # 出力: JSON (stdout)
```

スクリプトのインターフェース規約は次の 2 点だけです。

- **入力**: `sys.stdin` から JSON を読む（`json.load(sys.stdin)`）
- **出力**: `sys.stdout` に JSON を書く（`print(json.dumps(...))`）

---

## よくあるパターン

### パターン A: 標準ライブラリのみ（最もシンプル）

```yaml
# scripts/text_count.yaml
name: text_count
description: "テキストの文字数・単語数・行数をカウントする"
timeout: 10
packages: []

parameters:
  type: object
  properties:
    text:
      type: string
      description: "カウントするテキスト"
  required: [text]
```

```python
# scripts/text_count.py
import json, sys

def main(params):
    text = params["text"]
    return {
        "chars": len(text),
        "words": len(text.split()),
        "lines": len(text.splitlines()),
    }

if __name__ == "__main__":
    print(json.dumps(main(json.load(sys.stdin)), ensure_ascii=False))
```

---

### パターン B: 外部パッケージを使う

```yaml
# scripts/sentiment.yaml
name: sentiment
description: "テキストの感情分析を行う（ポジティブ/ネガティブ/ニュートラル）"
timeout: 60   # パッケージインストール時間を含めて余裕を持たせる
packages:
  - textblob

parameters:
  type: object
  properties:
    text:
      type: string
      description: "分析するテキスト（英語）"
  required: [text]
```

```python
# scripts/sentiment.py
import json, sys

def main(params):
    from textblob import TextBlob
    blob = TextBlob(params["text"])
    polarity = blob.sentiment.polarity
    if polarity > 0.1:
        label = "positive"
    elif polarity < -0.1:
        label = "negative"
    else:
        label = "neutral"
    return {"label": label, "polarity": round(polarity, 3)}

if __name__ == "__main__":
    print(json.dumps(main(json.load(sys.stdin)), ensure_ascii=False))
```

`packages` に書いたパッケージは Docker コンテナ起動時に自動インストールされます。初回実行は少し時間がかかります。

---

### パターン C: ネットワークアクセスが必要

デフォルトではコンテナのネットワークは遮断されています。外部通信が必要なスクリプトは YAML に `docker.network: bridge` を追加します。

```yaml
# scripts/ip_lookup.yaml
name: ip_lookup
description: "IP アドレスの地理情報を取得する"
timeout: 30
packages:
  - requests

docker:
  network: bridge   # ← ネットワークアクセスを許可

parameters:
  type: object
  properties:
    ip:
      type: string
      description: "調べる IP アドレス（例: 8.8.8.8）"
  required: [ip]
```

```python
# scripts/ip_lookup.py
import json, sys, requests

def main(params):
    ip = params["ip"]
    resp = requests.get(f"https://ipapi.co/{ip}/json/", timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return {
        "ip": ip,
        "country": data.get("country_name"),
        "city": data.get("city"),
        "org": data.get("org"),
    }

if __name__ == "__main__":
    print(json.dumps(main(json.load(sys.stdin)), ensure_ascii=False))
```

---

### パターン D: ファイルデータを処理する

Claude からファイルの中身をテキストとして渡し、スクリプト内で処理します。

```yaml
# scripts/json_format.yaml
name: json_format
description: "JSON テキストを整形・バリデーションする"
timeout: 10
packages: []

parameters:
  type: object
  properties:
    json_text:
      type: string
      description: "整形する JSON テキスト"
    indent:
      type: integer
      description: "インデントのスペース数（デフォルト: 2）"
  required: [json_text]
```

```python
# scripts/json_format.py
import json, sys

def main(params):
    try:
        data = json.loads(params["json_text"])
        indent = params.get("indent", 2)
        formatted = json.dumps(data, ensure_ascii=False, indent=indent)
        return {"formatted": formatted, "valid": True}
    except json.JSONDecodeError as e:
        return {"error": str(e), "valid": False}

if __name__ == "__main__":
    print(json.dumps(main(json.load(sys.stdin)), ensure_ascii=False))
```

---

## パラメータの型について

`parameters` は [JSON Schema](https://json-schema.org/) 形式で記述します。

| 型 | YAML | Claude への伝わり方 |
|---|---|---|
| 文字列 | `type: string` | テキストを期待 |
| 整数 | `type: integer` | 整数値を期待 |
| 小数 | `type: number` | 数値を期待 |
| 真偽値 | `type: boolean` | true/false を期待 |
| 配列 | `type: array` | リストを期待 |
| オブジェクト | `type: object` | 辞書を期待 |

```yaml
parameters:
  type: object
  properties:
    name:
      type: string
      description: "名前"
    count:
      type: integer
      description: "繰り返し回数"
      default: 1              # デフォルト値（Claude へのヒントになる）
    tags:
      type: array
      items:
        type: string
      description: "タグのリスト"
  required:
    - name                    # 必須パラメータ
```

---

## エラーハンドリング

スクリプト内でエラーが起きた場合、runner は自動的にキャプチャして Claude に返します。

```python
# 例外を上げると stderr がそのまま返る
raise ValueError("入力が不正です: ...")

# または JSON でエラーを返す（より丁寧な対応）
return {"error": "入力が不正です", "detail": str(e)}
```

---

## 単体テスト

Claude Desktop を経由せずにスクリプト単体でテストできます。

```bash
# 基本テスト
echo '{"input_text": "hello world"}' | python scripts/your_tool.py

# ファイルから入力
cat test_input.json | python scripts/your_tool.py

# venv を使っている場合
echo '{"input_text": "test"}' | .venv/bin/python scripts/your_tool.py
```

---

## チェックリスト

スクリプトを追加したら確認してください。

- [ ] `scripts/` に `.yaml` と `.py` のファイル名（拡張子なし）が一致している
- [ ] YAML の `name` フィールドが他のツールと重複していない
- [ ] `description` が何をするツールか明確に説明している
- [ ] `parameters.required` に必須パラメータが列挙されている
- [ ] スクリプトが `json.load(sys.stdin)` で入力を受け取っている
- [ ] スクリプトが `print(json.dumps(...))` で出力している
- [ ] 単体テストで正しい JSON が返ってくることを確認した
- [ ] ネットワークが必要なら `docker.network: bridge` を追加した
