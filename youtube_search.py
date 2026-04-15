"""
YouTube Data API v3 を使って動画検索を行うスクリプト。

使い方:
  export YOUTUBE_API_KEY="your_api_key"
  python youtube_search.py

オプション:
  python youtube_search.py --keyword "東京 おでかけ" --max-results 10
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request


YOUTUBE_SEARCH_ENDPOINT = "https://www.googleapis.com/youtube/v3/search"
DEFAULT_KEYWORD = "東京 おでかけ"


def search_videos(api_key: str, keyword: str, max_results: int) -> list[dict[str, str]]:
    params = {
        "part": "snippet",
        "q": keyword,
        "type": "video",
        "maxResults": str(max_results),
        "key": api_key,
    }
    query = urllib.parse.urlencode(params)
    url = f"{YOUTUBE_SEARCH_ENDPOINT}?{query}"

    with urllib.request.urlopen(url, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))

    items = payload.get("items", [])
    results: list[dict[str, str]] = []
    for item in items:
        video_id = item.get("id", {}).get("videoId")
        title = item.get("snippet", {}).get("title", "")
        if not video_id:
            continue
        results.append(
            {
                "title": title,
                "url": f"https://www.youtube.com/watch?v={video_id}",
            }
        )
    return results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="YouTube 動画検索スクリプト")
    parser.add_argument(
        "--keyword",
        default=DEFAULT_KEYWORD,
        help=f'検索キーワード（デフォルト: "{DEFAULT_KEYWORD}"）',
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=5,
        help="取得件数（1〜50）",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 1 <= args.max_results <= 50:
        raise ValueError("--max-results は 1〜50 で指定してください。")

    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        print(
            "YOUTUBE_API_KEY が未設定です。環境変数に API キーを設定してください。",
            file=sys.stderr,
        )
        print('例: export YOUTUBE_API_KEY="your_api_key"', file=sys.stderr)
        sys.exit(1)

    videos = search_videos(api_key=api_key, keyword=args.keyword, max_results=args.max_results)
    if not videos:
        print("検索結果がありませんでした。")
        return

    print(f'検索キーワード: "{args.keyword}"')
    print(f"取得件数: {len(videos)}")
    print("-" * 60)
    for index, video in enumerate(videos, start=1):
        print(f"{index}. {video['title']}")
        print(video["url"])
        print("-" * 60)


if __name__ == "__main__":
    main()
