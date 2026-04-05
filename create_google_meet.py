"""
Google Meet の参加リンクを生成する。

Meet 専用の「会議だけを作る」REST API は一般向けに提供されておらず、
Google が推奨している方法は Calendar API でイベントを作成し、
conferenceData（hangoutsMeet）を付与して Meet URL を取得することです。

前提（.venv を有効化したターミナルで実行）:
  python -m pip install google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2
  python create_google_meet.py

OAuth: credentials.json または client_secret_*.json（テストフォルダ）
トークン: token_calendar.json（他スクリプトの token と分離）
"""
from __future__ import annotations

import argparse
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# カレンダーにイベントを作成し Meet を付与するために必要
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


def find_credentials_file(base_dir: Path) -> Path:
    default_file = base_dir / "credentials.json"
    if default_file.exists():
        return default_file
    candidates = list(base_dir.glob("client_secret_*"))
    if candidates:
        return candidates[0]
    raise FileNotFoundError(
        "OAuth クライアント情報が見つかりません。"
        " credentials.json または client_secret_* をテストフォルダに置いてください。"
    )


def get_credentials(base_dir: Path) -> Credentials:
    token_path = base_dir / "token_calendar.json"
    credentials_path = find_credentials_file(base_dir)
    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), SCOPES
            )
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return creds


def extract_meet_uri(conference_data: dict | None) -> str | None:
    if not conference_data:
        return None
    entry_points = conference_data.get("entryPoints", [])
    for ep in entry_points:
        if ep.get("entryPointType") == "video" and ep.get("uri"):
            return ep["uri"]
    for ep in entry_points:
        if ep.get("uri"):
            return ep["uri"]
    return None


def create_meet_event(
    base_dir: Path,
    summary: str,
    duration_minutes: int,
    tz_name: str,
) -> tuple[str | None, str | None]:
    """
    カレンダーに Meet 付きイベントを作成し、(Meet URL, イベント HTML リンク) を返す。
    """
    creds = get_credentials(base_dir)
    service = build("calendar", "v3", credentials=creds)

    now = datetime.now(timezone.utc)
    end = now + timedelta(minutes=max(1, duration_minutes))

    event_body = {
        "summary": summary,
        "start": {
            "dateTime": now.isoformat().replace("+00:00", "Z"),
            "timeZone": tz_name,
        },
        "end": {
            "dateTime": end.isoformat().replace("+00:00", "Z"),
            "timeZone": tz_name,
        },
        "conferenceData": {
            "createRequest": {
                "requestId": str(uuid.uuid4()),
                "conferenceSolutionKey": {"type": "hangoutsMeet"},
            }
        },
    }

    created = (
        service.events()
        .insert(
            calendarId="primary",
            body=event_body,
            conferenceDataVersion=1,
        )
        .execute()
    )

    meet_uri = extract_meet_uri(created.get("conferenceData"))
    if not meet_uri and created.get("hangoutLink"):
        meet_uri = created["hangoutLink"]

    html_link = created.get("htmlLink")
    return meet_uri, html_link


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calendar API 経由で Google Meet 付きイベントを作成し、参加リンクを表示します。"
    )
    parser.add_argument(
        "--title",
        default="オンラインミーティング",
        help="カレンダー上のイベント名",
    )
    parser.add_argument(
        "--minutes",
        type=int,
        default=60,
        help="イベントの長さ（分）。Meet リンク自体は会議作成後も利用可能です。",
    )
    parser.add_argument(
        "--timezone",
        default="Asia/Tokyo",
        help="カレンダー表示用タイムゾーン（IANA 名、例: Asia/Tokyo）",
    )
    args = parser.parse_args()

    base_dir = Path(__file__).resolve().parent
    meet_uri, html_link = create_meet_event(
        base_dir,
        summary=args.title,
        duration_minutes=args.minutes,
        tz_name=args.timezone,
    )

    print("Google Meet 付きカレンダーイベントを作成しました。")
    if meet_uri:
        print(f"Meet 参加リンク: {meet_uri}")
    else:
        print(
            "Meet URL を取得できませんでした。"
            " Google Workspace / 利用アカウントで Meet が利用可能か、"
            " Calendar API が有効なプロジェクトか確認してください。"
        )
    if html_link:
        print(f"カレンダーイベント: {html_link}")


if __name__ == "__main__":
    main()
