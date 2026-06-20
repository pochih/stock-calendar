"""
send_briefing.py — 將 weekly_briefing 某一週轉成 mobile-friendly HTML email

使用:
  python send_briefing.py                 # 預設輸出最新一週
  python send_briefing.py --week 2026-W25 # 指定週次
  python send_briefing.py --latest 2      # 最新 2 週合併
  python send_briefing.py --json          # 輸出 {subject, html} JSON 給程式吃

輸出:
  stdout 印出 markdown header + 完整 HTML
  --json 模式輸出 {"subject": "...", "html_body": "..."}

設計重點 (mobile-friendly):
- viewport meta + responsive max-width
- table-based layout (Gmail 對 flex 支援差)
- 字體 14-16px (手機可讀)
- 跟隨系統 dark mode (meta name="color-scheme")
- inline style only (Gmail clipper 會吃掉 <style>)
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
    "蘋果": "#8b949e",
    "Tesla": "#ffa657", "Tesla / FSD": "#ffa657", "Tesla / Robotaxi": "#ffa657",
    "馬斯克": "#ffa657", "SpaceX": "#ffa657", "Intel 復活": "#d29922",
    "台股個股": "#58a6ff", "台股深度": "#58a6ff", "股癌觀點": "#58a6ff",
}

# 統一字體 stack (放大版,手機友善)
FONT_STACK = (
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Microsoft JhengHei', "
    "'PingFang TC', 'Noto Sans TC', Roboto, sans-serif"
)


def esc(s: str) -> str:
    return html.escape(str(s or ""), quote=True)


def render_chip(text: str, bg: str, fg: str, font_size: str = "12px", mono: bool = False) -> str:
    family = "Consolas, monospace" if mono else FONT_STACK
    return (
        f'<span style="display:inline-block; background:{bg}; color:{fg}; '
        f'padding:3px 9px; margin:2px 4px 2px 0; border-radius:4px; '
        f'font-size:{font_size}; font-family:{family}; line-height:1.4;">{esc(text)}</span>'
    )


def render_headline(h: dict) -> str:
    cat = h.get("category", "")
    color = CAT_COLOR.get(cat, "#58a6ff")
    tickers = h.get("tickers") or []
    themes = h.get("themes_touched") or []

    # category badge + title 用 table 包,避免 flex 在 Gmail 出包
    title_block = f'''
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
       style="margin-bottom:10px;">
  <tr>
    <td style="vertical-align:top; padding-bottom:6px;">
      {render_chip(cat, color, "#ffffff", "12px")}
    </td>
  </tr>
  <tr>
    <td style="font-size:17px; font-weight:700; color:#1f2937; line-height:1.4;
               font-family:{FONT_STACK};">{esc(h.get("title", ""))}</td>
  </tr>
</table>
'''

    ticker_html = ""
    if tickers:
        chips = "".join(render_chip(t, "#dbeafe", "#1e40af", "12px", mono=True) for t in tickers)
        ticker_html = f'<div style="margin:8px 0;">{chips}</div>'

    theme_html = ""
    if themes:
        chips = "".join(render_chip(f"🏷️ {t}", "#f3f4f6", "#6b7280", "11px") for t in themes)
        theme_html = f'<div style="margin-top:10px;">{chips}</div>'

    sections = []
    for key, label in [("summary", "摘要"), ("stance", "立場"), ("implication", "含意")]:
        v = h.get(key)
        if v:
            sections.append(
                f'<div style="margin:8px 0; font-size:14px; line-height:1.7; color:#1f2937; '
                f'font-family:{FONT_STACK};">'
                f'<span style="display:inline-block; background:#e0e7ff; color:#3730a3; '
                f'padding:1px 7px; border-radius:3px; font-size:12px; font-weight:700; '
                f'margin-right:6px;">{label}</span>{esc(v)}</div>'
            )
    body = "".join(sections)

    return f'''
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
       style="background:#ffffff; border:1px solid #e5e7eb; border-radius:8px;
              margin-bottom:14px; border-left:4px solid {color};">
  <tr>
    <td style="padding:14px 16px;">
      {title_block}
      {ticker_html}
      {body}
      {theme_html}
    </td>
  </tr>
</table>
'''


def render_week(w: dict) -> str:
    sources = " · ".join(esc(s) for s in (w.get("sources") or []))
    headlines_html = "".join(render_headline(h) for h in (w.get("headlines") or []))
    return f'''
<table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
       style="background:#f9fafb; border:1px solid #e5e7eb; border-radius:10px;
              margin-bottom:20px;">
  <tr>
    <td style="padding:16px;">
      <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
             style="border-bottom:1px solid #e5e7eb; margin-bottom:14px;">
        <tr>
          <td style="padding-bottom:10px;">
            <div style="font-size:20px; font-weight:700; color:#1e40af; font-family:{FONT_STACK};">
              📅 {esc(w["week"])}
            </div>
            <div style="color:#6b7280; font-size:13px; margin-top:4px; font-family:{FONT_STACK};">
              {esc(w["date_range"])}
            </div>
            <div style="color:#6b7280; font-size:12px; margin-top:6px;
                        font-family:{FONT_STACK}; line-height:1.6;">
              📚 {sources}
            </div>
          </td>
        </tr>
      </table>
      {headlines_html}
    </td>
  </tr>
</table>
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
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="color-scheme" content="light dark">
  <meta name="supported-color-schemes" content="light dark">
  <meta name="format-detection" content="telephone=no, date=no, address=no, email=no">
  <title>📰 每週洞察 {esc(weeks[0]["week"])}</title>
</head>
<body style="margin:0; padding:0; background:#f3f4f6; font-family:{FONT_STACK};
             -webkit-text-size-adjust:100%; -ms-text-size-adjust:100%;">
  <!-- preheader (gmail inbox 預覽文字,但不顯示在信件內) -->
  <div style="display:none; max-height:0; overflow:hidden; opacity:0;">
    {total_h} 條 headline · 共 {len(weeks)} 週 · 點開看本週 AI / 美股 / 台股重點
  </div>

  <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
         style="background:#f3f4f6;">
    <tr>
      <td align="center" style="padding:16px 12px;">
        <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%"
               style="max-width:640px; margin:0 auto;">

          <!-- header -->
          <tr>
            <td style="background:#ffffff; border-radius:10px; padding:20px 18px;
                       text-align:center; margin-bottom:16px;">
              <h1 style="margin:0 0 8px 0; color:#1e40af; font-size:22px; font-weight:700;
                         font-family:{FONT_STACK};">
                📰 每週洞察
              </h1>
              <div style="color:#6b7280; font-size:14px; line-height:1.6; font-family:{FONT_STACK};">
                {total_h} 條 headline · 共 {len(weeks)} 週<br>
                <span style="font-size:12px;">M報 / 馬斯克帝國觀察 / 富果直送 / 股癌 / All-In</span>
              </div>
              <div style="margin-top:12px;">
                <a href="https://pochih.github.io/stock-calendar/" target="_blank"
                   style="display:inline-block; background:#1e40af; color:#ffffff;
                          padding:10px 20px; border-radius:6px; text-decoration:none;
                          font-size:14px; font-weight:600; font-family:{FONT_STACK};">
                  → 完整 dashboard
                </a>
              </div>
            </td>
          </tr>
          <tr><td style="height:16px; line-height:16px;">&nbsp;</td></tr>

          <!-- weeks -->
          <tr>
            <td>
              {weeks_html}
            </td>
          </tr>

          <!-- footer -->
          <tr>
            <td style="text-align:center; color:#9ca3af; font-size:11px;
                       padding:20px 16px; font-family:{FONT_STACK};">
              stock-calendar · auto-generated weekly briefing<br>
              <a href="https://pochih.github.io/stock-calendar/" target="_blank"
                 style="color:#6b7280; text-decoration:underline;">pochih.github.io/stock-calendar</a>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>
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
