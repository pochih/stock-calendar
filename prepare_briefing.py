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
  python prepare_briefing.py --daily    # 每日增量:檢查當週 drafts,append 今天有的新素材

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
import re
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


def build_daily_increment(year: int, week: int, monday: dt.date, sunday: dt.date,
                          existing_text: str) -> tuple[str, list[dict], list[dict], dt.date, dt.date]:
    """檢查當週 drafts 已涵蓋哪些素材,回傳新增區段 + 新 episodes 清單。

    回傳 (markdown_section, new_gooaye, new_allin, gmail_after, gmail_before)。
    若無新素材,markdown_section 為空字串。
    """
    today = dt.date.today()
    # 抓本週至今的素材 (本週一 ~ today)
    gooaye_all = find_gooaye_episodes(monday, min(today, sunday))
    allin_all = find_allin_episodes(monday, min(today, sunday))

    # 解析既有 drafts 中提到的 EP 號與 All-In id
    mentioned_eps = set(re.findall(r"EP(\d+)", existing_text))
    # All-In txt_file 名稱含 video id,沿用同樣方式抓出
    mentioned_allin = set(re.findall(r"EP([A-Za-z0-9_-]{11})_", existing_text))

    new_gooaye = [ep for ep in gooaye_all if str(ep["n"]) not in mentioned_eps]
    new_allin = [ep for ep in allin_all if ep.get("id") not in mentioned_allin]

    # Gmail 區段:每日都印,Claude 自己依日期判斷 (M報 / 馬斯克 / 富果 都可能多封)
    # 用 today (含當天) 作為 before,monday 作為 after,讓 Claude 抓本週至今所有信
    gmail_after = monday
    gmail_before = today + dt.timedelta(days=1)

    if not new_gooaye and not new_allin:
        # 仍提供 Gmail 搜尋指令(電子報可能每日都有新信)
        section = [
            f"",
            f"## 增量 {today.isoformat()} (cron 22:33)",
            f"",
            f"**本地素材**: 今日無新股癌 / All-In 集數",
            f"",
            f"**Gmail 增量**: Claude 用 MCP 抓本週至今所有信,並比對既有 drafts 是否已收錄",
            f"",
            f"```",
            f"mcp__gmail__search_emails(query='from:mviewpoint@substack.com after:{gmail_after} before:{gmail_before}', maxResults=5)",
            f"mcp__gmail__search_emails(query='from:muskempire0628@substack.com after:{gmail_after} before:{gmail_before}', maxResults=5)",
            f"mcp__gmail__search_emails(query='from:service@fugle.tw after:{gmail_after} before:{gmail_before}', maxResults=10)",
            f"```",
            f"",
            f"若 Gmail 抓到的 subject 已存在於上方 drafts,跳過;否則 mcp__gmail__read_email 抓正文後在此 append 摘要 (2-4 行/封)。",
            f"",
        ]
        return "\n".join(section), [], [], gmail_after, gmail_before

    section = [
        f"",
        f"## 增量 {today.isoformat()} (cron 22:33)",
        f"",
    ]
    if new_gooaye:
        section.append(f"### 股癌新集數 ({len(new_gooaye)} 集)")
        for ep in sorted(new_gooaye, key=lambda x: x["d"]):
            section.append("")
            section.append(f"**EP{ep['n']} ({ep['d']}) — {ep['t']}**")
            section.append("")
            section.append(f"> {ep.get('desc', '')}")
        section.append("")
    if new_allin:
        section.append(f"### All-In 新集數 ({len(new_allin)} 集)")
        for ep in sorted(new_allin, key=lambda x: x.get("upload_date", "")):
            section.append("")
            section.append(f"**{ep.get('upload_date','?')} — {ep.get('title','?')}**")
            section.append("")
            section.append(f"全文位於: `transcripts/allin/{ep.get('txt_file','?')}`")
            section.append("")
            section.append("Claude Read tool 載入,然後萃取 1-3 個對應到本週事件的觀點。")
        section.append("")

    section.extend([
        f"### Gmail 增量",
        f"",
        f"Claude 用 MCP 抓本週至今所有信,並比對既有 drafts 是否已收錄:",
        f"",
        f"```",
        f"mcp__gmail__search_emails(query='from:mviewpoint@substack.com after:{gmail_after} before:{gmail_before}', maxResults=5)",
        f"mcp__gmail__search_emails(query='from:muskempire0628@substack.com after:{gmail_after} before:{gmail_before}', maxResults=5)",
        f"mcp__gmail__search_emails(query='from:service@fugle.tw after:{gmail_after} before:{gmail_before}', maxResults=10)",
        f"```",
        f"",
        f"若 Gmail 抓到的 subject 已存在於上方 drafts,跳過;否則 mcp__gmail__read_email 抓正文後在此 append 摘要 (2-4 行/封)。",
        f"",
    ])
    return "\n".join(section), new_gooaye, new_allin, gmail_after, gmail_before


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    today = dt.date.today()
    iso = today.isocalendar()
    ap.add_argument("--year", type=int, default=iso[0])
    ap.add_argument("--week", type=int, default=iso[1])
    ap.add_argument("--daily", action="store_true", help="每日增量模式:檢查當週 drafts,append 今天的新素材")
    args = ap.parse_args()

    monday, sunday = iso_week_bounds(args.year, args.week)
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    context_path = DRAFTS_DIR / f"W{args.week:02d}_{args.year}_context.md"

    if args.daily:
        if not context_path.exists():
            # 該週首次:走完整模式以建立 base context
            print(f"📅 {args.year}-W{args.week:02d}: drafts 不存在,首次建立完整 context")
            gooaye = find_gooaye_episodes(monday, sunday)
            allin = find_allin_episodes(monday, sunday)
            context_path.write_text(
                build_context(args.year, args.week, monday, sunday, gooaye, allin),
                encoding="utf-8",
            )
            print(f"📝 context 寫入: {context_path}")
            return

        existing = context_path.read_text(encoding="utf-8")
        section, new_gooaye, new_allin, gmail_after, gmail_before = build_daily_increment(
            args.year, args.week, monday, sunday, existing,
        )
        with open(context_path, "a", encoding="utf-8") as f:
            f.write(section)
        print(f"📅 {args.year}-W{args.week:02d} daily 增量:股癌 +{len(new_gooaye)} / All-In +{len(new_allin)}")
        print(f"📝 append 到 {context_path}")
        print(f"📧 Gmail 範圍: after={gmail_after} before={gmail_before} — 由 Claude session 進一步 fetch")
        return

    # 預設:整週重寫
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
