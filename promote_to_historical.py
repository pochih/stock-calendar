"""
promote_to_historical.py — 把 weekly_briefing 中重大條目升級到 historical_events

Phase 4 半自動化:
  - 列 weekly_briefing 內最近 N 條條目
  - 互動選擇要升級的 (或 --headline 指定 title 關鍵字)
  - 自動轉換 schema 並插入 historical_events
  - weekly_briefing 原條目保留不刪 (兩處都看得到歷史脈絡)

schema 對映:
  weekly_briefing.headline → historical_events
  - date: 用 weekly date_range 的中間或週末日 (或 --date 指定)
  - ticker: tickers[0] (主要受影響股)
  - event: title
  - move: '?'  (需手動補)
  - mcap_loss: '?'
  - spx / qqq: '?'
  - type: 從 category 推 (市場修正 → 下跌; IPO/併購 → 暴漲)
  - lesson: stance + implication 合併

使用:
  python promote_to_historical.py                    # 列最近 20 條 weekly headlines 給你選
  python promote_to_historical.py --week 2026-W25    # 列該週的 headlines
  python promote_to_historical.py --week 2026-W25 --headline "Anthropic" --date 2026-06-19 \\
      --ticker ANTH --move "-5%" --type 下跌
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data.json"

# category → type mapping
TYPE_MAP = {
    "市場修正": "下跌",
    "宏觀資金": "下跌",  # 多半是緊縮類
    "宏觀政治": "下跌",
    "司法": "下跌",
    "IPO + 估值": "暴漲",  # SpaceX IPO 等
    "併購": "暴漲",
    "AI 模型": "下跌",  # Anthropic 之類事故
    "Intel 復活": "暴漲",
}


def find_headline(weeks: list[dict], week_key: str, title_kw: str) -> tuple[dict, dict] | None:
    """回傳 (week_entry, headline) 或 None"""
    week = next((w for w in weeks if w["week"] == week_key), None)
    if not week:
        return None
    h = next((h for h in week.get("headlines", []) if title_kw.lower() in h.get("title", "").lower()), None)
    if not h:
        return None
    return week, h


def build_historical_entry(week: dict, headline: dict, date_str: str, ticker: str,
                           move: str, mcap_loss: str, spx: str, qqq: str,
                           type_str: str) -> dict:
    """從 weekly headline 組 historical_events entry"""
    lesson_parts = []
    if headline.get("summary"):
        lesson_parts.append(headline["summary"])
    if headline.get("stance"):
        lesson_parts.append(f"立場: {headline['stance']}")
    if headline.get("implication"):
        lesson_parts.append(f"含意: {headline['implication']}")
    lesson = " | ".join(lesson_parts)

    if not type_str:
        type_str = TYPE_MAP.get(headline.get("category", ""), "下跌")

    return {
        "date": date_str,
        "ticker": ticker,
        "event": headline.get("title", ""),
        "move": move or "?",
        "mcap_loss": mcap_loss or "?",
        "spx": spx or "?",
        "qqq": qqq or "?",
        "type": type_str,
        "lesson": lesson,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--week", help="指定 week (e.g. 2026-W25),不指定則列最近 20 條")
    ap.add_argument("--headline", help="title 關鍵字 (substring match)")
    ap.add_argument("--date", help="historical_events 日期 YYYY-MM-DD")
    ap.add_argument("--ticker", help="主要受影響股 (預設取 headline tickers[0])")
    ap.add_argument("--move", default="?", help="該股漲跌 (e.g. -5% / +19%)")
    ap.add_argument("--mcap-loss", default="?", help="市值變化 (e.g. -$120B)")
    ap.add_argument("--spx", default="?", help="S&P 500 漲跌 (e.g. -0.3%)")
    ap.add_argument("--qqq", default="?", help="QQQ 漲跌")
    ap.add_argument("--type", help="事件類型 (暴漲/下跌/崩盤),不指定則從 category 推")
    args = ap.parse_args()

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    weeks = data.get("weekly_briefing", [])

    # 沒指定 week + headline → 列最近 20 條
    if not args.week or not args.headline:
        print("📋 最近 weekly_briefing headlines:\n")
        count = 0
        for w in weeks[:5]:
            print(f"=== {w['week']} ({w['date_range']}) ===")
            for h in w.get("headlines", []):
                tickers = ",".join(h.get("tickers", [])[:3])
                print(f"  [{h.get('category','?'):8s}] {h.get('title','')[:60]}  tickers=[{tickers}]")
                count += 1
                if count >= 20:
                    break
            if count >= 20:
                break
        print(f"\n👉 用 --week {weeks[0]['week']} --headline '<title 關鍵字>' --date YYYY-MM-DD --ticker XX --move '-5%' [--type 下跌] 升級")
        return

    # 找指定 headline
    found = find_headline(weeks, args.week, args.headline)
    if not found:
        print(f"❌ 找不到 {args.week} 內 title 含 '{args.headline}' 的 headline", file=sys.stderr)
        sys.exit(1)
    week, headline = found

    # 日期 fallback: 用 date_range 結束
    if not args.date:
        args.date = week["date_range"].split("~")[-1].strip()
        print(f"⚠️  未指定 --date,用週末日 {args.date}", file=sys.stderr)

    # ticker fallback
    ticker = args.ticker
    if not ticker:
        tickers = headline.get("tickers", [])
        if tickers:
            ticker = tickers[0].split()[0]  # "ANTH (未上市)" → "ANTH"
        else:
            print("❌ headline 無 tickers,請用 --ticker 指定", file=sys.stderr)
            sys.exit(1)

    entry = build_historical_entry(
        week, headline, args.date, ticker,
        args.move, args.mcap_loss, args.spx, args.qqq, args.type
    )

    print("\n📋 將新增 historical_events 條目:")
    print(json.dumps(entry, ensure_ascii=False, indent=2))

    ans = input("\n確定加入嗎? [y/N] ").strip().lower()
    if ans != "y":
        print("已取消")
        return

    # 插入到 historical_events 開頭 (新的在前)
    data.setdefault("historical_events", [])
    data["historical_events"].insert(0, entry)
    # 按 date 排序 (新的在前)
    data["historical_events"].sort(key=lambda e: e.get("date", ""), reverse=True)

    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n✅ 寫入 {DATA_FILE.name}")
    print("👉 記得跑 python run.py --no-update --update-only 重新嵌入 index.html")


if __name__ == "__main__":
    main()
