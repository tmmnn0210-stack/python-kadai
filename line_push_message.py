"""
LINE Messaging API で Push メッセージを送る。

前提:
  python -m pip install requests
  export LINE_CHANNEL_ACCESS_TOKEN="..."  # LINE Developers のチャネルアクセストークン（長期）
  python line_push_message.py

任意:
  export LINE_TO_USER_ID="U..."           # 送信先ユーザーID（省略時は既定）
  export LINE_PUSH_MESSAGE="送りたい本文"  # 省略時は既定の挨拶

LINE Developers:
  https://developers.line.biz/console/
  チャネル種別「Messaging API」でチャネルアクセストークン（長期）を発行し、
  友だち追加済みのユーザーにのみ Push 可能です。
"""
from __future__ import annotations

import os
import sys

import requests

LINE_PUSH_API = "https://api.line.me/v2/bot/message/push"

# 送信先（友だち追加済みユーザーの userId）。環境変数 LINE_TO_USER_ID で上書き可。
DEFAULT_TO_USER_ID = "U9dec80a688981a3e2369e9a3fa8e1357"
DEFAULT_MESSAGE = "おはようございます！"


def push_text_message(access_token: str, to_user_id: str, text: str) -> None:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    payload = {
        "to": to_user_id,
        "messages": [{"type": "text", "text": text}],
    }
    response = requests.post(LINE_PUSH_API, headers=headers, json=payload, timeout=30)
    response.raise_for_status()


def main() -> None:
    token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    if not token:
        print(
            "環境変数 LINE_CHANNEL_ACCESS_TOKEN が未設定です。\n"
            "LINE Developers コンソールで Messaging API チャネルの "
            "チャネルアクセストークン（長期）を設定してください。",
            file=sys.stderr,
        )
        sys.exit(1)

    to_user_id = os.getenv("LINE_TO_USER_ID", DEFAULT_TO_USER_ID)
    message = os.getenv("LINE_PUSH_MESSAGE", DEFAULT_MESSAGE)

    try:
        push_text_message(token, to_user_id, message)
    except requests.HTTPError as exc:
        print(f"LINE Push 送信に失敗しました: {exc}", file=sys.stderr)
        if exc.response is not None:
            print(exc.response.text, file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"LINE Push 送信に失敗しました: {exc}", file=sys.stderr)
        sys.exit(1)

    print("LINE メッセージを送信しました。")
    print(f"to: {to_user_id}")


if __name__ == "__main__":
    main()
