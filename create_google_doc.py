"""
Google Docs API で新規ドキュメントを作成し、指定テキストを挿入する。
OAuth: テストフォルダの credentials.json または client_secret_*.json
トークン: token_docs.json（Drive 用 token.json と分離）
"""
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ドキュメントの作成・編集に必要なスコープ
SCOPES = ["https://www.googleapis.com/auth/documents"]

# ドキュメントに挿入する本文
DOC_BODY_TEXT = """うちの猫が最高にかわいい理由50選

1,顔がかわいい
2,まんまるに寝ることができる
3,お出迎えしてくれるなど
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
    token_path = base_dir / "token_docs.json"
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


def create_doc_with_text(
    base_dir: Path,
    title: str,
    body: str,
) -> tuple[str, str]:
    """
    新規ドキュメントを作成し body を先頭に挿入する。
    戻り値: (documentId, ブラウザで開く用の URL)
    """
    creds = get_credentials(base_dir)
    service = build("docs", "v1", credentials=creds)

    doc = service.documents().create(body={"title": title}).execute()
    document_id = doc["documentId"]

    # 空ドキュメントは先頭に暗黙の改行があり、index 1 から挿入する
    service.documents().batchUpdate(
        documentId=document_id,
        body={
            "requests": [
                {
                    "insertText": {
                        "location": {"index": 1},
                        "text": body,
                    }
                }
            ]
        },
    ).execute()

    url = f"https://docs.google.com/document/d/{document_id}/edit"
    return document_id, url


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    title = "うちの猫が最高にかわいい理由50選"
    doc_id, url = create_doc_with_text(base_dir, title, DOC_BODY_TEXT)
    print("ドキュメントを作成し、テキストを挿入しました。")
    print(f"Document ID: {doc_id}")
    print(f"URL: {url}")


if __name__ == "__main__":
    main()
