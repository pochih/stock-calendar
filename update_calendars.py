"""
update_calendars.py — 自動更新 data.json 的 fomc / econ / conferences 區段

完全離線:
  - FOMC 硬編碼 2026-2027 官方排程 (每年 12 月可手動更新)
  - Beige Book = FOMC - 2 週 (公開規律)
  - FOMC Minutes = FOMC + 3 週 (公開規律)
  - Humphrey-Hawkins = 2 月 + 7 月中
  - Jackson Hole = 8 月第 4 週 (KC Fed 規律)
  - CPI/PPI/NFP/Retail/PCE 用每月 deterministic 推算 (BLS/BEA 有固定 pattern)
  - Conferences 硬編碼 + 推估每年慣例 (GTC/WWDC/Build/Computex/CES)

使用:
  python update_calendars.py                # 更新到 data.json
  python update_calendars.py --dry-run      # 只印出來不寫入
  python update_calendars.py --year 2027    # 補 2027 (預設 2026+2027)

設計:
  - 保留手寫 note (從 data.json 既有條目搬過來)
  - 新增條目標 (自動產生),如果你手改過 note 就不會被覆蓋
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data.json"

# ─────────────── 官方排程硬編碼 ───────────────

# FOMC 從 federalreserve.gov/monetarypolicy/fomccalendars.htm 抓
FOMC_OFFICIAL = {
    # (date, sep_meeting)
    2026: [
        ("2026-01-28", False),  # 兩天會議的最後一天
        ("2026-03-18", True),
        ("2026-04-29", False),
        ("2026-06-17", True),
        ("2026-07-29", False),
        ("2026-09-16", True),
        ("2026-10-28", False),
        ("2026-12-09", True),
    ],
    2027: [
        ("2027-01-27", False),
        ("2027-03-17", True),
        ("2027-04-28", False),
        ("2027-06-09", True),
        ("2027-07-28", False),
        ("2027-09-15", True),
        ("2027-10-27", False),
        ("2027-12-08", True),
    ],
}

# 已知科技發表會 (推估或官方公告)
CONFERENCES_OFFICIAL = {
    2026: [
        # (date, name, tickers, bias, note)
        ("2026-01-06", "CES 2026 Las Vegas (Tech 開春大會)",
         ["NVDA", "AMD", "INTC", "QCOM", "AAPL"],
         "neutral", "1/6-1/9 ; AI PC / Auto / IoT 重點"),
        ("2026-03-17", "NVIDIA GTC 2026 San Jose (Jensen keynote)",
         ["NVDA", "AMD", "AVGO", "TSM", "MRVL"],
         "up", "Vera CPU + Blackwell Ultra + Rubin 路線圖"),
        ("2026-05-19", "Microsoft Build 2026",
         ["MSFT", "NVDA", "AMD", "INTC"],
         "up", "MAI 模型 + Copilot Agent + Azure"),
        ("2026-05-22", "Anthropic Code with Claude 2026 (推測)",
         ["ANTH", "AMZN", "GOOGL"],
         "up", "Fable 5 / Mythos / Claude Code 重大更新"),
        ("2026-06-01", "Computex 2026 Taipei",
         ["NVDA", "AMD", "ASUS", "MSI"],
         "neutral", "6/1-6/5 ; AI PC + Server ODM"),
        ("2026-06-08", "Apple WWDC 2026",
         ["AAPL", "GOOGL", "NVDA"],
         "neutral", "AFM3 + New Siri + Gemini 合作"),
        ("2026-06-18", "Google I/O 2026 (推估)",
         ["GOOGL", "NVDA"],
         "up", "Gemini 4 / TPU v8 預估時段"),
        ("2026-08-21", "Jackson Hole Economic Symposium",
         [],
         "neutral", "KC Fed 主辦,主席演說常為市場轉折點"),
        ("2026-10-06", "OpenAI DevDay 2026 (推估)",
         ["OPENAI", "MSFT", "AMZN"],
         "up", "GPT-6 / 新 Agent / Hardware 可能首發"),
    ],
    2027: [
        ("2027-01-05", "CES 2027 Las Vegas (推估)",
         ["NVDA", "AMD", "INTC", "QCOM", "AAPL"],
         "neutral", "AI PC / Auto / IoT 重點"),
        ("2027-03-16", "NVIDIA GTC 2027 (推估)",
         ["NVDA", "AMD", "AVGO", "TSM"],
         "up", "Rubin Ultra / Feynman 預估"),
    ],
}

# ─────────────── deterministic date 計算 helpers ───────────────

def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """回傳該月第 n 個 weekday (0=Mon, 6=Sun)。n 從 1 開始。"""
    d = date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    return d + timedelta(days=offset + (n - 1) * 7)


def last_weekday(year: int, month: int, weekday: int) -> date:
    """該月最後一個 weekday"""
    # 從下個月 1 日往前推
    if month == 12:
        d = date(year + 1, 1, 1)
    else:
        d = date(year, month + 1, 1)
    d -= timedelta(days=1)
    offset = (d.weekday() - weekday) % 7
    return d - timedelta(days=offset)


# ─────────────── econ 生成器 ───────────────

def gen_econ_entries(year: int) -> list[dict]:
    """生成全年經濟數據事件 (依 BLS/BEA 規律)。
    所有日期皆為估算,實際發布以官方公告為準。
    """
    out = []

    # CPI: 通常每月第二週週二 / 三 / 四 (BLS 排程跟著當月而動)
    # 簡化: 用第 2 個週三作 baseline (大多月份吻合)
    for m in range(1, 13):
        # CPI 報的是上個月,1 月發布 12 月 CPI
        prev_m = 12 if m == 1 else m - 1
        prev_y = year - 1 if m == 1 else year
        d = nth_weekday(year, m, 2, 2)  # 週三 (2)
        out.append({
            "date": d.isoformat(),
            "type": "CPI",
            "period": f"{prev_m} 月",
            "note": "8:30 ET (估算,實際以 BLS 公告為準)",
        })

    # PPI: 通常 CPI 隔天 (週四)
    for m in range(1, 13):
        prev_m = 12 if m == 1 else m - 1
        d = nth_weekday(year, m, 2, 2) + timedelta(days=1)
        out.append({
            "date": d.isoformat(),
            "type": "PPI",
            "period": f"{prev_m} 月",
            "note": "8:30 ET (估算)",
        })

    # NFP (Non-Farm Payrolls): 每月第一個週五
    for m in range(1, 13):
        prev_m = 12 if m == 1 else m - 1
        d = nth_weekday(year, m, 4, 1)  # 週五 (4)
        out.append({
            "date": d.isoformat(),
            "type": "NFP",
            "period": f"{prev_m} 月",
            "note": "8:30 ET (估算,實際以 BLS 公告為準)",
        })

    # PCE (Personal Income & Outlays): 每月最後一個週五前後
    for m in range(1, 13):
        prev_m = 12 if m == 1 else m - 1
        d = last_weekday(year, m, 4)  # 最後週五
        out.append({
            "date": d.isoformat(),
            "type": "PCE",
            "period": f"{prev_m} 月",
            "note": "8:30 ET,Fed 最愛通膨指標 (估算)",
        })

    # 零售銷售: 通常每月 15 號前後 (BLS Census)
    for m in range(1, 13):
        prev_m = 12 if m == 1 else m - 1
        # 15 號附近找最近的週四 (Census 通常週二/四發)
        target = date(year, m, 15)
        offset = (3 - target.weekday()) % 7  # 週四 (3)
        d = target + timedelta(days=offset)
        # 若週四 > 19 號就改前一週
        if d.day > 19:
            d -= timedelta(days=7)
        out.append({
            "date": d.isoformat(),
            "type": "零售銷售",
            "period": f"{prev_m} 月",
            "note": "8:30 ET (估算)",
        })

    # GDP advance (Q1 末季 + 4 月底發布; Q2 末季 + 7 月底; Q3 末季 + 10 月底; Q4 + 隔年 1 月底)
    gdp_releases = [
        (year, 1, 30, f"{year-1} Q4 GDP advance"),
        (year, 4, 30, f"{year} Q1 GDP advance"),
        (year, 7, 30, f"{year} Q2 GDP advance"),
        (year, 10, 30, f"{year} Q3 GDP advance"),
    ]
    for y, m, d_, label in gdp_releases:
        target = date(y, m, d_)
        # 找最近的週四
        offset = (3 - target.weekday()) % 7
        d = target + timedelta(days=offset - 7 if offset > 3 else offset)
        out.append({
            "date": d.isoformat(),
            "type": "GDP",
            "period": label.replace(f"{year} ", "").replace(f"{year-1} ", "去年 "),
            "note": "8:30 ET (advance estimate, 估算)",
        })

    return out


# ─────────────── FOMC 衍生事件 (Beige Book / Minutes / H-H) ───────────────

def gen_fomc_derived(year: int) -> tuple[list[dict], list[dict]]:
    """回傳 (econ 衍生事件, conferences 衍生事件)"""
    econ_entries = []
    conf_entries = []

    fomc = FOMC_OFFICIAL.get(year, [])
    for fomc_date_str, sep in fomc:
        fd = date.fromisoformat(fomc_date_str)
        # Beige Book = FOMC - 2 週的週三
        bb = fd - timedelta(days=14)
        # 調整到週三 (FOMC 通常週三,所以 bb 也大致週三)
        offset = (2 - bb.weekday()) % 7
        if offset > 3:
            offset -= 7
        bb = bb + timedelta(days=offset)
        econ_entries.append({
            "date": bb.isoformat(),
            "type": "Beige Book",
            "period": f"FOMC {fd.month}/{fd.day} 前",
            "note": "區域經濟現況描述,FOMC 前 2 週發布",
        })
        # Minutes = FOMC + 3 週的週三
        mn = fd + timedelta(days=21)
        offset = (2 - mn.weekday()) % 7
        if offset > 3:
            offset -= 7
        mn = mn + timedelta(days=offset)
        sep_tag = "★ 含點陣圖會議的紀要,影響更大" if sep else "FOMC 後 3 週發布"
        econ_entries.append({
            "date": mn.isoformat(),
            "type": "FOMC Minutes",
            "period": f"{fd.month}/{fd.day} 會議",
            "note": sep_tag,
        })

    # Humphrey-Hawkins: 2 月中 + 7 月中 (週二或三作證)
    for m in (2, 7):
        d = nth_weekday(year, m, 1, 3)  # 第 3 個週二
        period = "上半年國會作證" if m == 7 else "下半年國會作證 (年初)"
        econ_entries.append({
            "date": d.isoformat(),
            "type": "Humphrey-Hawkins",
            "period": period,
            "note": "★ Fed 主席半年度貨幣政策報告 (參議院 + 眾議院)。鷹鴿派表態關鍵",
        })

    return econ_entries, conf_entries


# ─────────────── merge helpers ───────────────

def merge_entries(orig: list[dict], new: list[dict], key_fn) -> tuple[list[dict], int, int]:
    """合併,以 key_fn(entry) 為唯一鍵。原條目優先 (保留手寫 note)。
    回傳 (合併後 list, 新增數, 既有保留數)。
    """
    seen = {}
    for e in orig:
        seen[key_fn(e)] = e
    added = 0
    kept = len(orig)
    for n in new:
        k = key_fn(n)
        if k not in seen:
            seen[k] = n
            added += 1
    merged = sorted(seen.values(), key=lambda e: e["date"])
    return merged, added, kept


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="只印出來不寫入")
    ap.add_argument("--years", nargs="+", type=int, default=[2026, 2027],
                    help="處理年份 (預設 2026 2027)")
    args = ap.parse_args()

    if not DATA_FILE.exists():
        print(f"❌ 找不到 {DATA_FILE}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    # === FOMC ===
    new_fomc = []
    for y in args.years:
        for d_str, sep in FOMC_OFFICIAL.get(y, []):
            new_fomc.append({
                "date": d_str,
                "sep": sep,
                "note": "★ 含點陣圖 + Powell 記者會" if sep else "無點陣圖,波動較小",
            })

    orig_fomc = data.get("fomc", [])
    merged_fomc, added_f, kept_f = merge_entries(
        orig_fomc, new_fomc, key_fn=lambda e: e["date"]
    )
    print(f"📅 FOMC: 原 {kept_f} 場 + 新增 {added_f} 場 = {len(merged_fomc)} 場")

    # === econ ===
    new_econ = []
    for y in args.years:
        new_econ.extend(gen_econ_entries(y))
        derived_econ, _ = gen_fomc_derived(y)
        new_econ.extend(derived_econ)

    orig_econ = data.get("econ", [])
    merged_econ, added_e, kept_e = merge_entries(
        orig_econ, new_econ, key_fn=lambda e: (e["date"], e["type"])
    )
    print(f"📊 econ: 原 {kept_e} 筆 + 新增 {added_e} 筆 = {len(merged_econ)} 筆")

    # === conferences ===
    new_conf = []
    for y in args.years:
        for d_str, name, tickers, bias, note in CONFERENCES_OFFICIAL.get(y, []):
            new_conf.append({
                "date": d_str,
                "name": name,
                "tickers": tickers,
                "bias": bias,
                "note": note,
            })

    orig_conf = data.get("conferences", [])
    merged_conf, added_c, kept_c = merge_entries(
        orig_conf, new_conf, key_fn=lambda e: (e["date"], e["name"])
    )
    print(f"🎤 conferences: 原 {kept_c} 場 + 新增 {added_c} 場 = {len(merged_conf)} 場")

    if args.dry_run:
        print("\n--- dry-run, 不寫入 ---")
        # 印出新增的條目
        new_econ_keys = {(e["date"], e["type"]) for e in new_econ}
        existing_keys = {(e["date"], e["type"]) for e in orig_econ}
        for e in merged_econ:
            k = (e["date"], e["type"])
            if k in new_econ_keys and k not in existing_keys:
                print(f"  + {e['date']} {e['type']:15s} {e.get('period','')}")
        return

    # write
    data["fomc"] = merged_fomc
    data["econ"] = merged_econ
    data["conferences"] = merged_conf
    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n✅ 寫入 {DATA_FILE.name}")
    print("👉 記得跑 python run.py --no-update --update-only 重新嵌入 index.html")


if __name__ == "__main__":
    main()
