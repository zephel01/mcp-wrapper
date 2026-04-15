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

これ 1 コマンドで `.venv/` への仮想環境作成・基本パッケージのインストール・Docker イメージのビルドが自動で行われます。

---

## STEP 3 crawl4ai をインストールする

`crawl4ai` は `setup.sh` に含まれていないため、別途インストールします。

```bash
source .venv/bin/activate
pip install -U crawl4ai
```

crawl4ai には Chromium（ブラウザ）を使うモードと、使わない HTTP モードの 2 種類があります。このガイドでは Chromium 不要の HTTP モードを使います。

---

## STEP 4 Claude Desktop に設定を追加する

`setup.sh` の最後に表示された JSON を `~/Library/Application Support/Claude/claude_desktop_config.json` の `mcpServers` にコピペします。

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

パスは `setup.sh` が正しい値を表示してくれるので、そのままコピペすれば OK です。コピペ後は Claude Desktop を再起動してください。

---

## STEP 5 スクリプトを追加する

`scripts/` フォルダに `.yaml` と `.py` の 2 ファイルをセットで置きます。ファイル名（拡張子なし）は必ず揃えてください。

### `scripts/my_crawl.yaml`

```yaml
name: my_crawl
description: "指定した URL のページ内容を Markdown テキストで取得する"
timeout: 60
packages: []

docker:
  network: bridge

parameters:
  type: object
  properties:
    url:
      type: string
      description: "取得する URL（https:// から始まる形式）"
  required:
    - url
```

`packages` は空にします。`crawl4ai` は STEP 3 で venv に直接インストール済みのため、ここに書く必要はありません。

`docker: network: bridge` はネットワークアクセスに必要です。

### `scripts/my_crawl.py`

```python
import asyncio
import json
import sys

from crawl4ai import AsyncWebCrawler, HTTPCrawlerConfig
from crawl4ai.async_crawler_strategy import AsyncHTTPCrawlerStrategy


def main(params):
    async def _crawl(url):
        strategy = AsyncHTTPCrawlerStrategy(
            browser_config=HTTPCrawlerConfig()
        )
        async with AsyncWebCrawler(crawler_strategy=strategy) as crawler:
            result = await crawler.arun(url=url)
            return {"content": result.markdown.raw_markdown}

    return asyncio.run(_crawl(params["url"]))


if __name__ == "__main__":
    params = json.load(sys.stdin)
    print(json.dumps(main(params), ensure_ascii=False))
```

`AsyncHTTPCrawlerStrategy` を使うと Chromium（ブラウザ）が不要になります。`aiohttp` だけで動く軽量モードです。

ファイルを置いたら Claude Desktop の再起動は不要です。自動で認識されます。

---

## STEP 6 Docker の設定を確認する

スクリプトは Docker コンテナ内で実行されます（Docker がない場合は自動で subprocess に切り替わります）。

### Docker が使えるか確認する

```bash
docker --version
```

バージョンが表示されれば OK です。表示されない場合は Docker がインストールされていません。

### Docker モード / subprocess モードを切り替える

`config.yaml` で切り替えます。

```yaml
runner:
  use_docker: true   # true: Docker で実行（推奨）
                     # false: subprocess で実行（Docker 不要）
```

Docker がない環境では `use_docker: false` にしてください。

### Docker イメージをビルドする（初回のみ）

`sandbox/Dockerfile` には `crawl4ai` と `aiohttp` があらかじめ含まれています。以下でビルドします。

```bash
docker build -t mcp-sandbox ./sandbox
```

`config.yaml` はすでに `mcp-sandbox` を使う設定になっています。ビルド後すぐに使えます。

```yaml
runner:
  docker:
    default_image: "mcp-sandbox"
```

ビルドに成功しているか確認：

```bash
docker images mcp-sandbox
```

### Docker 経由でスクリプトを直接テストする

**ビルド前（素の Python イメージ）**

毎回 `pip install` が走るため初回は数十秒かかります。

```bash
echo '{"url": "https://example.com"}' | docker run --rm -i \
  -v "$(pwd)/scripts/my_crawl.py:/sandbox/script.py:ro" \
  --network bridge \
  python:3.12-slim \
  sh -c "pip install -q crawl4ai aiohttp && python /sandbox/script.py"
```

```
pip install crawl4ai aiohttp ...  ← 毎回ここで数十秒かかる
[INIT].... → Crawl4AI 0.8.6
[FETCH]... ↓ https://example.com  0.1s
```

**ビルド後（mcp-sandbox イメージ）**

`crawl4ai` がイメージに焼き込まれているので `pip install` が不要になり、すぐに実行が始まります。

```bash
echo '{"url": "https://example.com"}' | docker run --rm -i \
  -v "$(pwd)/scripts/my_crawl.py:/sandbox/script.py:ro" \
  --network bridge \
  mcp-sandbox \
  python /sandbox/script.py
```

```
[INIT].... → Crawl4AI 0.8.6       ← すぐここから始まる
[FETCH]... ↓ https://example.com  0.1s
```

runner.py も `config.yaml` の `default_image: "mcp-sandbox"` を読んで同じコマンドを組み立てます。つまり **ビルドさえすれば MCP 経由でも自動的に速くなります**。

---

## STEP 7 MCP 経由で動作確認する

### MCP と Docker の関係

MCP と Docker を「手動でつなぐ」操作は不要です。以下の流れで自動的につながります。

```
Claude Desktop
  ↓ MCP (stdio)
server.py         ← MCP のエントリーポイント
  ↓
runner.py         ← Docker SDK を呼び出す
  ↓
Docker デーモン   ← ローカルで起動している必要あり
  ↓
コンテナ内でスクリプト実行
```

Docker デーモンが起動していて `config.yaml` の `use_docker: true` になっていれば、スクリプトは自動的にコンテナ内で実行されます。

### MCP Inspector で GUI テストする

Claude Desktop を使わずに MCP ツールをブラウザから呼び出してテストできます。

```bash
npx @modelcontextprotocol/inspector .venv/bin/python server.py
```

ブラウザが開き、ツール一覧の確認・引数の入力・実行結果の確認がすべて GUI でできます。

### コマンドラインで直接テストする（Docker なし）

Docker を使わずに venv 直接で確認する場合：

```bash
echo '{"url": "https://example.com"}' | .venv/bin/python scripts/my_crawl.py
```

JSON が返ってくれば成功です。

---

## よくあるトラブル

| 症状 | 対処 |
|---|---|
| `ImportError: cannot import name 'WebCrawler'` | スクリプトが古い。`my_crawl.py` を上記のコードで上書きする |
| `command not found: python` | `python3` に変えて試す |
| `Executable doesn't exist` | `my_crawl.py` が `AsyncHTTPCrawlerStrategy` を使っているか確認する |
| ネットワークエラー | YAML に `docker: network: bridge` があるか確認する |
| ツールが Claude に表示されない | `.yaml` と `.py` のファイル名（拡張子なし）が一致しているか確認する |
