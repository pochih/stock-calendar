"""
run.py — 一鍵更新 + 啟動 dashboard

1. 抓 yfinance 即時資料 + PolyMarket 熱門市場
2. 寫入 data.json,加上時間戳 + version (semver auto-bump)
3. 啟動本地 HTTP server (port 8080)
4. 自動開瀏覽器到 index.html

使用:
    pip install yfinance requests
    python run.py                 # 全部:更新 + 啟動
    python run.py --no-update     # 只啟動 (不抓新資料)
    python run.py --no-open       # 只更新 + server (不開瀏覽器)
    python run.py --update-only   # 只更新資料,不啟動 server
    python run.py --port 9000     # 指定 port
"""

from __future__ import annotations

import argparse
import http.server
import json
import socketserver
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path

# Windows cmd 預設 cp1252 不認 emoji,強制 utf-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).parent
DATA_FILE = ROOT / "data.json"
HTML_FILE = ROOT / "index.html"

# ────────────────── 版本管理 ──────────────────
def bump_version(old: str | None) -> str:
    """auto-bump patch version: 0.1.0 → 0.1.1"""
    if not old or not isinstance(old, str):
        return "0.1.0"
    parts = old.split(".")
    if len(parts) != 3 or not all(p.isdigit() for p in parts):
        return "0.1.0"
    major, minor, patch = map(int, parts)
    return f"{major}.{minor}.{patch + 1}"


def stamp_meta(data: dict, sources: list[str]) -> None:
    now = datetime.now()
    meta = data.get("_meta", {})
    meta["generated_at"] = now.strftime("%Y-%m-%d %H:%M:%S")
    meta["generated_iso"] = now.isoformat(timespec="seconds")
    meta["version"] = bump_version(meta.get("version"))
    meta["sources_updated"] = sources
    meta.setdefault("note", "靜態快照。執行 run.py 重抓最新數據。")
    data["_meta"] = meta


# ────────────────── 抓資料 ──────────────────
def update_tickers(data: dict) -> bool:
    try:
        import yfinance as yf
    except ImportError:
        print("⚠️  yfinance 未安裝,跳過 ticker 更新 (pip install yfinance)", file=sys.stderr)
        return False

    # 預先抓非 USD 匯率 (to USD)
    fx_cache: dict[str, float] = {"USD": 1.0}
    def get_fx_to_usd(curr: str) -> float:
        if curr in fx_cache:
            return fx_cache[curr]
        try:
            # yfinance: TWDUSD=X, KRWUSD=X, ...
            ticker = f"{curr}USD=X"
            hist = yf.Ticker(ticker).history(period="5d")
            rate = float(hist["Close"].iloc[-1]) if not hist.empty else None
            if rate:
                fx_cache[curr] = rate
                print(f"  💱 {curr}→USD = {rate:.6f}")
                return rate
        except Exception as e:
            print(f"  ⚠️  {curr} 匯率抓不到: {e}", file=sys.stderr)
        fx_cache[curr] = None
        return None

    print(f"📊 更新 {len(data['tickers'])} 個 ticker...")
    success = 0
    for t in data["tickers"]:
        sym = t["ticker"]
        # 跳過 Private 未上市標的 (Anthropic / OpenAI 等估值寫死,不抓 yfinance)
        if t.get("type") == "Private":
            continue
        if sym == "VIX":
            try:
                v = yf.Ticker("^VIX").info.get("regularMarketPrice")
                if v:
                    t["price"] = f"~{v:.1f}"
                    success += 1
            except Exception:
                pass
            continue

        is_korean = sym.endswith(".KS")
        is_taiwan = sym.endswith(".TW")
        try:
            tk = yf.Ticker(sym)
            # 用 history 取最新收盤,比 info 可靠 (yfinance 1.4.x 有時回傳異常值)
            hist = tk.history(period="5d")
            price = float(hist["Close"].iloc[-1]) if not hist.empty else None

            info = tk.info or {}
            # sanity check: 若 info 的 currentPrice 與 history 差太多,以 history 為準
            info_price = info.get("currentPrice") or info.get("regularMarketPrice")
            if price and info_price and abs(info_price - price) / price > 0.30:
                # 超過 30% 落差,info 可能異常,用 history
                pass
            elif info_price and not price:
                price = info_price

            if price and price == price:  # NaN 過濾 (NaN != NaN)
                if is_korean:
                    t["price"] = f"₩{price:,.0f}"
                elif is_taiwan:
                    t["price"] = f"NT${price:,.2f}" if price < 100 else f"NT${price:,.0f}"
                else:
                    t["price"] = f"${price:,.0f}" if price >= 1000 else f"${price:.2f}"
            pe = info.get("trailingPE")
            fwd = info.get("forwardPE")
            gm = info.get("grossMargins")
            fcf = info.get("freeCashflow")
            dy = info.get("dividendYield")
            shares = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
            mcap = info.get("marketCap")
            # ETF 用 totalAssets (AUM)
            if not mcap:
                mcap = info.get("totalAssets")

            if pe: t["pe"] = f"~{pe:.0f}"
            if fwd: t["fwd_pe"] = f"~{fwd:.0f}"
            if gm is not None: t["gross_margin"] = f"{gm * 100:.0f}%"
            if fcf:
                # FCF 也統一換成 USD
                fcf_currency = info.get("financialCurrency", "USD")
                if fcf_currency != "USD":
                    rate = get_fx_to_usd(fcf_currency)
                    if rate:
                        fcf = fcf * rate
                t["fcf_ttm"] = (f"${fcf / 1e9:.1f}B" if abs(fcf) >= 1e9
                                else f"${fcf / 1e6:.0f}M")
            if dy is not None:
                # yfinance 1.x 的 dividendYield 已是百分比 (e.g. 1.03 = 1.03%)
                t["div"] = f"{dy:.1f}%"
            if shares:
                t["shares"] = (f"{shares / 1e9:.2f}B" if shares >= 1e9
                               else f"{shares / 1e6:.0f}M")
            if mcap:
                # 統一換算成 USD (非 USD 股票)
                currency = info.get("currency", "USD")
                if currency != "USD":
                    rate = get_fx_to_usd(currency)
                    if rate:
                        mcap_usd = mcap * rate
                    else:
                        # 抓不到匯率,標 ~ 並留當地幣 (避免錯估)
                        t["mcap"] = f"~{mcap / 1e9:.0f}B {currency}"
                        success += 1
                        print(f"  ✓ {sym:8s} {t.get('price', '—'):>12s}  PE={t.get('pe', '—')}  mcap=({currency} 匯率失敗)")
                        continue
                else:
                    mcap_usd = mcap
                t["mcap"] = (f"${mcap_usd / 1e12:.2f}T" if mcap_usd >= 1e12
                             else f"${mcap_usd / 1e9:.1f}B" if mcap_usd >= 1e9
                             else f"${mcap_usd / 1e6:.0f}M")

            success += 1
            print(f"  ✓ {sym:8s} {t.get('price', '—'):>12s}  PE={t.get('pe', '—')}")
        except Exception as e:
            print(f"  ✗ {sym}: {e}", file=sys.stderr)

    print(f"   完成 {success}/{len(data['tickers'])}")

    # 為財報事件補上分析師預期
    update_earnings_consensus(data, fx_cache)

    return success > 0


def update_earnings_consensus(data: dict, fx_cache: dict) -> None:
    """為 june_2026_earnings + h2_2026_earnings 補上分析師 EPS/Rev/PT consensus"""
    try:
        import yfinance as yf
    except ImportError:
        return

    print("📊 抓分析師預期 (EPS/Rev/PT)...")
    all_events = data.get("june_2026_earnings", []) + data.get("h2_2026_earnings", [])
    seen_symbols = set()
    for ev in all_events:
        sym = ev.get("ticker", "").split(" ")[0].split("/")[0].strip()
        if not sym or sym in seen_symbols or sym.endswith(".TW") or sym.endswith(".KS"):
            continue
        seen_symbols.add(sym)
        try:
            tk = yf.Ticker(sym)
            info = tk.info or {}
            # 已有手寫 consensus 就略過 (尊重手動值)
            existing = ev.get("consensus", {}) or {}

            # 目標價
            pt_mean = info.get("targetMeanPrice")
            pt_high = info.get("targetHighPrice")
            pt_low = info.get("targetLowPrice")
            n_analysts = info.get("numberOfAnalystOpinions")
            rec = info.get("recommendationKey", "").replace("_", " ").title()

            consensus = dict(existing)
            if pt_mean and "price_target" not in consensus:
                consensus["price_target"] = (f"${pt_mean:.0f}" +
                    (f" (n={n_analysts})" if n_analysts else "") +
                    (f" [${pt_low:.0f}-${pt_high:.0f}]" if pt_low and pt_high else ""))
            if rec and "rating" not in consensus:
                consensus["rating"] = rec

            # 下季 EPS / Revenue estimate (取最近一季)
            try:
                est = tk.earnings_estimate  # DataFrame
                if est is not None and not est.empty and "0q" in est.index:
                    avg_eps = est.loc["0q", "avg"]
                    if avg_eps and "eps" not in consensus:
                        consensus["eps"] = f"${avg_eps:.2f}"
                rev_est = tk.revenue_estimate
                if rev_est is not None and not rev_est.empty and "0q" in rev_est.index:
                    avg_rev = rev_est.loc["0q", "avg"]
                    growth = rev_est.loc["0q", "growth"]
                    if avg_rev and "revenue" not in consensus:
                        consensus["revenue"] = (f"${avg_rev/1e9:.2f}B" if avg_rev >= 1e9
                                                else f"${avg_rev/1e6:.0f}M")
                    if growth and "yoy_rev" not in consensus:
                        consensus["yoy_rev"] = f"+{growth*100:.0f}%" if growth > 0 else f"{growth*100:.0f}%"
            except Exception:
                pass

            if consensus:
                ev["consensus"] = consensus
                print(f"  ✓ {sym} PT={consensus.get('price_target', '?')} EPS={consensus.get('eps', '?')}")
        except Exception as e:
            print(f"  ✗ {sym}: {e}", file=sys.stderr)


def update_polymarket(data: dict, limit: int = 15) -> bool:
    """用 stdlib urllib;若 SSL 驗證失敗 (企業 MITM proxy),fallback 到不驗證。
    若網域被網路封鎖則保留原本手寫條目。"""
    import urllib.request
    import urllib.parse
    import urllib.error
    import ssl

    print("🎯 抓 PolyMarket 熱門市場...")
    params = urllib.parse.urlencode({
        "active": "true", "closed": "false", "limit": 100,
        "order": "volume24hr", "ascending": "false",
    })
    url = f"https://gamma-api.polymarket.com/markets?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

    def try_fetch(ctx=None):
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            return r.read().decode("utf-8")

    markets = None
    try:
        body = try_fetch()
    except ssl.SSLCertVerificationError:
        print("   ⚠️  SSL 驗證失敗 (企業 proxy),fallback 不驗證", file=sys.stderr)
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            body = try_fetch(ctx)
        except Exception as e:
            print(f"  ✗ {e}", file=sys.stderr)
            return False
    except urllib.error.HTTPError as e:
        peek = e.read(500).decode("utf-8", errors="replace")
        if "封鎖" in peek or "blocked" in peek.lower():
            print("   ⚠️  網域遭網路封鎖 (公司/學校 proxy),保留靜態條目", file=sys.stderr)
        else:
            print(f"  ✗ HTTP {e.code}: {peek[:120]}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"  ✗ {e}", file=sys.stderr)
        return False

    try:
        markets = json.loads(body)
    except json.JSONDecodeError:
        print("   ⚠️  回應非 JSON,可能被 proxy 攔截", file=sys.stderr)
        return False

    if not isinstance(markets, list) or not markets:
        return False

    KEYWORDS = ["fed", "rate", "ai ", "gpt", "claude", "gemini", "nvda", "nvidia",
                "bitcoin", "btc", "election", "midterm", "recession", "ipo",
                "openai", "anthropic", "tsmc", "tesla", "musk", "trump"]
    out = []
    for m in markets:
        title = m.get("question", "")
        if not any(k in title.lower() for k in KEYWORDS):
            continue
        try:
            outs = json.loads(m.get("outcomes", "[]"))
            prices = json.loads(m.get("outcomePrices", "[]"))
            prob = ", ".join(
                f"{o} {float(p) * 100:.0f}%" for o, p in zip(outs, prices)
            )[:80]
        except Exception:
            prob = "—"
        vol = float(m.get("volume24hr", 0) or 0)
        out.append({
            "title": title[:120],
            "prob": prob,
            "vol": f"${vol / 1e6:.1f}M" if vol > 1e6 else f"${vol / 1e3:.0f}K",
            "url": f"https://polymarket.com/event/{m.get('slug', '')}",
            "tag": classify_tag(title),
        })
        if len(out) >= limit:
            break

    if out:
        data["polymarket"] = out
        print(f"   ✓ 寫入 {len(out)} 個市場")
        return True
    print("   (無符合關鍵字的市場)")
    return False


def classify_tag(title: str) -> str:
    t = title.lower()
    if any(k in t for k in ["fed", "rate", "fomc"]): return "Fed"
    if any(k in t for k in ["ai ", "gpt", "claude", "gemini", "openai", "anthropic"]): return "AI"
    if any(k in t for k in ["bitcoin", "btc", "eth", "crypto"]): return "Crypto"
    if any(k in t for k in ["election", "midterm", "trump"]): return "Politics"
    if "ipo" in t: return "IPO"
    if any(k in t for k in ["recession", "gdp"]): return "Macro"
    return "Other"


# ────────────────── HTTP server ──────────────────
class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """除了當靜態檔 server,還支援 POST /update 觸發 yfinance 重抓"""

    def log_message(self, fmt, *args):
        if args and "200" not in str(args):
            sys.stderr.write(f"  [http] {fmt % args}\n")

    def do_POST(self):
        if self.path == "/update":
            print("\n🔄 [/update] 收到重抓請求...")
            try:
                data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
                update_tickers(data)
                update_polymarket(data)
                stamp_meta(data, ["yfinance", "polymarket"])
                DATA_FILE.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                embed_data_into_html()
                resp = {
                    "ok": True,
                    "version": data["_meta"]["version"],
                    "generated_at": data["_meta"]["generated_at"],
                    "updated": len(data.get("tickers", [])),
                }
                body = json.dumps(resp).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                print(f"   ✓ 完成 v{resp['version']}")
            except Exception as e:
                print(f"   ✗ 失敗: {e}", file=sys.stderr)
                body = json.dumps({"ok": False, "error": str(e)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.end_headers()
                self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def end_headers(self):
        # 強制不快取 data.json 與 index.html
        if self.path.startswith("/data.json") or self.path.startswith("/index.html") or self.path == "/":
            self.send_header("Cache-Control", "no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
        super().end_headers()


def embed_data_into_html() -> None:
    """把 data.json 內容嵌入 index.html 的 EMBEDDED_DATA placeholder。
    讓 dashboard 雙擊也能看 (不依賴 server)。"""
    html_path = ROOT / "index.html"
    if not html_path.exists():
        return
    html = html_path.read_text(encoding="utf-8")
    data_json = DATA_FILE.read_text(encoding="utf-8").strip()
    import re
    pattern = re.compile(
        r"/\*__EMBEDDED_DATA_START__\*/.*?/\*__EMBEDDED_DATA_END__\*/",
        re.DOTALL,
    )
    if not pattern.search(html):
        print("⚠️  index.html 缺 EMBEDDED_DATA placeholder,跳過嵌入", file=sys.stderr)
        return
    new = pattern.sub(
        lambda m: f"/*__EMBEDDED_DATA_START__*/{data_json}/*__EMBEDDED_DATA_END__*/",
        html,
    )
    if new != html:
        html_path.write_text(new, encoding="utf-8")
        print(f"📎 已嵌入 data.json 到 index.html ({len(data_json):,} bytes)")


def serve(port: int, open_browser: bool) -> None:
    import os
    os.chdir(ROOT)

    try:
        httpd = socketserver.TCPServer(("127.0.0.1", port), DashboardHandler)
    except OSError as e:
        print(f"❌ Port {port} 無法綁定: {e}", file=sys.stderr)
        print(f"   試試 python run.py --port {port + 1}", file=sys.stderr)
        sys.exit(1)

    url = f"http://localhost:{port}/"
    print(f"\n🌐 Server 啟動: {url}")
    print("   按 Ctrl+C 停止\n")

    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Bye")
        httpd.shutdown()


# ────────────────── Main ──────────────────
def main() -> None:
    ap = argparse.ArgumentParser(description="抓資料 + 啟動 dashboard")
    ap.add_argument("--no-update", action="store_true", help="不抓新資料,只啟動 server")
    ap.add_argument("--no-open", action="store_true", help="不自動開瀏覽器")
    ap.add_argument("--no-polymarket", action="store_true", help="跳過 PolyMarket")
    ap.add_argument("--update-only", action="store_true", help="只更新資料,不起 server")
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()

    if not DATA_FILE.exists():
        print(f"❌ 找不到 {DATA_FILE}", file=sys.stderr)
        sys.exit(1)
    if not HTML_FILE.exists():
        print(f"❌ 找不到 {HTML_FILE}", file=sys.stderr)
        sys.exit(1)

    if not args.no_update:
        t0 = time.time()
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        sources = []
        if update_tickers(data):
            sources.append("yfinance")
        if not args.no_polymarket and update_polymarket(data):
            sources.append("polymarket")

        stamp_meta(data, sources)
        DATA_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        m = data["_meta"]
        print(f"\n✅ 寫入 {DATA_FILE.name}  v{m['version']}  @ {m['generated_at']}  ({time.time() - t0:.1f}s)")
        embed_data_into_html()
    else:
        print("⏭️  跳過資料更新")
        # 即使不抓新資料,也把現有 data.json 嵌入 (確保 file:// 模式 OK)
        embed_data_into_html()

    if not args.update_only:
        serve(args.port, not args.no_open)


if __name__ == "__main__":
    main()
