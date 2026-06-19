"""
send_briefing.py — 將 weekly_briefing 某一週轉成 HTML email,
                   印到 stdout 供 Gmail MCP / 其他 SMTP 工具使用

使用:
  python send_briefing.py                 # 預設輸出最新一週
  python send_briefing.py --week 2026-W25 # 指定週次
  python send_briefing.py --latest 2      # 最新 2 週合併
  python send_briefing.py --json          # 輸出 {subject, html} JSON 給程式吃

輸出:
  stdout 印出 markdown header + 完整 HTML
  --json 模式輸出 {"subject": "...", "html_body": "..."}
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data.json"

# category → 顏色 (對應 index.html 的 brief-cat-* CSS)
CAT_COLOR = {
    "AI 模型": "#a371f7", "AI 算力": "#a371f7", "AI 硬體": "#a371f7", "AI 軟體": "#a371f7",
    "AI 雲端": "#a371f7", "微軟/OpenAI": "#a371f7", "Meta": "#a371f7", "AI 鬼故事": "#ff7b72",
    "IPO + 估值": "#3fb950", "財報": "#3fb950",
    "併購": "#d29922",
    "宏觀資金": "#f85149", "宏觀政治": "#f85149", "司法": "#ff7b72",
    "市場修正": "#ff7b72",
    "蘋果": "#c9d1d9",
    "Tesla": "#ffa657", "Tesla / FSD": "#ffa657", "Tesla / Robotaxi": "#ffa657",
    "馬斯克": "#ffa657", "SpaceX": "#ffa657", "Intel 復活": "#d29922",
    "台股個股": "#58a6ff", "台股深度": "#58a6ff", "股癌觀點": "#58a6ff",
}


def esc(s: str) -> str:
    return html.escape(str(s or ""), quote=True)


def render_headline(h: dict) -> str:
    cat = h.get("category", "")
    color = CAT_COLOR.get(cat, "#58a6ff")
    tickers = h.get("tickers") or []
    themes = h.get("themes_touched") or []

    ticker_html = ""
    if tickers:
        chips = "".join(
            f'<span style="display:inline-block; background:#1f3a5f; color:#79c0ff; '
            f'padding:2px 8px; margin:2px; border-radius:4px; font-size:11px; '
            f'font-family:monospace;">{esc(t)}</span>'
            for t in tickers
        )
        ticker_html = f'<div style="margin:8px 0;">{chips}</div>'

    theme_html = ""
    if themes:
        chips = "".join(
            f'<span style="display:inline-block; background:#21262d; color:#8b949e; '
            f'padding:2px 6px; margin:2px; border-radius:3px; font-size:10px;">🏷️ {esc(t)}</span>'
            for t in themes
        )
        theme_html = f'<div style="margin-top:8px;">{chips}</div>'

    sections = []
    for key, label in [("summary", "摘要"), ("stance", "立場"), ("implication", "含意")]:
        v = h.get(key)
        if v:
            sections.append(
                f'<div style="margin:6px 0; font-size:13px; line-height:1.65; color:#c9d1d9;">'
                f'<strong style="color:#58a6ff; margin-right:6px;">{label}</strong>{esc(v)}</div>'
            )
    body = "".join(sections)

    return f'''
<div style="background:rgba(13,17,23,0.5); border:1px solid #30363d; border-radius:8px;
            padding:14px 18px; margin-bottom:12px;">
  <div style="display:flex; align-items:baseline; gap:10px; margin-bottom:8px; flex-wrap:wrap;">
    <span style="font-size:10px; padding:2px 8px; border-radius:4px; font-weight:600;
                 background:{color}; color:#0d1117; white-space:nowrap;">{esc(cat)}</span>
    <span style="font-size:14px; font-weight:700; color:#c9d1d9; flex:1;">{esc(h.get('title', ''))}</span>
  </div>
  {ticker_html}
  {body}
  {theme_html}
</div>
'''


def render_week(w: dict) -> str:
    sources = " · ".join(esc(s) for s in (w.get("sources") or []))
    headlines_html = "".join(render_headline(h) for h in (w.get("headlines") or []))
    return f'''
<div style="background:#161b22; border:1px solid #30363d; border-radius:10px;
            padding:18px; margin-bottom:18px;">
  <div style="display:flex; justify-content:space-between; align-items:center;
              padding-bottom:10px; margin-bottom:14px; border-bottom:1px solid #30363d; flex-wrap:wrap;">
    <div>
      <div style="font-size:18px; font-weight:700; color:#58a6ff;">📅 {esc(w['week'])}</div>
      <div style="color:#8b949e; font-size:12px; margin-top:4px;">📚 {sources}</div>
    </div>
    <div style="color:#8b949e; font-size:12px; font-family:monospace;">{esc(w['date_range'])}</div>
  </div>
  {headlines_html}
</div>
'''


def build_email(weeks: list[dict]) -> tuple[str, str]:
    """回傳 (subject, html_body)"""
    if not weeks:
        return "📰 每週洞察 (無資料)", "<p>無 weekly_briefing 資料</p>"

    if len(weeks) == 1:
        subject = f"📰 每週洞察 {weeks[0]['week']} — {len(weeks[0]['headlines'])} 條 headline"
    else:
        subject = f"📰 每週洞察 {weeks[-1]['week']} → {weeks[0]['week']} ({len(weeks)} 週)"

    weeks_html = "".join(render_week(w) for w in weeks)
    total_h = sum(len(w.get("headlines", [])) for w in weeks)

    body = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="background:#0d1117; color:#c9d1d9; font-family:-apple-system, BlinkMacSystemFont,
             'Segoe UI', 'Noto Sans TC', sans-serif; margin:0; padding:20px;">
  <div style="max-width:760px; margin:0 auto;">
    <div style="text-align:center; padding:20px 0; border-bottom:1px solid #30363d; margin-bottom:20px;">
      <h1 style="margin:0; color:#58a6ff; font-size:24px;">📰 每週洞察 (Weekly Briefing)</h1>
      <p style="color:#8b949e; font-size:13px; margin:8px 0;">
        {total_h} 條 headline · 共 {len(weeks)} 週<br>
        來源: M報 / 馬斯克帝國觀察 / 富果直送 / 股癌 / All-In Podcast
      </p>
      <p style="margin:8px 0;">
        <a href="https://pochih.github.io/stock-calendar/" target="_blank"
           style="color:#58a6ff; text-decoration:none; font-size:13px;">
          → 完整 dashboard
        </a>
      </p>
    </div>
    {weeks_html}
    <div style="text-align:center; color:#8b949e; font-size:11px;
                padding:20px 0; border-top:1px solid #30363d; margin-top:20px;">
      stock-calendar · auto-generated weekly briefing
    </div>
  </div>
</body></html>
'''
    return subject, body


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--week", help="指定週次,如 2026-W25")
    g.add_argument("--latest", type=int, default=1, help="最新 N 週 (預設 1)")
    ap.add_argument("--json", action="store_true", help="輸出 JSON 供程式吃")
    args = ap.parse_args()

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    weeks = data.get("weekly_briefing", [])
    if not weeks:
        print("❌ 沒有 weekly_briefing 資料", file=sys.stderr)
        sys.exit(1)

    if args.week:
        selected = [w for w in weeks if w["week"] == args.week]
        if not selected:
            print(f"❌ 找不到週次 {args.week}", file=sys.stderr)
            print(f"   可用: {', '.join(w['week'] for w in weeks[:10])}...", file=sys.stderr)
            sys.exit(1)
    else:
        selected = weeks[:args.latest]

    subject, body = build_email(selected)

    if args.json:
        print(json.dumps({"subject": subject, "html_body": body, "to": ["b01902068@gmail.com"]},
                         ensure_ascii=False, indent=2))
    else:
        print(f"# Subject: {subject}\n")
        print(f"# (HTML body, {len(body):,} bytes)\n")
        print(body)


if __name__ == "__main__":
    main()
