"""
update_ipos.py — 從 SEC EDGAR 抓最近 S-1 IPO filings 寫進 data.json

Phase 3 自動化:
  - 抓 SEC EDGAR latest filings RSS (公開,無 auth)
  - 過濾 Form S-1 / S-1/A (IPO 註冊書 / 修正)
  - 用關鍵字過濾科技類 (AI / Cloud / Software / Semiconductor / Internet / Biotech)
  - 新條目寫入 ipos 區段,標 (SEC auto-fetch),不覆蓋已有手寫

使用:
  python update_ipos.py              # 抓最近 100 筆 filings
  python update_ipos.py --limit 200  # 抓更多
  python update_ipos.py --dry-run    # 只印不寫

SEC EDGAR 規範:
  - Form S-1: 公司首次公開募股 (IPO) 註冊書
  - Form S-1/A: 修正版 (amendment)
  - 兩者都暗示公司在準備或修正 IPO
  - User-Agent 必須宣告 (SEC 規範): "stock-calendar 1.0 b01902068@gmail.com"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path
from xml.etree import ElementTree as ET

DATA_FILE = Path(__file__).parent / "data.json"

# SEC EDGAR latest filings (Atom feed,公開)
EDGAR_FEED = ("https://www.sec.gov/cgi-bin/browse-edgar"
              "?action=getcompany&type=S-1&dateb=&owner=include&count={limit}&output=atom")

# 必要 User-Agent (SEC 要求識別)
HEADERS = {"User-Agent": "stock-calendar 1.0 b01902068@gmail.com"}

# 科技類過濾關鍵字 (case insensitive)
TECH_KEYWORDS = [
    "AI", "artificial intelligence", "cloud", "saas", "software", "platform",
    "data", "analytics", "machine learning", "ML", "agent", "LLM",
    "semiconductor", "chip", "GPU", "ASIC", "compute", "infrastructure",
    "internet", "fintech", "crypto", "blockchain", "robotics",
    "biotech", "pharma", "medical device", "diagnostic",
    "EV", "electric vehicle", "battery", "energy storage", "solar",
]

# 已經上市或大家都知道在準備 IPO 的不重複加 (用 ipos 既有 company 名 lower 比對)
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=100, help="抓最近 N 筆 filings (預設 100)")
    ap.add_argument("--dry-run", action="store_true", help="只印不寫")
    args = ap.parse_args()

    if not DATA_FILE.exists():
        print(f"❌ 找不到 {DATA_FILE}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    existing_companies = {ipo["company"].lower() for ipo in data.get("ipos", [])}

    url = EDGAR_FEED.format(limit=args.limit)
    print(f"📡 抓 SEC EDGAR latest S-1 filings ({args.limit} 筆)...")
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read()
    except Exception as e:
        print(f"❌ SEC 抓取失敗: {e}", file=sys.stderr)
        sys.exit(1)

    # parse Atom
    root = ET.fromstring(body)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entries = root.findall("atom:entry", ns)
    print(f"   ✓ 找到 {len(entries)} 筆 filings\n")

    new_ipos = []
    seen_companies = set()
    for entry in entries:
        title = (entry.find("atom:title", ns).text or "").strip()
        summary_el = entry.find("atom:summary", ns)
        summary = (summary_el.text or "").strip() if summary_el is not None else ""
        link_el = entry.find("atom:link", ns)
        link = link_el.get("href") if link_el is not None else ""
        updated_el = entry.find("atom:updated", ns)
        updated = (updated_el.text or "").strip()[:10] if updated_el is not None else ""

        # title 通常是 "S-1 - Company Name (CIK 000XXX)"
        m = re.match(r"S-1(?:/A)?\s*-\s*(.+?)\s*\(", title)
        if not m:
            continue
        company = m.group(1).strip()
        is_amendment = "/A" in title

        # 已有 → 不重複加 (但若是 amendment 可改寫狀態)
        if company.lower() in existing_companies or company.lower() in seen_companies:
            continue
        seen_companies.add(company.lower())

        # 科技類過濾 (用 title + summary)
        haystack = (title + " " + summary).lower()
        matched_kw = [kw for kw in TECH_KEYWORDS if kw.lower() in haystack]
        if not matched_kw:
            continue  # 不是科技類,跳過

        new_ipos.append({
            "company": company,
            "status": f"{'S-1/A' if is_amendment else 'S-1'} 已遞交 ({updated})",
            "valuation": "未公布",
            "note": f"SEC EDGAR auto-fetch · 關鍵字: {', '.join(matched_kw[:3])} · {link}",
        })

    print(f"📊 新增 {len(new_ipos)} 家科技類 IPO 候選:\n")
    for ipo in new_ipos:
        print(f"  + {ipo['company']:40s} {ipo['status']}")
        print(f"    {ipo['note'][:100]}")

    if args.dry_run:
        print("\n--- dry-run, 不寫入 ---")
        return

    if not new_ipos:
        print("\n(無新條目)")
        return

    data["ipos"] = data.get("ipos", []) + new_ipos
    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n✅ 寫入 {DATA_FILE.name}")
    print("👉 記得跑 python run.py --no-update --update-only 重新嵌入 index.html")


if __name__ == "__main__":
    main()
