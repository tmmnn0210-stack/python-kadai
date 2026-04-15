"""
Slack API で指定チャンネルへメッセージ投稿する。

前提:
  python -m pip install requests
  export SLACK_BOT_TOKEN="xoxb-..."
  export SLACK_CHANNEL_ID="C0123456789"
  python slack_post_message.py

必要スコープ:
  chat:write
"""
from __future__ import annotations

import os
import sys

import requests

SLACK_API_URL = "https://slack.com/api/chat.postMessage"
BOT_NAME = "NIRA"
MESSAGE = (
    "にらさんお疲れ様です。AI学習のMTG設定いたしました。\n"
    "あと必要な情報あれば教えてください〜"
)


def post_message(token: str, channel_id: str, text: str) -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    payload = {
        "channel": channel_id,
        "text": text,
    }

    # Bot表示名は Slack App 側の Bot 名設定が使われる（chat:write のみ想定）。
    response = requests.post(SLACK_API_URL, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Slack API error: {data.get('error', 'unknown_error')}")
    return data


def main() -> None:
    token = os.getenv("SLACK_BOT_TOKEN")
    channel_id = os.getenv("SLACK_CHANNEL_ID")
    if not token:
        print("環境変数 SLACK_BOT_TOKEN が未設定です。", file=sys.stderr)
        sys.exit(1)
    if not channel_id:
        print("環境変数 SLACK_CHANNEL_ID が未設定です。", file=sys.stderr)
        sys.exit(1)

    try:
        result = post_message(token, channel_id, MESSAGE)
    except Exception as exc:
        print(f"メッセージ送信に失敗しました: {exc}", file=sys.stderr)
        sys.exit(1)

    print("Slackメッセージを送信しました。")
    print(f"channel_id: {channel_id}")
    print(f"bot: {BOT_NAME}")
    print(f"ts: {result.get('ts')}")


if __name__ == "__main__":
    main()
