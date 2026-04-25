"""
毎朝実行して Google スプレッドシートの当日行を LINE に送る。

要件:
1. 今日の日付に一致する行を探し、D列タイトルとE列URLを取得
2. LINEへ以下形式で送信
   今日のインプット📚
   {タイトル}
   {URL}
3. 同じURLは重複送信しない
4. 今日の日付に一致する行がない場合は、その旨をLINE送信
5. エラー時はコンソールに分かりやすく表示

前提:
  python -m pip install google-api-python-client google-auth google-auth-oauthlib requests

環境変数（IDなど環境依存の値）:
  GOOGLE_SHEETS_SPREADSHEET_ID  : 必須
  GOOGLE_SHEETS_RANGE           : 任意 (既定: Sheet1!A:E)
  GOOGLE_SHEETS_DATE_COL_INDEX  : 任意 (既定: 0 = A列)
  GOOGLE_SHEETS_TITLE_COL_INDEX : 任意 (既定: 3 = D列)
  GOOGLE_SHEETS_URL_COL_INDEX   : 任意 (既定: 4 = E列)
  GOOGLE_SHEETS_TOKEN_FILE      : 任意 (既定: token_sheets.json)
  LINE_CHANNEL_ACCESS_TOKEN     : 必須
  LINE_TO_USER_ID               : 必須
  SENT_URLS_FILE                : 任意 (既定: sent_urls.txt)
"""
from __future__ import annotations

import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
LINE_PUSH_API = "https://api.line.me/v2/bot/message/push"

DEFAULT_RANGE = "'音声・動画アウトプット'!A:E"
DEFAULT_DATE_COL_INDEX = 1
DEFAULT_TITLE_COL_INDEX = 3
DEFAULT_URL_COL_INDEX = 4
DEFAULT_TOKEN_FILE = "token_sheets.json"
DEFAULT_SENT_URLS_FILE = "sent_urls.txt"


def find_credentials_file(base_dir: Path) -> Path:
    default_file = base_dir / "credentials.json"
    if default_file.exists():
        return default_file
    candidates = list(base_dir.glob("client_secret_*"))
    if candidates:
        # 複数ある場合は更新日時が新しいものを優先
        return max(candidates, key=lambda p: p.stat().st_mtime)
    raise FileNotFoundError(
        "OAuth クライアント情報が見つかりません。"
        " credentials.json または client_secret_* を配置してください。"
    )


def get_sheets_service(base_dir: Path, token_file_name: str) -> object:
    token_path = base_dir / token_file_name
    credentials_path = find_credentials_file(base_dir)
    print(f"INFO: OAuth クライアント情報 = {credentials_path.name}")
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

    return build("sheets", "v4", credentials=creds)


def parse_sheet_date(value: str) -> date | None:
    raw = value.strip()
    if not raw:
        return None

    # 全角記号や曜日表記を吸収して、日付の本体だけを残す
    normalized = (
        raw.replace("／", "/")
        .replace("－", "-")
        .replace("年", "/")
        .replace("月", "/")
        .replace("日", "")
    )
    normalized = re.sub(r"\s+", "", normalized)
    normalized = re.sub(r"\(.*?\)|（.*?）", "", normalized)
    normalized = normalized.strip("/")

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%m/%d/%Y", "%m/%d"):
        try:
            parsed = datetime.strptime(normalized, fmt)
            if fmt == "%m/%d":
                return date(date.today().year, parsed.month, parsed.day)
            return parsed.date()
        except ValueError:
            continue

    # 例: 4/25(土), 4-25, 4.25 などから月日を救済
    mmdd_match = re.search(r"(\d{1,2})[\/\-.](\d{1,2})", normalized)
    if mmdd_match:
        month = int(mmdd_match.group(1))
        day = int(mmdd_match.group(2))
        try:
            return date(date.today().year, month, day)
        except ValueError:
            return None

    return None


def get_cell(row: list[str], idx: int) -> str:
    if idx < 0:
        return ""
    return row[idx].strip() if idx < len(row) and row[idx] else ""


def read_sent_urls(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def append_sent_urls(path: Path, urls: list[str]) -> None:
    if not urls:
        return
    with path.open("a", encoding="utf-8") as f:
        for u in urls:
            f.write(f"{u}\n")


def push_text_message(access_token: str, to_user_id: str, text: str) -> None:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    payload = {"to": to_user_id, "messages": [{"type": "text", "text": text}]}
    response = requests.post(LINE_PUSH_API, headers=headers, json=payload, timeout=30)
    response.raise_for_status()


def build_daily_message(title: str, url: str) -> str:
    return f"今日のインプット📚\n{title}\n{url}"


def main() -> None:
    base_dir = Path(__file__).resolve().parent

    spreadsheet_id = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")
    line_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    line_to_user_id = os.getenv("LINE_TO_USER_ID")

    if not spreadsheet_id:
        print("エラー: 環境変数 GOOGLE_SHEETS_SPREADSHEET_ID が未設定です。", file=sys.stderr)
        sys.exit(1)
    if not line_token:
        print("エラー: 環境変数 LINE_CHANNEL_ACCESS_TOKEN が未設定です。", file=sys.stderr)
        sys.exit(1)
    if not line_to_user_id:
        print("エラー: 環境変数 LINE_TO_USER_ID が未設定です。", file=sys.stderr)
        sys.exit(1)

    sheet_range = os.getenv("GOOGLE_SHEETS_RANGE", DEFAULT_RANGE)
    date_col_idx = int(os.getenv("GOOGLE_SHEETS_DATE_COL_INDEX", str(DEFAULT_DATE_COL_INDEX)))
    title_col_idx = int(
        os.getenv("GOOGLE_SHEETS_TITLE_COL_INDEX", str(DEFAULT_TITLE_COL_INDEX))
    )
    url_col_idx = int(os.getenv("GOOGLE_SHEETS_URL_COL_INDEX", str(DEFAULT_URL_COL_INDEX)))
    token_file = os.getenv("GOOGLE_SHEETS_TOKEN_FILE", DEFAULT_TOKEN_FILE)
    sent_urls_file = Path(os.getenv("SENT_URLS_FILE", str(base_dir / DEFAULT_SENT_URLS_FILE)))

    today = date.today()
    print(f"INFO: 本日の日付 = {today.isoformat()}")
    print(f"INFO: 取得レンジ = {sheet_range}")
    print(f"INFO: 日付列インデックス = {date_col_idx}（A列=0, B列=1 ...）")
    print(f"INFO: タイトル列インデックス = {title_col_idx}（D列=3）")
    print(f"INFO: URL列インデックス = {url_col_idx}（E列=4）")

    try:
        sheets = get_sheets_service(base_dir, token_file)
        values = (
            sheets.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=sheet_range)
            .execute()
            .get("values", [])
        )
    except Exception as exc:
        print(f"エラー: Google Sheets の読み取りに失敗しました: {exc}", file=sys.stderr)
        sys.exit(1)

    if not values:
        msg = "今日の日付に一致する行がありませんでした。（シートが空です）"
        try:
            push_text_message(line_token, line_to_user_id, msg)
        except Exception as exc:
            print(f"エラー: LINE送信に失敗しました: {exc}", file=sys.stderr)
            sys.exit(1)
        print("INFO: シートが空のため通知を送信しました。")
        return

    sent_urls = read_sent_urls(sent_urls_file)
    new_sent_urls: list[str] = []
    matched_count = 0
    sent_count = 0

    for row_idx, row in enumerate(values, start=1):
        row_date = parse_sheet_date(get_cell(row, date_col_idx))
        if row_date != today:
            continue

        matched_count += 1
        title = get_cell(row, title_col_idx) or "(タイトルなし)"
        url = get_cell(row, url_col_idx)

        if not url:
            print(
                f"WARN: {row_idx}行目はURL(E列)が空のためスキップしました。",
                file=sys.stderr,
            )
            continue
        if url in sent_urls or url in new_sent_urls:
            print(f"INFO: 重複URLのため送信スキップ: {url}")
            continue

        message = build_daily_message(title, url)
        try:
            push_text_message(line_token, line_to_user_id, message)
            new_sent_urls.append(url)
            sent_count += 1
            print(f"INFO: LINE送信成功（{row_idx}行目）")
        except requests.HTTPError as exc:
            print(f"エラー: LINE APIエラーで送信失敗（{row_idx}行目）: {exc}", file=sys.stderr)
            if exc.response is not None:
                print(f"レスポンス: {exc.response.text}", file=sys.stderr)
        except Exception as exc:
            print(f"エラー: LINE送信失敗（{row_idx}行目）: {exc}", file=sys.stderr)

    if sent_count > 0:
        append_sent_urls(sent_urls_file, new_sent_urls)
        print(f"INFO: {sent_count} 件送信し、重複防止ファイルを更新しました。")
    elif matched_count == 0:
        # 一致しなかった時に原因を切り分けやすくするため先頭数行を表示
        preview_count = min(5, len(values))
        for i in range(preview_count):
            preview_raw = get_cell(values[i], date_col_idx)
            preview_parsed = parse_sheet_date(preview_raw)
            print(
                f"DEBUG: {i + 1}行目 日付セル='{preview_raw}' -> 解析結果={preview_parsed}",
                file=sys.stderr,
            )
        msg = "今日の日付に一致する行がありませんでした。"
        try:
            push_text_message(line_token, line_to_user_id, msg)
            print("INFO: 一致行なしの通知を送信しました。")
        except Exception as exc:
            print(f"エラー: 一致行なし通知のLINE送信に失敗しました: {exc}", file=sys.stderr)
            sys.exit(1)
    else:
        print("INFO: 当日行はありましたが、重複またはURL空欄のため新規送信はありません。")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"致命的エラー: {exc}", file=sys.stderr)
        sys.exit(1)
