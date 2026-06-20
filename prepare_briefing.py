"""
prepare_briefing.py — 收集本週原始素材給 Claude 生成 weekly_briefing 草稿

Phase 2 自動化的第一步:
  - 抓 Gmail 訂閱 (M報 / 馬斯克帝國觀察 / 富果直送) 本週新郵件 ID
  - 抓股癌本週新集 (EP 對應日期)
  - 抓 All-In 本週新集 (allin/index.json)
  - 組成 markdown context 檔,放 drafts/W{n}_context.md
  - 印出推薦的 Claude prompt 與來源清單

使用:
  python prepare_briefing.py            # 預設本週 (上週一到本週日)
  python prepare_briefing.py --week 25  # 指定 ISO week
  python prepare_briefing.py --year 2026 --week 25

執行流程:
  1. 跑這個 script 產生 context
  2. 把 context 交給 Claude (在 Claude Code 或 Web)
  3. Claude 產出 JSON weekly_briefing entry
  4. 你審稿 + 插入 data.json + commit
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DRAFTS_DIR = ROOT / "drafts"
DATA_FILE = ROOT / "data.json"
GOOAYE_INDEX = ROOT / "transcripts" / "gooaye" / "index.json"
ALLIN_INDEX = ROOT / "transcripts" / "allin" / "index.json"


def iso_week_bounds(year: int, week: int) -> tuple[dt.date, dt.date]:
    """回傳該 ISO week 的週一與週日 (含)"""
    # ISO week 起點是週一
    jan4 = dt.date(year, 1, 4)
    week1_monday = jan4 - dt.timedelta(days=jan4.isocalendar()[2] - 1)
    monday = week1_monday + dt.timedelta(weeks=week - 1)
    sunday = monday + dt.timedelta(days=6)
    return monday, sunday


def find_gooaye_episodes(start: dt.date, end: dt.date) -> list[dict]:
    if not GOOAYE_INDEX.exists():
        return []
    j = json.loads(GOOAYE_INDEX.read_text(encoding="utf-8"))
    return [ep for ep in j if start.isoformat() <= ep.get("d", "") <= end.isoformat()]


def find_allin_episodes(start: dt.date, end: dt.date) -> list[dict]:
    if not ALLIN_INDEX.exists():
        return []
    j = json.loads(ALLIN_INDEX.read_text(encoding="utf-8"))
    return [ep for ep in j if start.isoformat() <= ep.get("upload_date", "") <= end.isoformat()]


def build_context(year: int, week: int, monday: dt.date, sunday: dt.date,
                  gooaye_eps: list[dict], allin_eps: list[dict]) -> str:
    """組裝 markdown context 給 Claude 生草稿"""
    lines = [
        f"# Weekly Briefing Draft Context — {year}-W{week:02d}",
        f"",
        f"**範圍**: {monday} ~ {sunday} (週一至週日)",
        f"",
        f"## 任務",
        f"",
        f"請為 `data.json` 的 `weekly_briefing` 區段產生本週 entry。輸出 JSON,",
        f"格式參照既有的條目 (week / date_range / sources / headlines)。",
        f"",
        f"**目標**: 4-8 條 headlines,涵蓋:",
        f"- 1 macro / Fed (category: 宏觀資金 / 市場修正)",
        f"- 1-2 AI 模型 / 雲端 (category: AI 模型 / AI 軟體)",
        f"- 1 Tesla / SpaceX / 馬斯克 (category: Tesla / Tesla / FSD / 馬斯克)",
        f"- 1 IPO / M&A (若有,category: IPO + 估值 / 併購)",
        f"- 1 台股 (category: 股癌觀點 / 台股個股)",
        f"",
        f"**重要**: 在 `implication` 欄位提及『後續可能影響 X』或『印證 W{week-1} 的 Y』",
        f"以建立週次間的因果鏈。讀者(博的)很重視這條 narrative thread。",
        f"",
        f"## 來源",
        f"",
    ]

    # 股癌
    if gooaye_eps:
        lines.append(f"### 股癌 ({len(gooaye_eps)} 集)")
        for ep in sorted(gooaye_eps, key=lambda x: x["d"]):
            lines.append(f"")
            lines.append(f"**EP{ep['n']} ({ep['d']}) — {ep['t']}**")
            lines.append(f"")
            lines.append(f"> {ep.get('desc', '')}")
        lines.append("")

    # All-In
    if allin_eps:
        lines.append(f"### All-In Podcast ({len(allin_eps)} 集)")
        for ep in sorted(allin_eps, key=lambda x: x.get("upload_date", "")):
            lines.append(f"")
            lines.append(f"**{ep.get('upload_date','?')} — {ep.get('title','?')}**")
            lines.append(f"")
            lines.append(f"全文位於: `transcripts/allin/{ep.get('txt_file','?')}`")
            lines.append(f"")
            lines.append(f"用 Read tool 載入,然後萃取 1-3 個對應到本週事件的觀點。")
        lines.append("")

    # Gmail
    lines.append(f"### Gmail 訂閱 (需 Claude 用 Gmail MCP 抓)")
    lines.append(f"")
    lines.append(f"Claude 請執行以下 search:")
    lines.append(f"")
    lines.append(f"```")
    lines.append(f"# M報")
    lines.append(f"mcp__gmail__search_emails(")
    lines.append(f"  query='from:mviewpoint@substack.com after:{monday} before:{sunday + dt.timedelta(days=1)}',")
    lines.append(f"  maxResults=5)")
    lines.append(f"")
    lines.append(f"# 馬斯克帝國觀察")
    lines.append(f"mcp__gmail__search_emails(")
    lines.append(f"  query='from:muskempire0628@substack.com after:{monday} before:{sunday + dt.timedelta(days=1)}',")
    lines.append(f"  maxResults=5)")
    lines.append(f"")
    lines.append(f"# 富果直送")
    lines.append(f"mcp__gmail__search_emails(")
    lines.append(f"  query='from:service@fugle.tw after:{monday} before:{sunday + dt.timedelta(days=1)}',")
    lines.append(f"  maxResults=10)")
    lines.append(f"```")
    lines.append(f"")
    lines.append(f"找到的每封信都用 `mcp__gmail__read_email` 看內文。")

    lines.extend([
        "",
        "## 輸出格式",
        "",
        "```json",
        "{",
        f'  "week": "{year}-W{week:02d}",',
        f'  "date_range": "{monday} ~ {sunday}",',
        '  "sources": ["M報 #X", "馬斯克帝國觀察 #Y", "富果直送 (個股名)", '
        + f'"股癌 EP{gooaye_eps[0]["n"] if gooaye_eps else "?"}-#{gooaye_eps[-1]["n"] if gooaye_eps else "?"}", '
        '"All-In 6/13"],',
        '  "headlines": [',
        '    {',
        '      "category": "宏觀資金",',
        '      "title": "...",',
        '      "tickers": ["NVDA", "..."],',
        '      "summary": "事實 / 數據點",',
        '      "stance": "M觀點:... / 股癌:... / All-In:...",',
        '      "implication": "後續...",',
        '      "themes_touched": ["..."]',
        '    }',
        '  ]',
        '}',
        "```",
        "",
        f"產出後請插入 `data.json` 的 `weekly_briefing` 陣列開頭,然後跑:",
        f"",
        f"```bash",
        f"python run.py --no-update --update-only  # 重新嵌入 index.html",
        f"git add data.json index.html",
        f"git commit -m 'feat: weekly_briefing {year}-W{week:02d}'",
        f"git push",
        f"python send_briefing.py --week {year}-W{week:02d} --json  # 寄信",
        f"```",
    ])

    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    today = dt.date.today()
    iso = today.isocalendar()
    ap.add_argument("--year", type=int, default=iso[0])
    ap.add_argument("--week", type=int, default=iso[1])
    args = ap.parse_args()

    monday, sunday = iso_week_bounds(args.year, args.week)
    gooaye = find_gooaye_episodes(monday, sunday)
    allin = find_allin_episodes(monday, sunday)

    print(f"📅 {args.year}-W{args.week:02d}: {monday} ~ {sunday}")
    print(f"   股癌: {len(gooaye)} 集")
    if gooaye:
        for ep in gooaye:
            print(f"     EP{ep['n']} {ep['d']} {ep['t'][:50]}")
    print(f"   All-In: {len(allin)} 集")
    if allin:
        for ep in allin:
            print(f"     {ep['upload_date']} {ep['title'][:60]}")

    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    context_path = DRAFTS_DIR / f"W{args.week:02d}_{args.year}_context.md"
    context_path.write_text(
        build_context(args.year, args.week, monday, sunday, gooaye, allin),
        encoding="utf-8",
    )
    print(f"\n📝 context 寫入: {context_path}")
    print(f"\n下一步:")
    print(f"  1. 把 {context_path.name} 內容貼給 Claude (或讓 Claude Read 這個檔)")
    print(f"  2. Claude 會抓 Gmail + 生成 weekly_briefing entry JSON")
    print(f"  3. 審稿後插入 data.json,commit + push + 寄信")


if __name__ == "__main__":
    main()
