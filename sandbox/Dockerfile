# sandbox/Dockerfile
# スクリプト実行用のセキュアなベースイメージ
#
# 使い方:
#   docker build -t mcp-sandbox ./sandbox
#   # config.yaml の docker.default_image を "mcp-sandbox" に変更する
#
# このイメージの特徴:
#   - 非 root ユーザー (uid=1000) で実行
#   - 不要なシステムツールを排除
#   - /sandbox のみ書き込み可能（runner.py が tmpfs でマウント）

FROM python:3.12-slim

# セキュリティ: 非 root ユーザーを作成
RUN useradd -m -u 1000 -s /bin/sh sandbox

# 作業ディレクトリ
RUN mkdir -p /sandbox && chown sandbox:sandbox /sandbox
WORKDIR /sandbox

# pip を最新化（イメージビルド時のみ）
RUN pip install --no-cache-dir --upgrade pip

# よく使うライブラリをプリインストール（任意）
# ここに追加すると各スクリプト実行時のインストール時間を節約できる
# RUN pip install --no-cache-dir pandas requests beautifulsoup4

# 非 root で実行
USER sandbox

CMD ["python", "/sandbox/script.py"]
