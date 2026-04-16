"""
my_crawl.py - URL のコンテンツを Markdown で取得するスクリプト

入力: JSON (stdin)
  {
    "url": "https://example.com",
    "max_chars": 8000    // 省略可（デフォルト: 8000）
  }

出力: JSON (stdout)
  {
    "content": "...",
    "truncated": false
  }

セキュリティ:
  - プライベート IP / ループバック / リンクローカルへのアクセスをブロック（SSRF対策）
  - file:// / ftp:// など http(s) 以外のスキームをブロック
  - 認証情報（user:pass@host）を含む URL をブロック
  - DNS 解決後のアドレスも検証（DNS リバインディング対策）
"""

import asyncio
import ipaddress
import json
import re
import socket
import sys
from urllib.parse import urlparse


# ── SSRF ガード ────────────────────────────────────────────────

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),       # ループバック
    ipaddress.ip_network("169.254.0.0/16"),     # リンクローカル
    ipaddress.ip_network("100.64.0.0/10"),      # 共有アドレス空間
    ipaddress.ip_network("::1/128"),            # IPv6 ループバック
    ipaddress.ip_network("fc00::/7"),           # IPv6 ユニークローカル
    ipaddress.ip_network("fe80::/10"),          # IPv6 リンクローカル
]


def _is_private_ip(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
        return any(ip in net for net in _PRIVATE_NETWORKS)
    except ValueError:
        return False


def validate_url(url: str) -> None:
    """URL の安全性を検証。問題があれば ValueError を送出する。"""
    parsed = urlparse(url)

    # スキームチェック
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Blocked scheme: {parsed.scheme!r}. Only http/https is allowed.")

    # 認証情報チェック
    if parsed.username or parsed.password:
        raise ValueError("Blocked: URL must not contain credentials (user:pass@host).")

    # ホスト名チェック
    host = parsed.hostname
    if not host:
        raise ValueError("Blocked: URL has no hostname.")

    # IP リテラルの場合は即座に検証
    try:
        ip_obj = ipaddress.ip_address(host)
        if _is_private_ip(str(ip_obj)):
            raise ValueError(f"Blocked: IP address {host!r} is in a private/reserved range.")
    except ValueError as e:
        # ip_address() が失敗 → ホスト名（ドメイン）→ DNS 解決して検証
        if "Blocked" in str(e):
            raise
        try:
            infos = socket.getaddrinfo(host, None)
        except socket.gaierror as dns_err:
            raise ValueError(f"DNS resolution failed for {host!r}: {dns_err}") from dns_err

        for info in infos:
            resolved_ip = info[4][0]
            if _is_private_ip(resolved_ip):
                raise ValueError(
                    f"Blocked: {host!r} resolves to private IP {resolved_ip!r}."
                )


# ── クロール本体 ──────────────────────────────────────────────


def main(params: dict) -> dict:
    url: str = params["url"]
    max_chars: int = int(params.get("max_chars", 8000))

    # SSRF チェック（クロール前に実行）
    try:
        validate_url(url)
    except ValueError as e:
        return {"error": str(e)}

    from crawl4ai import AsyncWebCrawler, HTTPCrawlerConfig
    from crawl4ai.async_crawler_strategy import AsyncHTTPCrawlerStrategy

    async def _crawl(u: str) -> dict:
        strategy = AsyncHTTPCrawlerStrategy(browser_config=HTTPCrawlerConfig())
        async with AsyncWebCrawler(crawler_strategy=strategy) as crawler:
            result = await crawler.arun(url=u)
            raw: str = result.markdown.raw_markdown or ""
            truncated = len(raw) > max_chars
            return {
                "content": raw[:max_chars],
                "truncated": truncated,
                "total_chars": len(raw),
            }

    return asyncio.run(_crawl(url))


if __name__ == "__main__":
    params = json.load(sys.stdin)
    print(json.dumps(main(params), ensure_ascii=False))
