"""
hello.py - 動作確認用サンプルスクリプト

入力: JSON (stdin)
  {"name": "Hideki", "greeting": "こんにちは"}

出力: JSON (stdout)
  {"message": "こんにちは, Hideki!"}
"""

import json
import sys


def main(params: dict) -> dict:
    name: str = params["name"]
    greeting: str = params.get("greeting", "Hello")
    return {"message": f"{greeting}, {name}!"}


if __name__ == "__main__":
    params = json.load(sys.stdin)
    result = main(params)
    print(json.dumps(result, ensure_ascii=False))
