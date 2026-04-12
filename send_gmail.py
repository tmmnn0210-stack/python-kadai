"""
Gmail API でメールを送信する。

前提（.venv を有効化したターミナルで実行）:
  python -m pip install google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2
  python send_gmail.py

OAuth: credentials.json または client_secret_*.json（テストフォルダ）
トークン: token_gmail.json（他スクリプトの token と分離）
"""
from __future__ import annotations

import base64
from email.message import EmailMessage
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

TO_ADDRESS = "tmmnn0210@gmail.com"
SUBJECT = "明日の予定について"
BODY = """にらさん
お疲れ様です
明日の9:30よりチームMTGがありますのでご参加のほどよろしくお願いいたします。
"""


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
    token_path = base_dir / "token_gmail.json"
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


def build_mime_message(to_addr: str, subject: str, body: str) -> str:
    msg = EmailMessage()
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def send_message(
    base_dir: Path,
    to_addr: str,
    subject: str,
    body: str,
) -> str:
    creds = get_credentials(base_dir)
    service = build("gmail", "v1", credentials=creds)
    raw = build_mime_message(to_addr, subject, body)
    sent = (
        service.users()
        .messages()
        .send(userId="me", body={"raw": raw})
        .execute()
    )
    return sent["id"]


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    message_id = send_message(base_dir, TO_ADDRESS, SUBJECT, BODY)
    print("メールを送信しました。")
    print(f"To: {TO_ADDRESS}")
    print(f"Subject: {SUBJECT}")
    print(f"Message ID: {message_id}")


if __name__ == "__main__":
    main()
