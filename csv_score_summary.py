"""
CSVファイルから参加者ごとのスコア集計を行い、
平均・最高点・最低点を表示するプログラム。

想定CSV:
  - ヘッダーありの場合: 参加者列(name/participant/player/user 等)とスコア列(score/point/result 等)
  - ヘッダーなしの場合: 先頭2列を「参加者, スコア」とみなす
"""

from __future__ import annotations

import argparse
import csv
import os
from collections import defaultdict
from typing import Dict, List, Optional, Tuple


PARTICIPANT_KEYS = {
    "name",
    "participant",
    "player",
    "user",
    "member",
    "person",
    "参加者",
    "氏名",
    "名前",
    "選手",
    "メンバー",
}
SCORE_KEYS = {
    "score",
    "point",
    "points",
    "result",
    "results",
    "score_value",
    "mark",
    "スコア",
    "点",
    "得点",
    "ポイント",
    "結果",
    "成績",
}


def _lower_str(x: str) -> str:
    return x.strip().lower()


def _format_score(x: float) -> str:
    # 浮動小数で読み込んでいるが、整数っぽい場合は整数表示にする
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    s = f"{x:.2f}"
    # 末尾の0や小数点だけを取り除く（見た目を整える）
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def _detect_columns_from_header(fieldnames: List[str]) -> Tuple[int, int]:
    participant_idx: Optional[int] = None
    score_idx: Optional[int] = None

    lowered = [_lower_str(f) for f in fieldnames]
    for i, key in enumerate(lowered):
        if participant_idx is None and key in PARTICIPANT_KEYS:
            participant_idx = i
        if score_idx is None and key in SCORE_KEYS:
            score_idx = i

    if participant_idx is None or score_idx is None:
        raise ValueError(
            "ヘッダーから列を特定できません。"
            f" 見つかった列: {fieldnames}. "
            "参加者列(name/participant/player/user 等)とスコア列(score/point/result 等)を用意してください。"
        )

    return participant_idx, score_idx


def _read_scores(csv_path: str, delimiter: str, encoding: str) -> Dict[str, List[float]]:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSVファイルが見つかりません: {csv_path}")

    scores_by_participant: Dict[str, List[float]] = defaultdict(list)

    with open(csv_path, "r", encoding=encoding, newline="") as f:
        reader = csv.reader(f, delimiter=delimiter)
        rows = list(reader)

    if not rows:
        return {}

    first_row = rows[0]
    has_header = any(_lower_str(cell) in PARTICIPANT_KEYS.union(SCORE_KEYS) for cell in first_row)

    if has_header:
        fieldnames = first_row
        participant_idx, score_idx = _detect_columns_from_header(fieldnames)
        data_rows = rows[1:]
        for row in data_rows:
            if len(row) <= max(participant_idx, score_idx):
                continue
            participant = row[participant_idx].strip()
            score_raw = row[score_idx].strip()
            if not participant:
                continue
            try:
                score = float(score_raw)
            except ValueError:
                # 数値に変換できない行はスキップ（必要なら挙動を変えてください）
                continue
            scores_by_participant[participant].append(score)
    else:
        # ヘッダーなし: 先頭2列を (参加者, スコア) とみなす
        for row in rows:
            if len(row) < 2:
                continue
            participant = row[0].strip()
            score_raw = row[1].strip()
            if not participant:
                continue
            try:
                score = float(score_raw)
            except ValueError:
                continue
            scores_by_participant[participant].append(score)

    return dict(scores_by_participant)


def _compute_stats(scores: List[float]) -> Tuple[float, float, float]:
    # 平均、最高点、最低点
    total = sum(scores)
    n = len(scores)
    mean = total / n if n else 0.0
    max_score = max(scores)
    min_score = min(scores)
    return mean, max_score, min_score


def _print_table(scores_by_participant: Dict[str, List[float]], csv_path: str) -> None:
    participants = sorted(scores_by_participant.keys())
    if not participants:
        print("データがありませんでした。")
        return

    # 表の列幅を揃えるために先に文字列化しておく
    rows = []
    for p in participants:
        values = scores_by_participant[p]
        mean, mx, mn = _compute_stats(values)
        rows.append(
            (
                p,
                str(len(values)),
                _format_score(mean),
                _format_score(mx),
                _format_score(mn),
            )
        )

    headers = ("参加者", "回数", "平均", "最高点", "最低点")
    col_widths = [len(h) for h in headers]
    for r in rows:
        for i, cell in enumerate(r):
            col_widths[i] = max(col_widths[i], len(cell))

    def fmt_row(cols: Tuple[str, ...]) -> str:
        return " | ".join(col.ljust(col_widths[i]) for i, col in enumerate(cols))

    sep = "-+-".join("-" * w for w in col_widths)

    print(f"参加者ごとのスコア集計: {csv_path}")
    print(fmt_row(headers))
    print(sep)
    for r in rows:
        print(fmt_row(r))


def main() -> None:
    parser = argparse.ArgumentParser(description="CSVから参加者ごとのスコア平均・最高・最低を算出します。")
    parser.add_argument("csv_path", help="CSVファイルのパス")
    parser.add_argument("--delimiter", default=",", help="区切り文字（デフォルト: ,）")
    parser.add_argument("--encoding", default="utf-8", help="文字コード（デフォルト: utf-8）")
    args = parser.parse_args()

    scores_by_participant = _read_scores(args.csv_path, delimiter=args.delimiter, encoding=args.encoding)
    _print_table(scores_by_participant, csv_path=args.csv_path)


if __name__ == "__main__":
    main()

