"""
更新 data.json 中的 tickers 區段 — 抓最新價格、PE、Fwd PE、毛利、FCF、殖利率。
其他區段(財報日、IPO、PolyMarket、發表會、FOMC、經濟數據)維持手動維護或從別處抓。

使用:
    pip install yfinance requests
    python update_data.py

可選旗標:
    python update_data.py --polymarket   # 同時更新 PolyMarket 熱門市場
    python update_data.py --earnings     # 用 yfinance 重抓財報日 (覆蓋 6 月 / H2)
    python update_data.py --all          # 全部更新
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data.json"


# ────────────────── Helper ──────────────────
def fmt_price(v: float | None) -> str:
    if v is None:
        return "—"
    if v >= 1000:
        return f"${v:,.0f}"
    return f"${v:.2f}"


def fmt_pct(v: float | None) -> str:
    return f"{v * 100:.1f}%" if v is not None else "—"


def fmt_billion(v: float | None) -> str:
    if v is None or v == 0:
        return "—"
    if abs(v) >= 1e9:
        return f"${v / 1e9:.1f}B"
    if abs(v) >= 1e6:
        return f"${v / 1e6:.0f}M"
    return f"${v:,.0f}"


def fmt_korean_won(v: float | None) -> str:
    return f"₩{v:,.0f}" if v else "—"


# ────────────────── yfinance 抓 ticker ──────────────────
def fetch_ticker(symbol: str, is_korean: bool = False) -> dict:
    import yfinance as yf

    try:
        tk = yf.Ticker(symbol)
        info = tk.info or {}

        # 價格
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if price is None:
            hist = tk.history(period="5d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])

        # PE
        pe = info.get("trailingPE")
        fwd_pe = info.get("forwardPE")
        gross_margin = info.get("grossMargins")
        fcf = info.get("freeCashflow")
        div_yield = info.get("dividendYield")  # yfinance 直接返回比例

        # 30 天 sparkline (限 30 個點,round 至 4 位) + 成交量爆量比 (5d avg / 30d avg)
        sparkline = []
        change_pct = None
        vol_5d_avg = None
        vol_30d_avg = None
        try:
            hist30 = tk.history(period="30d", interval="1d")
            if not hist30.empty:
                closes = hist30["Close"].dropna().tolist()
                if len(closes) >= 2:
                    sparkline = [round(float(c), 4) for c in closes[-30:]]
                    change_pct = round((closes[-1] - closes[0]) / closes[0] * 100, 2)
                # 成交量 (排除 0,有些 ETF/指數會缺)
                if "Volume" in hist30.columns:
                    vols = [v for v in hist30["Volume"].dropna().tolist() if v and v > 0]
                    if len(vols) >= 5:
                        vol_5d_avg = int(sum(vols[-5:]) / 5)
                    if len(vols) >= 10:
                        vol_30d_avg = int(sum(vols) / len(vols))
        except Exception:
            pass

        out = {
            "price": fmt_korean_won(price) if is_korean else fmt_price(price),
            "pe": f"~{pe:.0f}" if pe else "—",
            "fwd_pe": f"~{fwd_pe:.0f}" if fwd_pe else "—",
            "gross_margin": fmt_pct(gross_margin),
            "fcf_ttm": fmt_billion(fcf),
            "div": fmt_pct(div_yield) if div_yield else "0%",
        }
        if sparkline:
            out["sparkline_30d"] = sparkline
        if change_pct is not None:
            out["change_30d_pct"] = change_pct
        if vol_5d_avg is not None:
            out["vol_5d_avg"] = vol_5d_avg
        if vol_30d_avg is not None:
            out["vol_30d_avg"] = vol_30d_avg
        return out
    except Exception as e:
        print(f"  ⚠️  {symbol} 失敗: {e}", file=sys.stderr)
        return {}


def update_tickers(data: dict) -> None:
    print(f"更新 {len(data['tickers'])} 個 ticker...")
    for t in data["tickers"]:
        sym = t["ticker"]
        # 跳過 Private 未上市標的 (Anthropic / OpenAI 等估值寫死,不抓 yfinance)
        if t.get("type") == "Private":
            continue
        # 跳過 VIX(需特殊處理)
        if sym == "VIX":
            try:
                import yfinance as yf
                v = yf.Ticker("^VIX").info.get("regularMarketPrice")
                if v:
                    t["price"] = f"~{v:.1f}"
            except Exception:
                pass
            continue
        is_korean = sym.endswith(".KS")
        result = fetch_ticker(sym, is_korean)
        if result:
            t.update(result)
            print(f"  ✓ {sym} {t['price']} PE={t['pe']}")


# ────────────────── 抓 PolyMarket (公開 API) ──────────────────
def update_polymarket(data: dict, limit: int = 15) -> None:
    """Gamma API: https://gamma-api.polymarket.com/markets"""
    import requests

    print("更新 PolyMarket...")
    try:
        r = requests.get(
            "https://gamma-api.polymarket.com/markets",
            params={"active": "true", "closed": "false", "limit": 50,
                    "order": "volume24hr", "ascending": "false"},
            timeout=15,
        )
        markets = r.json()
    except Exception as e:
        print(f"  ⚠️  Polymarket API 失敗: {e}", file=sys.stderr)
        return

    KEYWORDS = ["Fed", "rate", "AI", "GPT", "Claude", "Gemini", "NVDA", "Bitcoin",
                "BTC", "election", "midterm", "recession", "IPO", "OpenAI", "Anthropic", "TSMC"]
    filtered = []
    for m in markets:
        title = m.get("question", "")
        if not any(k.lower() in title.lower() for k in KEYWORDS):
            continue
        try:
            outcomes = json.loads(m.get("outcomes", "[]"))
            prices = json.loads(m.get("outcomePrices", "[]"))
            prob_str = ", ".join(
                f"{o} {float(p) * 100:.0f}%" for o, p in zip(outcomes, prices)
            )[:80]
        except Exception:
            prob_str = "—"
        vol = m.get("volume24hr", 0) or 0
        filtered.append({
            "title": title[:120],
            "prob": prob_str,
            "vol": f"${vol / 1e6:.1f}M" if vol > 1e6 else f"${vol / 1e3:.0f}K",
            "url": f"https://polymarket.com/event/{m.get('slug', '')}",
            "tag": classify_tag(title),
        })
        if len(filtered) >= limit:
            break

    if filtered:
        data["polymarket"] = filtered
        print(f"  ✓ 寫入 {len(filtered)} 個市場")


def classify_tag(title: str) -> str:
    t = title.lower()
    if any(k in t for k in ["fed", "rate", "fomc"]):
        return "Fed"
    if any(k in t for k in ["ai", "gpt", "claude", "gemini", "openai", "anthropic"]):
        return "AI"
    if any(k in t for k in ["bitcoin", "btc", "eth", "crypto"]):
        return "Crypto"
    if any(k in t for k in ["election", "midterm", "trump", "biden"]):
        return "Politics"
    if "ipo" in t:
        return "IPO"
    if "recession" in t or "gdp" in t:
        return "Macro"
    return "Other"


# ────────────────── 抓財報日 (Finnhub or yfinance) ──────────────────
def update_earnings(data: dict, days: int = 180) -> None:
    """用 yfinance 重抓未來 N 天財報日,覆蓋 june_2026_earnings / h2_2026_earnings。

    時區處理:
      - 美股 (無後綴): yfinance 回 ET 日期。財報多半盤前 (BMO ≈ ET 8:00)
        或盤後 (AMC ≈ ET 16:00)。盤後 AMC 在台北為隔日凌晨,但行事曆以
        ET 當日為主 (台股投資人通常看『美股 6/15 盤後』而非『台北 6/16 早上』)。
      - 台股 .TW: yfinance 回的就是台北日期,直接用。
      - 韓股 .KS: 韓國 KST = UTC+9 (與台北 UTC+8 差 1 小時),日期級別視為一致。
      - 日股 .T: JST = UTC+9,同上。
    """
    import yfinance as yf

    print(f"重抓未來 {days} 天財報日 (含台股/韓股/日股)...")
    today = date.today()
    until = today + timedelta(days=days)
    june, h2 = [], []

    # 包含所有 Stock,不再 skip .KS / .TW
    symbols = [t["ticker"] for t in data["tickers"]
               if t.get("type") == "Stock"]
    for sym in symbols:
        try:
            tk = yf.Ticker(sym)
            cal = tk.calendar
            if not cal:
                continue
            dates = cal.get("Earnings Date", [])
            if not isinstance(dates, list):
                dates = [dates]
            # 判斷 ticker 市場 + 時區註記
            if sym.endswith(".TW") or sym.endswith(".TWO"):
                tz_note = "TPE"
            elif sym.endswith(".KS"):
                tz_note = "KST"
            elif sym.endswith(".T"):
                tz_note = "JST"
            else:
                tz_note = "ET"
            for d in dates:
                if isinstance(d, datetime):
                    d = d.date()
                if not (today <= d <= until):
                    continue
                rec = {
                    "date": d.isoformat(),
                    "ticker": sym,
                    "company": sym,
                    "fiscal": "TBD",
                    "time": tz_note,
                    "note": "(自動抓取)",
                    "hist_move": "—",
                    "bias": "neutral",
                }
                (june if d.month == 6 and d.year == 2026 else h2).append(rec)
                print(f"  ✓ {sym:10s} {d} [{tz_note}]")
        except Exception as e:
            print(f"  ⚠️  {sym}: {e}", file=sys.stderr)

    # 合併:手寫優先 (有 hist_move != '—' 或 note != '(自動抓取)')
    # 若 ticker 已有手寫項,完全跳過 yfinance 同 ticker 的 record (避免時區差造成
    # 同一場財報出現在相鄰兩日)
    def merge(orig: list, new: list) -> list:
        manual_tickers = {
            o["ticker"] for o in orig
            if o.get("note", "") != "(自動抓取)" and o.get("hist_move", "—") != "—"
        }
        seen = {(o["ticker"], o["date"][:10]) for o in orig}
        out = list(orig)
        for n in new:
            if n["ticker"] in manual_tickers:
                continue  # 已有手寫,不採 yfinance
            if (n["ticker"], n["date"][:10]) in seen:
                continue
            out.append(n)
        out.sort(key=lambda x: x["date"])
        return out

    data["june_2026_earnings"] = merge(data["june_2026_earnings"], june)
    data["h2_2026_earnings"] = merge(data["h2_2026_earnings"], h2)


# ────────────────── Main ──────────────────
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--polymarket", action="store_true")
    ap.add_argument("--earnings", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--no-tickers", action="store_true", help="跳過 ticker 更新")
    args = ap.parse_args()

    if not DATA_FILE.exists():
        print(f"❌ 找不到 {DATA_FILE}", file=sys.stderr)
        sys.exit(1)

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    if not args.no_tickers:
        update_tickers(data)
    if args.polymarket or args.all:
        update_polymarket(data)
    if args.earnings or args.all:
        update_earnings(data)

    data["_meta"]["generated_at"] = date.today().isoformat()
    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n✅ 寫入 {DATA_FILE}")
    print("👉 打開 index.html (建議用本地 server):")
    print("   cd stock-calendar && python -m http.server 8080")
    print("   然後開啟 http://localhost:8080/")


if __name__ == "__main__":
    main()
