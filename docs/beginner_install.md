# 初心者向けセットアップガイド

コピペで進められるように、順番通りに実行してください。

---

## STEP 1 リポジトリをクローンする

```bash
git clone https://github.com/zephel01/mcp-wrapper.git
cd mcp-wrapper
```

---

## STEP 2 セットアップスクリプトを実行する

```bash
bash setup.sh
```

これ 1 コマンドで以下が自動で行われます。

- `.venv/` に Python 仮想環境を作成
- `mcp`, `pyyaml`, `docker` などの必要パッケージをインストール
- Docker が使える場合はサンドボックスイメージをビルド

---

## STEP 3 Claude Desktop に設定を追加する

`setup.sh` の最後に以下のような JSON が表示されます。

```json
"python-scripts": {
  "command": "/path/to/mcp-wrapper/.venv/bin/python",
  "args": ["/path/to/mcp-wrapper/server.py"]
}
```

表示された内容を `~/Library/Application Support/Claude/claude_desktop_config.json` の `mcpServers` にコピペします。

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

> **パスは自分の環境に合わせてください。** `setup.sh` が正しいパスを表示してくれるので、そのままコピペすれば OK です。

Claude Desktop を再起動して設定を反映させます。

---

## STEP 4 スクリプトを追加する

`scripts/` フォルダに `.yaml` と `.py` の 2 ファイルをセットで置きます。
ファイル名（拡張子なし）は必ず揃えてください。

```
scripts/
├── my_tool.yaml   ← ツールの定義
└── my_tool.py     ← 処理の中身
```

### 例: crawl4ai を使うスクリプト

**① `scripts/my_crawl.yaml` を作成**

```yaml
name: my_crawl
description: "指定した URL のページ内容をテキストで取得する"
timeout: 60
packages:
  - crawl4ai          # ← pip install されるパッケージを書く

docker:
  network: bridge     # ← ネットワークアクセスが必要なので必須

parameters:
  type: object
  properties:
    url:
      type: string
      description: "取得する URL（https:// から始まる形式）"
  required:
    - url
```

**② `scripts/my_crawl.py` を作成**

```python
import json
import sys

def main(params):
    from crawl4ai import WebCrawler
    crawler = WebCrawler()
    crawler.warmup()
    result = crawler.run(url=params["url"])
    return {"content": result.markdown}

if __name__ == "__main__":
    params = json.load(sys.stdin)
    print(json.dumps(main(params), ensure_ascii=False))
```

ファイルを置いたら **Claude Desktop の再起動は不要**です。自動で認識されます。

---

## STEP 5 動作確認する

Claude Desktop を開いて「〇〇のページを取得して」などと話しかけると `my_crawl` ツールが呼ばれます。

ターミナルから単体テストもできます。

```bash
echo '{"url": "https://example.com"}' | .venv/bin/python scripts/my_crawl.py
```

正しく JSON が返ってくれば成功です。

---

## よくあるトラブル

| 症状 | 対処 |
|---|---|
| `command not found: python` | `python3` に変えて試す |
| パッケージが見つからないエラー | `bash setup.sh` を再実行する |
| ネットワークエラー | YAML に `docker: {network: bridge}` が書いてあるか確認 |
| ツールが Claude に表示されない | `.yaml` と `.py` のファイル名（拡張子なし）が一致しているか確認 |
