from __future__ import annotations

import csv
from pathlib import Path
from statistics import mean

import matplotlib.pyplot as plt
from matplotlib import rcParams


def configure_plot_style() -> None:
    # macOSで利用可能な日本語フォントを優先指定
    rcParams["font.family"] = "sans-serif"
    rcParams["font.sans-serif"] = [
        "Hiragino Sans",
        "Yu Gothic",
        "Meiryo",
        "Noto Sans CJK JP",
        "IPAPGothic",
        "DejaVu Sans",
    ]
    rcParams["axes.unicode_minus"] = False


def read_csv_data(csv_path: Path) -> tuple[list[str], list[str], list[float]]:
    names: list[str] = []
    departments: list[str] = []
    scores: list[float] = []

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("名前") or "").strip()
            dept = (row.get("所属") or "").strip()
            score_raw = (row.get("スコア") or "").strip()
            if not name or not dept or not score_raw:
                continue
            try:
                score = float(score_raw)
            except ValueError:
                continue
            names.append(name)
            departments.append(dept)
            scores.append(score)

    return names, departments, scores


def save_pie_chart(departments: list[str], output_path: Path) -> None:
    counts: dict[str, int] = {}
    for dept in departments:
        counts[dept] = counts.get(dept, 0) + 1

    labels = list(counts.keys())
    sizes = list(counts.values())

    plt.figure(figsize=(7, 7))
    plt.pie(
        sizes,
        labels=labels,
        autopct="%1.1f%%",
        startangle=90,
        counterclock=False,
    )
    plt.title("所属ごとの参加者割合")
    plt.axis("equal")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def save_bar_chart(departments: list[str], scores: list[float], output_path: Path) -> None:
    grouped_scores: dict[str, list[float]] = {}
    for dept, score in zip(departments, scores):
        grouped_scores.setdefault(dept, []).append(score)

    labels = list(grouped_scores.keys())
    avg_scores = [mean(grouped_scores[dept]) for dept in labels]

    plt.figure(figsize=(8, 5))
    plt.bar(labels, avg_scores, label="平均スコア")
    plt.title("所属ごとの平均スコア")
    plt.xlabel("所属")
    plt.ylabel("スコア")
    plt.ylim(0, 100)
    plt.legend()
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def save_histogram(scores: list[float], output_path: Path) -> None:
    plt.figure(figsize=(8, 5))
    plt.hist(scores, bins=8, edgecolor="black")
    plt.title("全参加者のスコア分布")
    plt.xlabel("スコア")
    plt.ylabel("人数")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    csv_path = base_dir / "課題3 (1).csv"

    configure_plot_style()

    names, departments, scores = read_csv_data(csv_path)
    if not names:
        raise ValueError("有効なデータが読み込めませんでした。CSV内容を確認してください。")

    pie_path = base_dir / "kadai3_pie.png"
    bar_path = base_dir / "kadai3_bar.png"
    hist_path = base_dir / "kadai3_hist.png"

    save_pie_chart(departments, pie_path)
    save_bar_chart(departments, scores, bar_path)
    save_histogram(scores, hist_path)

    print("グラフ画像を保存しました。")
    print(f"- {pie_path}")
    print(f"- {bar_path}")
    print(f"- {hist_path}")


if __name__ == "__main__":
    main()
