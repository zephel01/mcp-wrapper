"""
web_fetch.py - URL のコンテンツ取得スクリプト

入力: JSON (stdin)
  {
    "url": "https://example.com",
    "text_only": true,    // 省略可（デフォルト: true）
    "max_chars": 3000     // 省略可（デフォルト: 3000）
  }

出力: JSON (stdout)
  {
    "url": "...",
    "status_code": 200,
    "content_type": "text/html",
    "content": "...",
    "truncated": false
  }

注意: このスクリプトは docker.network = bridge で実行される（web_fetch.yaml 参照）
"""

import json
import sys


def main(params: dict) -> dict:
    import requests
    from bs4 import BeautifulSoup

    url: str = params["url"]
    text_only: bool = params.get("text_only", True)
    max_chars: int = int(params.get("max_chars", 3000))

    try:
        resp = requests.get(
            url,
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0 (compatible; mcp-wrapper/1.0)"},
            allow_redirects=True,
        )
        resp.raise_for_status()
    except requests.exceptions.Timeout:
        return {"error": "Request timed out"}
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

    content_type: str = resp.headers.get("content-type", "")

    if text_only and "html" in content_type:
        soup = BeautifulSoup(resp.text, "html.parser")
        # スクリプト・スタイルを除去
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        content = soup.get_text(separator="\n", strip=True)
        # 連続する空行を圧縮
        lines = [ln for ln in content.splitlines() if ln.strip()]
        content = "\n".join(lines)
    else:
        content = resp.text

    truncated = len(content) > max_chars
    return {
        "url": url,
        "status_code": resp.status_code,
        "content_type": content_type,
        "content": content[:max_chars],
        "truncated": truncated,
        "total_chars": len(content),
    }


if __name__ == "__main__":
    params = json.load(sys.stdin)
    result = main(params)
    print(json.dumps(result, ensure_ascii=False))
