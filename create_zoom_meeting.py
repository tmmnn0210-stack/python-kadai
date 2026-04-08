"""
Zoom Server-to-Server OAuth で会議を作成し、
会議 ID / パスコード / 参加リンクを表示するスクリプト。

使い方（.venv 前提）:
  ./.venv/bin/python create_zoom_meeting.py

必要な環境変数:
  ZOOM_ACCOUNT_ID
  ZOOM_CLIENT_ID
  ZOOM_CLIENT_SECRET
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


TOKEN_URL = "https://zoom.us/oauth/token"
CREATE_MEETING_URL = "https://api.zoom.us/v2/users/me/meetings"


def get_env_or_raise(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"環境変数 {name} が未設定です。")
    return value


def fetch_access_token(account_id: str, client_id: str, client_secret: str) -> str:
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("utf-8")
    query = urlencode({"grant_type": "account_credentials", "account_id": account_id})
    req = Request(
        f"{TOKEN_URL}?{query}",
        method="POST",
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    with urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    token = data.get("access_token")
    if not token:
        raise RuntimeError("Zoom のアクセストークン取得に失敗しました。")
    return token


def create_meeting(
    access_token: str,
    topic: str,
    start_time_iso: str,
    timezone_name: str,
    duration_minutes: int,
) -> dict:
    body = {
        "topic": topic,
        "type": 2,  # scheduled meeting
        "start_time": start_time_iso,
        "duration": duration_minutes,
        "timezone": timezone_name,
        "settings": {
            "join_before_host": False,
            "waiting_room": True,
            "mute_upon_entry": True,
        },
    }
    req = Request(
        CREATE_MEETING_URL,
        method="POST",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
    )
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def parse_start_time(value: str, timezone_name: str) -> str:
    # "2026-04-09 19:00" 形式を期待し、タイムゾーン付き ISO8601 を作る
    dt = datetime.strptime(value, "%Y-%m-%d %H:%M")
    dt = dt.replace(tzinfo=ZoneInfo(timezone_name))
    return dt.isoformat()


def main() -> None:
    parser = argparse.ArgumentParser(description="Zoom 会議を作成して情報を表示します。")
    parser.add_argument("--topic", default="定例ミーティング", help="会議タイトル")
    parser.add_argument(
        "--start",
        default="2026-04-09 19:00",
        help='開始日時（例: "2026-04-09 19:00"）',
    )
    parser.add_argument("--timezone", default="Asia/Tokyo", help="タイムゾーン名")
    parser.add_argument("--duration", type=int, default=60, help="会議時間（分）")
    args = parser.parse_args()

    try:
        account_id = get_env_or_raise("ZOOM_ACCOUNT_ID")
        client_id = get_env_or_raise("ZOOM_CLIENT_ID")
        client_secret = get_env_or_raise("ZOOM_CLIENT_SECRET")

        start_time_iso = parse_start_time(args.start, args.timezone)
        token = fetch_access_token(account_id, client_id, client_secret)
        meeting = create_meeting(
            access_token=token,
            topic=args.topic,
            start_time_iso=start_time_iso,
            timezone_name=args.timezone,
            duration_minutes=args.duration,
        )

        meeting_id = meeting.get("id")
        password = meeting.get("password")
        join_url = meeting.get("join_url")
        start_url = meeting.get("start_url")

        print("Zoom 会議を作成しました。")
        print(f"Meeting ID: {meeting_id}")
        print(f"Passcode: {password}")
        print(f"Join URL: {join_url}")
        if start_url:
            print(f"Host Start URL: {start_url}")
    except ValueError as e:
        print(f"[設定エラー] {e}", file=sys.stderr)
        sys.exit(1)
    except HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        print(f"[HTTPエラー] {e.code} {e.reason}", file=sys.stderr)
        if detail:
            print(detail, file=sys.stderr)
        sys.exit(1)
    except URLError as e:
        print(f"[通信エラー] {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[予期しないエラー] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
