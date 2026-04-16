"""
web_search.py - キーワード検索スクリプト（DuckDuckGo）

入力: JSON (stdin)
  {
    "query": "TypeScript async iterator",
    "count": 5,           // 省略可（デフォルト: 5、最大: 10）
    "region": "wt-wt"    // 省略可（デフォルト: "wt-wt" = 地域なし）
  }

出力: JSON (stdout)
  {
    "query": "...",
    "results": [
      {
        "title": "...",
        "url": "https://...",
        "description": "..."
      },
      ...
    ]
  }

注意: このスクリプトは docker.network = bridge で実行される（web_search.yaml 参照）
"""

import json
import sys


def main(params: dict) -> dict:
    from ddgs import DDGS

    query: str = params["query"]
    count: int = min(int(params.get("count", 5)), 10)
    region: str = params.get("region", "wt-wt")

    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, region=region, max_results=count):
                results.append(
                    {
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "description": r.get("body", ""),
                    }
                )
    except Exception as e:
        return {"query": query, "results": [], "error": str(e)}

    return {"query": query, "results": results}


if __name__ == "__main__":
    params = json.load(sys.stdin)
    result = main(params)
    print(json.dumps(result, ensure_ascii=False))
