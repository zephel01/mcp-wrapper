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
