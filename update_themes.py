"""
update_themes.py — 從 weekly_briefing 統計題材熱度,標進 themes 區段

邏輯:
  - 掃 weekly_briefing 所有 headlines 的 themes_touched
  - 計算每個題材出現的: 總次數 / 最近 4 週次數 / 最近 8 週次數
  - 寫進每個 theme 物件的 heat 欄位 {total, recent_4w, recent_8w, trend}
  - trend: "🔥 hot" (recent_4w >= 3) / "📈 rising" (recent_8w 比前 8 週多) /
    "🔻 cooling" / "➡️ stable"

使用:
  python update_themes.py            # 寫入 data.json
  python update_themes.py --dry-run  # 只印
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data.json"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="只印不寫")
    args = ap.parse_args()

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    weeks = data.get("weekly_briefing", [])
    themes = data.get("themes", [])

    if not weeks:
        print("❌ weekly_briefing 空,沒題材可分析", file=sys.stderr)
        sys.exit(1)

    # weeks 已按 week desc 排序 (W25 W24 W23 ...) ; 拿 recent N
    def themes_in(week_slice: list[dict]) -> Counter:
        c = Counter()
        for w in week_slice:
            for h in w.get("headlines", []):
                for t in h.get("themes_touched") or []:
                    c[t] += 1
        return c

    total = themes_in(weeks)
    recent_4w = themes_in(weeks[:4])
    recent_8w = themes_in(weeks[:8])
    prev_8w = themes_in(weeks[8:16])

    print(f"📊 weekly_briefing: {len(weeks)} 週,題材出現總次數 top 10:\n")
    for t, n in total.most_common(10):
        r4, r8, p8 = recent_4w.get(t, 0), recent_8w.get(t, 0), prev_8w.get(t, 0)
        trend = "➡️"
        if r4 >= 3:
            trend = "🔥"
        elif r8 > p8 * 1.3 and r8 >= 2:
            trend = "📈"
        elif r8 < p8 * 0.5:
            trend = "🔻"
        print(f"  {trend} {t:35s} total={n:3d}  4w={r4}  8w={r8}  prev8w={p8}")

    print()
    print(f"🏷️ themes 區段: {len(themes)} 個。標記 heat 中...")

    updated = 0
    for theme in themes:
        name = theme.get("name", "")
        t_total = total.get(name, 0)
        r4 = recent_4w.get(name, 0)
        r8 = recent_8w.get(name, 0)
        p8 = prev_8w.get(name, 0)
        trend = "stable"
        if r4 >= 3:
            trend = "hot"
        elif r8 > p8 * 1.3 and r8 >= 2:
            trend = "rising"
        elif r8 < p8 * 0.5 and p8 >= 2:
            trend = "cooling"

        new_heat = {
            "total_mentions": t_total,
            "recent_4w": r4,
            "recent_8w": r8,
            "trend": trend,
        }
        if theme.get("heat") != new_heat:
            theme["heat"] = new_heat
            updated += 1

    # themes 主題不在 weekly_briefing 出現過的列出 (可能該手動建關聯 / 該題材已過氣)
    referenced = set(total.keys())
    theme_names = {t.get("name", "") for t in themes}
    missing_theme_refs = referenced - theme_names
    if missing_theme_refs:
        print(f"\n⚠️ weekly_briefing 提到但 themes 內無對應條目 ({len(missing_theme_refs)}):")
        for n in sorted(missing_theme_refs):
            print(f"  · {n}")

    unused_themes = theme_names - referenced
    if unused_themes:
        print(f"\n💤 themes 內但從沒被 weekly_briefing 提到的 ({len(unused_themes)}):")
        for n in sorted(unused_themes)[:20]:
            print(f"  · {n}")

    if args.dry_run:
        print(f"\n--- dry-run, 不寫入 (本來會更新 {updated} 個 theme.heat) ---")
        return

    if updated:
        DATA_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\n✅ 更新 {updated} 個 theme 的 heat 欄位,寫入 {DATA_FILE.name}")
        print("👉 記得跑 python run.py --no-update --update-only 重新嵌入 index.html")
    else:
        print(f"\n✓ heat 無變化")


if __name__ == "__main__":
    main()
