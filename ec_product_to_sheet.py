"""
テスト用の商品データを加工して Google スプレッドシートへ追記するプロトタイプ。

要件:
- Amazon API / スクレイピングは未接続（モックデータで正常系確認）
- OAuth 認証で Google Sheets API を利用
- credentials.json はプロジェクト直下
- token.json は初回認証後に生成
- 秘密情報は .env から読み込む
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
RAKUTEN_ITEM_SEARCH_API_URL = (
    "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"
)
DEFAULT_RAKUTEN_KEYWORD = "モバイルバッテリー"
DEFAULT_FETCH_LIMIT = 10


def looks_like_rakuten_app_id(app_id: str) -> bool:
    """楽天アプリIDらしい形式（数字列）かを簡易チェックする。"""
    return app_id.isdigit() and len(app_id) >= 10


def find_credentials_file(base_dir: Path) -> Path:
    """利用可能な OAuth クライアント情報ファイルを返す。"""
    default_file = base_dir / "credentials.json"
    if default_file.exists():
        return default_file

    candidates = list(base_dir.glob("client_secret_*.json"))
    if candidates:
        # 複数ある場合は更新日時が新しいものを優先
        return max(candidates, key=lambda p: p.stat().st_mtime)

    raise FileNotFoundError(
        "credentials.json が見つかりません。"
        " credentials.json または client_secret_*.json をプロジェクト直下に配置してください。"
    )


def load_env_file(env_path: Path) -> None:
    """`.env` を読み込み、このスクリプト実行時の環境変数へ反映する。"""
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue

        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key:
            # ターミナルに残っている古い export 値の影響を避けるため、
            # このスクリプトでは .env の値を優先する。
            os.environ[key] = value


def get_mock_products() -> list[dict[str, Any]]:
    """
    後で Amazon API / スクレイピングに差し替えやすいよう、
    商品取得処理を関数で分離する。
    """
    return [
        {
            "name": "ワイヤレスイヤホン Pro",
            "url": "https://example.com/products/earbuds-pro",
            "price": "¥12,980",
            "image_url": "https://example.com/images/earbuds-pro.jpg",
            "review_average": 4.6,
        },
        {
            "name": "USB-C 65W 充電器",
            "url": "https://example.com/products/charger-65w",
            "price": "3980円",
            "image_url": "https://example.com/images/charger-65w.jpg",
            "review_average": 3.2,
        },
        {
            "name": "4K モニター 27インチ",
            "url": "https://example.com/products/monitor-27-4k",
            "price": "49,800",
            "image_url": "",
            "review_average": "不明",
        },
    ]


def fetch_products_from_api() -> list[dict[str, Any]]:
    """
    楽天市場 商品検索 API から商品を取得する。
    失敗時はモックデータへフォールバックする。
    """
    app_id = os.getenv("RAKUTEN_APPLICATION_ID", "").strip()
    keyword = os.getenv("RAKUTEN_KEYWORD", DEFAULT_RAKUTEN_KEYWORD).strip()
    max_items_text = os.getenv("FETCH_LIMIT", str(DEFAULT_FETCH_LIMIT)).strip()

    try:
        max_items = int(max_items_text)
    except ValueError:
        print(
            f"WARN: FETCH_LIMIT が数値ではないため {DEFAULT_FETCH_LIMIT} 件を使用します: {max_items_text}"
        )
        max_items = DEFAULT_FETCH_LIMIT

    if max_items <= 0:
        max_items = DEFAULT_FETCH_LIMIT
    max_items = min(max_items, 30)

    if not app_id:
        print(
            "WARN: RAKUTEN_APPLICATION_ID が未設定のため、モックデータにフォールバックします。"
        )
        return get_mock_products()
    if not looks_like_rakuten_app_id(app_id):
        print(
            "WARN: RAKUTEN_APPLICATION_ID の形式が不正の可能性があります。"
            f" 現在値='{app_id}'。楽天アプリID（数字列）を設定してください。"
            " モックデータへフォールバックします。"
        )
        return get_mock_products()

    try:
        params = {
            "applicationId": app_id,
            "keyword": keyword or DEFAULT_RAKUTEN_KEYWORD,
            "hits": max_items,
            "format": "json",
        }
        response = requests.get(RAKUTEN_ITEM_SEARCH_API_URL, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        print(f"エラー: 楽天APIの取得に失敗したためモックデータを使用します: {exc}")
        return get_mock_products()

    items = data.get("Items", [])
    if not items:
        print("WARN: 楽天APIの取得結果が0件だったため、モックデータを使用します。")
        return get_mock_products()

    products: list[dict[str, Any]] = []
    for item_wrapper in items[:max_items]:
        item = item_wrapper.get("Item", item_wrapper)
        name = str(item.get("itemName", "")).strip()
        url = str(item.get("itemUrl", "")).strip()
        price = item.get("itemPrice")

        if not name or not url or price is None:
            # 欠損データはスキップして安全に処理継続
            continue

        products.append(
            {
                "name": name,
                "url": url,
                "price": price,
                "image_url": extract_rakuten_medium_image_url(item),
                # reviewAverage が無い場合は後段で「不明」に変換
                "review_average": item.get("reviewAverage"),
            }
        )

    if not products:
        print("WARN: 楽天APIレスポンスに有効な商品がなかったため、モックデータを使用します。")
        return get_mock_products()

    print(f"INFO: 楽天APIから {len(products)} 件取得しました。")
    return products


def get_products(product_source: str = "mock") -> list[dict[str, Any]]:
    """
    商品データ取得の入口。
    将来 API へ切り替える時は main() 側の source か、この分岐を変更する。
    """
    if product_source == "mock":
        return get_mock_products()
    if product_source == "api":
        return fetch_products_from_api()
    print(
        "WARN: PRODUCT_SOURCE は 'mock' または 'api' を指定してください。"
        f" 未対応の値 '{product_source}' が指定されたため 'mock' を使用します。"
    )
    return get_mock_products()


def parse_price_to_int(price_raw: Any) -> int:
    """価格を数値（int）として扱える形へ整える。"""
    if isinstance(price_raw, (int, float)):
        return int(price_raw)
    if price_raw is None:
        raise ValueError("価格が空です。")

    text = str(price_raw)
    digits = re.sub(r"[^\d]", "", text)
    if not digits:
        raise ValueError(f"価格の形式を解釈できません: {price_raw}")
    return int(digits)


def extract_rakuten_medium_image_url(item: dict[str, Any]) -> str:
    """楽天APIレスポンスから mediumImageUrls を優先して画像URLを抽出する。"""
    medium_images = item.get("mediumImageUrls", [])
    if isinstance(medium_images, list):
        for image_info in medium_images:
            if isinstance(image_info, dict):
                candidate = str(image_info.get("imageUrl", "")).strip()
            else:
                candidate = str(image_info).strip()
            if candidate:
                return candidate
    return ""


def build_google_sheets_image_formula(image_url: str) -> str:
    """画像URLから Google Sheets の IMAGE 関数文字列を作る。"""
    image_url = str(image_url).strip()
    if not image_url:
        return ""
    return f'=IMAGE("{image_url}")'


def format_review_average(review_raw: Any) -> str:
    """レビュー平均を '⭐⭐⭐ 3.2' 形式へ整える。取得不可時は '不明'。"""
    if review_raw is None:
        return "不明"

    text = str(review_raw).strip()
    if not text:
        return "不明"
    if text == "不明":
        return "不明"

    try:
        score = float(text)
    except ValueError:
        return "不明"

    star_count = round(score)
    star_count = max(0, min(5, star_count))
    stars = "⭐" * star_count if star_count > 0 else "☆"
    return f"{stars} {score:.1f}"


def normalize_product_record(
    raw_product: dict[str, Any], fetched_at: str
) -> dict[str, Any]:
    """
    取得元に依存する生データを、内部の統一形式へ変換する。
    統一キー: fetched_at / image / name / price / url / review_display
    """
    name = str(raw_product.get("name", "")).strip()
    url = str(raw_product.get("url", "")).strip()
    price = parse_price_to_int(raw_product.get("price"))
    image = build_google_sheets_image_formula(raw_product.get("image_url", ""))
    review_display = format_review_average(raw_product.get("review_average"))

    if not name:
        raise ValueError("商品名が空のデータがあります。")
    if not url:
        raise ValueError(f"URL が空です: {name}")

    return {
        "fetched_at": fetched_at,
        "image": image,
        "name": name,
        "price": price,
        "url": url,
        "review_display": review_display,
    }


def transform_products(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """商品データを統一形式へ加工する。"""
    fetched_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    normalized_products: list[dict[str, Any]] = []

    for product in products:
        normalized_products.append(normalize_product_record(product, fetched_at))

    return normalized_products


def build_sheet_rows(products: list[dict[str, Any]]) -> list[list[Any]]:
    """統一形式の商品データを、シート追記用の2次元配列へ変換する。"""
    return [
        [
            product["fetched_at"],
            product["image"],
            product["name"],
            product["price"],
            product["url"],
            product["review_display"],
        ]
        for product in products
    ]


def get_sheets_service(base_dir: Path) -> Any:
    """OAuth 認証済みの Google Sheets サービスを返す。"""
    credentials_path = find_credentials_file(base_dir)
    token_path = base_dir / "token.json"
    print(f"INFO: OAuth クライアント情報 = {credentials_path.name}")

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        if not creds.has_scopes(SCOPES):
            print(
                "INFO: 既存 token.json の権限が不足しているため削除し、再認証します。"
            )
            token_path.unlink(missing_ok=True)
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as exc:
                # invalid_grant などで更新失敗した場合は token を捨てて再認証する
                print(
                    f"INFO: token.json の更新に失敗したため再認証します: {exc}"
                )
                token_path.unlink(missing_ok=True)
                creds = None
        else:
            creds = None

        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    return build("sheets", "v4", credentials=creds)


def append_rows_to_sheet(
    service: Any, spreadsheet_id: str, sheet_name: str, rows: list[list[Any]]
) -> dict[str, Any]:
    """指定シートへ行データを追記する。"""
    body = {"values": rows}
    append_range = f"{sheet_name}!A:F"
    result = (
        service.spreadsheets()
        .values()
        .append(
            spreadsheetId=spreadsheet_id,
            range=append_range,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body=body,
        )
        .execute()
    )
    return result


def parse_updated_row_range(updated_range: str) -> tuple[int, int] | None:
    """
    updates.updatedRange 文字列から開始行・終了行（1始まり）を取り出す。
    例: Sheet1!A10:F12 -> (10, 12)
    """
    match = re.search(r"[A-Z]+(\d+):[A-Z]+(\d+)", updated_range)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def get_sheet_id_by_name(service: Any, spreadsheet_id: str, sheet_name: str) -> int:
    """シート名から sheetId を取得する。"""
    metadata = (
        service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets(properties(sheetId,title))")
        .execute()
    )
    for sheet in metadata.get("sheets", []):
        properties = sheet.get("properties", {})
        if properties.get("title") == sheet_name:
            return int(properties["sheetId"])
    raise ValueError(f"シート '{sheet_name}' が見つかりません。")


def set_row_height_for_appended_rows(
    service: Any,
    spreadsheet_id: str,
    sheet_name: str,
    append_response: dict[str, Any],
    pixel_size: int = 100,
) -> None:
    """追記された行の高さを指定ピクセルに設定する。"""
    updated_range = append_response.get("updates", {}).get("updatedRange", "")
    if not updated_range:
        print("WARN: updatedRange が取得できないため、行の高さ調整をスキップします。")
        return

    row_range = parse_updated_row_range(updated_range)
    if not row_range:
        print(
            f"WARN: updatedRange の解析に失敗したため、行の高さ調整をスキップします: {updated_range}"
        )
        return

    start_row_1based, end_row_1based = row_range
    sheet_id = get_sheet_id_by_name(service, spreadsheet_id, sheet_name)
    request_body = {
        "requests": [
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        # API は 0 始まり・endIndex は排他的
                        "dimension": "ROWS",
                        "startIndex": start_row_1based - 1,
                        "endIndex": end_row_1based,
                    },
                    "properties": {"pixelSize": pixel_size},
                    "fields": "pixelSize",
                }
            }
        ]
    }

    service.spreadsheets().batchUpdate(
        spreadsheetId=spreadsheet_id, body=request_body
    ).execute()
    print(f"INFO: 追記行の高さを {pixel_size}px に設定しました。")


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    load_env_file(base_dir / ".env")

    spreadsheet_id = os.getenv("SPREADSHEET_ID")
    sheet_name = os.getenv("SHEET_NAME")

    if not spreadsheet_id:
        print("エラー: 環境変数 SPREADSHEET_ID が未設定です。", file=sys.stderr)
        sys.exit(1)
    if not sheet_name:
        print("エラー: 環境変数 SHEET_NAME が未設定です。", file=sys.stderr)
        sys.exit(1)

    try:
        # 将来 API 接続へ差し替える場所:
        # - PRODUCT_SOURCE=mock: モックデータ
        # - PRODUCT_SOURCE=api : 楽天 API
        product_source = os.getenv("PRODUCT_SOURCE", "api").strip().lower()
        raw_products = get_products(product_source)
        normalized_products = transform_products(raw_products)
        transformed_rows = build_sheet_rows(normalized_products)

        print("INFO: 加工後データ（書き込み前）")
        for product in normalized_products:
            print(product)

        service = get_sheets_service(base_dir)
        response = append_rows_to_sheet(service, spreadsheet_id, sheet_name, transformed_rows)
        set_row_height_for_appended_rows(
            service, spreadsheet_id, sheet_name, response, pixel_size=100
        )
        updated_rows = response.get("updates", {}).get("updatedRows", 0)
        print(f"INFO: スプレッドシートへの追記が完了しました。追記行数: {updated_rows}")
    except Exception as exc:
        print(f"エラー: 処理に失敗しました: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
