from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


# Google Drive にファイル作成するための最小スコープ
SCOPES = ["https://www.googleapis.com/auth/drive.file"]

# ユーザーが提示した API キー（Drive へのアップロード認可には使えません）
GOOGLE_API_KEY = "AIzaSyC1X_QH10Q_NKDHiaiSeOYAS7ufjV55pgE"


def find_credentials_file(base_dir: Path) -> Path:
    """
    利用可能な OAuth クライアント情報ファイルを探して返す。
    """
    default_file = base_dir / "credentials.json"
    if default_file.exists():
        return default_file

    # ユーザーが保存した形式（例: client_secret_xxx.apps.googleusercontent.com）
    candidates = list(base_dir.glob("client_secret_*"))
    if candidates:
        return candidates[0]

    raise FileNotFoundError(
        "OAuth クライアント情報ファイルが見つかりません。"
        " credentials.json か client_secret_* ファイルを配置してください。"
    )


def get_drive_service(base_dir: Path) -> object:
    """
    OAuth 認証済みの Google Drive サービスを返す。
    初回実行時はブラウザが開き、認証後に token.json が保存される。
    """
    creds = None
    token_path = base_dir / "token.json"
    credentials_path = find_credentials_file(base_dir)

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

    return build("drive", "v3", credentials=creds)


def upload_file_to_drive(file_path: Path, base_dir: Path) -> str:
    """
    指定したローカルファイルを Google Drive にアップロードし、ファイルIDを返す。
    """
    if not file_path.exists():
        raise FileNotFoundError(f"アップロード対象が見つかりません: {file_path}")

    service = get_drive_service(base_dir)

    file_metadata = {"name": file_path.name}
    media = MediaFileUpload(str(file_path), resumable=True)

    uploaded = (
        service.files()
        .create(body=file_metadata, media_body=media, fields="id, name, webViewLink")
        .execute()
    )

    print(f"アップロード完了: {uploaded['name']}")
    print(f"File ID: {uploaded['id']}")
    print(f"Drive URL: {uploaded.get('webViewLink', '(取得不可)')}")
    return uploaded["id"]


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    target_file = base_dir / "kadai3_pie.png"

    # API キーはこの処理では実質未使用。将来の拡張時のために表示のみ行う。
    if GOOGLE_API_KEY:
        print("Google API Key は設定済みです。")

    upload_file_to_drive(target_file, base_dir)


if __name__ == "__main__":
    main()
