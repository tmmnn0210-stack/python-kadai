"""
Discord Incoming Webhook で指定チャンネルへメッセージを投稿する。

サーバー設定 → 連携サービス → ウェブフック → 新しいウェブフック で URL を取得し、
対象チャンネル（例: channel_id 1495324257490567249）用の Webhook を作成してください。

前提:
  python -m pip install requests
  export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
  python discord_post_webhook.py

任意:
  export DISCORD_NOTIFY_MESSAGE="送りたい本文"
"""
from __future__ import annotations

import os
import sys

import requests

# この Webhook が紐づく想定チャンネル（ドキュメント・ログ用。API には不要）
CHANNEL_ID = "1495324257490567249"
BOT_NAME = "Bot作成テスト"

DEFAULT_MESSAGE = (
    "【自動通知】Bot作成テストからのテスト送信です。\n"
    "Webhook 経由でこのチャンネルに届いていれば成功です。"
)


def post_webhook(webhook_url: str, content: str, username: str | None = None) -> dict:
    """Discord Incoming Webhook に JSON POST する。"""
    payload: dict = {"content": content}
    if username:
        payload["username"] = username

    response = requests.post(
        webhook_url,
        json=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        timeout=30,
    )
    response.raise_for_status()
    # 204 No Content の場合もある
    if response.status_code == 204 or not response.content:
        return {}
    try:
        return response.json()
    except ValueError:
        return {}


def main() -> None:
    # コピペで末尾にスペースが付くと 50027 Invalid Webhook Token になるため除去する
    webhook_url = (os.getenv("DISCORD_WEBHOOK_URL") or "").strip()
    if not webhook_url:
        print("環境変数 DISCORD_WEBHOOK_URL が未設定です。", file=sys.stderr)
        sys.exit(1)

    message = os.getenv("DISCORD_NOTIFY_MESSAGE", DEFAULT_MESSAGE)

    try:
        post_webhook(webhook_url, message, username=BOT_NAME)
    except requests.HTTPError as exc:
        print(f"Discord Webhook 送信に失敗しました: {exc}", file=sys.stderr)
        if exc.response is not None:
            print(exc.response.text, file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Discord Webhook 送信に失敗しました: {exc}", file=sys.stderr)
        sys.exit(1)

    print("Discord へ通知を送信しました。")
    print(f"channel_id (想定): {CHANNEL_ID}")
    print(f"表示名 (username): {BOT_NAME}")


if __name__ == "__main__":
    main()
