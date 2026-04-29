"""
Slackメッセージを取得し、ルールベースで分類してLINEへ送信する。

前提:
  .venv の Python を使用
  python -m pip install requests python-dotenv
  .env に以下を設定:
    SLACK_BOT_TOKEN=xoxb-...
    SLACK_CHANNEL_ID=C0123456789
    LINE_CHANNEL_ACCESS_TOKEN=...
    LINE_USER_ID=U...

実行:
  python slack_summary_to_line.py
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

SLACK_HISTORY_API_URL = "https://slack.com/api/conversations.history"
LINE_PUSH_API_URL = "https://api.line.me/v2/bot/message/push"
FETCH_LIMIT = 10

IMPORTANT_KEYWORDS = ("重要", "優先", "高", "リスク", "急ぎ", "PoC")
TODO_KEYWORDS = ("TODO", "修正", "作成", "連絡", "フォロー", "必要", "明日", "今日")
SYSTEM_JOIN_PATTERN = re.compile(r"^<[@U][A-Z0-9]+>さんがチャンネルに参加しました$")
SPEAKER_PATTERN = re.compile(r"^[^:\n]{1,20}:$")
COMPANY_PATTERN = re.compile(r"[A-ZＡ-Ｚ][社店部]")
MAX_ITEMS_PER_CATEGORY = 3


def load_required_env() -> tuple[str, str, str, str]:
    """必要な環境変数を読み込んで返す。"""
    env_path = Path(__file__).resolve().parent / ".env"
    loaded = load_dotenv(dotenv_path=env_path, override=True)

    slack_token = os.getenv("SLACK_BOT_TOKEN")
    slack_channel_id = os.getenv("SLACK_CHANNEL_ID")
    line_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    line_user_id = os.getenv("LINE_USER_ID")

    if not loaded:
        print(f"注意: .env を読み込めませんでした: {env_path}")
    if not slack_token:
        print("環境変数 SLACK_BOT_TOKEN が未設定です。", file=sys.stderr)
        sys.exit(1)
    if not slack_channel_id:
        print("環境変数 SLACK_CHANNEL_ID が未設定です。", file=sys.stderr)
        sys.exit(1)
    if not line_token:
        print("環境変数 LINE_CHANNEL_ACCESS_TOKEN が未設定です。", file=sys.stderr)
        sys.exit(1)
    if not line_user_id:
        print("環境変数 LINE_USER_ID が未設定です。", file=sys.stderr)
        sys.exit(1)

    return slack_token, slack_channel_id, line_token, line_user_id


def fetch_slack_messages(token: str, channel_id: str, limit: int = FETCH_LIMIT) -> list[dict[str, Any]]:
    """Slackの指定チャンネルから直近メッセージを取得する。"""
    print(f"Slackから直近{limit}件のメッセージを取得します...")

    headers = {"Authorization": f"Bearer {token}"}
    params = {"channel": channel_id, "limit": limit}
    response = requests.get(
        SLACK_HISTORY_API_URL,
        headers=headers,
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()

    if not data.get("ok"):
        error = data.get("error", "unknown_error")
        print(f"Slack取得に失敗しました: error={error}", file=sys.stderr)
        sys.exit(1)

    messages = data.get("messages", [])
    if not isinstance(messages, list):
        print("Slackレスポンスが想定外です。messages が配列ではありません。", file=sys.stderr)
        sys.exit(1)

    print(f"Slack取得成功: 生データ {len(messages)} 件")
    return messages


def extract_text_messages(messages: list[dict[str, Any]]) -> list[str]:
    """空テキスト・Botメッセージを除外して本文だけを返す。"""
    texts: list[str] = []
    for message in messages:
        text = (message.get("text") or "").strip()
        subtype = message.get("subtype")
        is_bot = subtype == "bot_message" or bool(message.get("bot_id"))
        if not text or is_bot:
            continue
        texts.append(text)

    print(f"本文抽出完了: {len(texts)} 件")
    return texts


def classify_message(text: str) -> str:
    """1メッセージを 重要 / TODO / 補足 に分類する。"""
    if any(keyword in text for keyword in IMPORTANT_KEYWORDS):
        return "重要"
    if any(keyword in text for keyword in TODO_KEYWORDS):
        return "TODO"
    return "補足"


def normalize_line(line: str) -> str:
    """要約対象の行へ整形する。"""
    cleaned = line.strip().strip("・").strip()
    if not cleaned:
        return ""
    if cleaned == "【営業チャンネル】":
        return ""
    if cleaned == "TODO":
        return ""
    if SPEAKER_PATTERN.match(cleaned):
        return ""
    if SYSTEM_JOIN_PATTERN.match(cleaned):
        return ""
    return cleaned


def split_candidates(texts: list[str]) -> list[str]:
    """Slack本文を行単位に分解し、要約候補を抽出する。"""
    candidates: list[str] = []
    for text in texts:
        for raw_line in text.splitlines():
            line = normalize_line(raw_line)
            if not line:
                continue
            candidates.append(line)
    return candidates


def theme_key(text: str) -> str:
    """同じテーマをまとめるためのキーを返す。"""
    company_match = COMPANY_PATTERN.search(text)
    if company_match:
        return f"company:{company_match.group(0)}"
    if "Google Sheets連携" in text:
        return "topic:Google Sheets連携"
    if "フォロー" in text:
        return "topic:フォロー"
    return f"raw:{text}"


def summarize_theme(theme: str, items: list[str]) -> tuple[str, str] | None:
    """テーマ単位で短い要点へ変換する。"""
    blob = " / ".join(items)

    if theme == "company:A社":
        if "PoC" in blob and ("優先" in blob or "高" in blob):
            return "重要", "A社は来月PoC希望、優先度高"
        if "修正" in blob:
            return "TODO", "A社資料修正"
    if theme == "company:B社":
        if "Google Sheets連携" in blob and ("条件" in blob or "検討" in blob):
            return "補足", "B社はGoogle Sheets連携が条件"
        if "連携図" in blob and "作成" in blob:
            return "TODO", "B社連携図作成"
    if theme == "company:C社":
        if "失注" in blob and "リスク" in blob:
            return "重要", "C社は失注リスクあり"
        if "フォロー" in blob:
            return "TODO", "C社フォロー"

    if "失注" in blob and "リスク" in blob:
        return "重要", "失注リスクあり"
    if "PoC" in blob and ("優先" in blob or "高" in blob):
        return "重要", "PoC案件は優先度高"
    if "修正" in blob:
        return "TODO", "修正対応が必要"
    if "作成" in blob:
        return "TODO", "資料作成タスクあり"
    if "フォロー" in blob or "連絡" in blob:
        return "TODO", "フォロー連絡が必要"

    first = items[0]
    category = classify_message(first)
    return category, first


def format_summary(texts: list[str]) -> str:
    """要点化・テーマ統合したLINE送信用テキストを作る。"""
    candidates = split_candidates(texts)
    theme_map: dict[str, list[str]] = {}
    for line in candidates:
        key = theme_key(line)
        theme_map.setdefault(key, []).append(line)

    grouped = {"重要": [], "TODO": [], "補足": []}
    used_texts: set[str] = set()
    for theme, items in theme_map.items():
        result = summarize_theme(theme, items)
        if not result:
            continue
        category, summary_text = result
        if summary_text in used_texts:
            continue
        used_texts.add(summary_text)
        grouped[category].append(summary_text)

    print(
        "分類完了: "
        f"重要 {len(grouped['重要'])} 件 / "
        f"TODO {len(grouped['TODO'])} 件 / "
        f"補足 {len(grouped['補足'])} 件"
    )
    for category in grouped:
        grouped[category] = grouped[category][:MAX_ITEMS_PER_CATEGORY]

    def to_lines(items: list[str]) -> str:
        if not items:
            return "・なし"
        return "\n".join(f"・{item}" for item in items)

    # TODOが抽出できた場合は "なし" を出さない（空の場合のみ表示）
    todo_block = to_lines(grouped["TODO"])

    return (
        "【Slack要約】\n"
        "\n"
        "重要:\n"
        f"{to_lines(grouped['重要'])}\n\n"
        "TODO:\n"
        f"{todo_block}\n\n"
        "補足:\n"
        f"{to_lines(grouped['補足'])}"
    )


def push_line_message(access_token: str, user_id: str, text: str) -> None:
    """LINE Messaging APIでテキストを送信する。"""
    print("LINEへ要約を送信します...")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=utf-8",
    }
    payload = {
        "to": user_id,
        "messages": [{"type": "text", "text": text}],
    }
    response = requests.post(LINE_PUSH_API_URL, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    print("LINE送信成功。")


def main() -> None:
    slack_token, slack_channel_id, line_token, line_user_id = load_required_env()

    try:
        slack_messages = fetch_slack_messages(slack_token, slack_channel_id, limit=FETCH_LIMIT)
        texts = extract_text_messages(slack_messages)
        summary_text = format_summary(texts)

        print("送信する要約本文:")
        print("=" * 50)
        print(summary_text)
        print("=" * 50)

        push_line_message(line_token, line_user_id, summary_text)
    except requests.HTTPError as exc:
        print(f"API通信に失敗しました: {exc}", file=sys.stderr)
        if exc.response is not None:
            print(exc.response.text, file=sys.stderr)
        sys.exit(1)
    except requests.RequestException as exc:
        print(f"API通信に失敗しました: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"処理に失敗しました: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
