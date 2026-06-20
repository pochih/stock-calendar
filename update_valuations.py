"""
update_valuations.py — 為個股估值分析 tab 抓資料

從 yfinance 抓:
  - 分析師目標價共識 (mean / median / high / low)
  - 評等分布 (Strong Buy / Buy / Hold / Sell)
  - 多年財測 (EPS / Revenue,FY current / +1y,含 trend)
  - 最近 analyst actions (upgrades/downgrades)
  - 1y 歷史價格 (支撐 / 壓力推導)

計算:
  - 6 個估值模型 (PE / P/S / EV/EBITDA / DCF / Analyst Target / AI Premium PE)
  - 支撐 / 壓力位 (50DMA / 200DMA / 52w high/low / 整數心理關)
  - Fair Value 三段 (bear / base / bull)

多空論點 + briefing_mentions 為手寫常數 (LLM 可後續自動 extract)。

使用:
  python update_valuations.py              # 跑全部 (目前只有 MU)
  python update_valuations.py --ticker MU  # 指定一檔
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
DATA_FILE = ROOT / "data.json"


# ── 每個 ticker 的手工註解 (多空 + briefing mentions + 估值模型參數) ──
TICKER_CONFIG = {
    "MU": {
        "name": "Micron Technology",
        "category_label": "Memory / HBM (cyclical semi)",
        "valuation_params": {
            "fwd_pe_base": 15,       # 歷史 fwd P/E 中位 (Memory 12-18x)
            "fwd_pe_bull": 15,       # AI premium 維持中段
            "ps_base": 3,            # 歷史 P/S 中位 (2-4x)
            "ev_ebitda_base": 10,    # 歷史 EV/EBITDA (8-12x)
            "dcf_disc_rate": 0.10,
            "dcf_fcf_growth_5y": 0.25,  # FCF 5y CAGR
            "dcf_terminal_growth": 0.03,
        },
        "bull_thesis": [
            "HBM3E 訂單能見度到 2027,SK 海力士產能吃緊讓 MU 拿到 NVDA 二供 ~25% 份額",
            "DRAM 價格 6 季連漲,AI server / GPU 需求結構性 (Brad Gerstner / All-In W21 多次提到)",
            "FY27 EPS 共識 $118 vs FY26 $61,接近翻倍成長 — 若維持中段 fwd P/E,目標價自然上修",
            "Coatue Laffont (All-In W23 Summit) 點名:每用戶記憶體需求隨 AI memory/context 可 5x → 重估邏輯仍未走完",
            "FY26 毛利率 58%、ROE ~40%,cyclical 高點但 cash flow 真實",
        ],
        "bear_thesis": [
            "歷史 cyclical:DRAM 每次景氣高峰後股價回吐 50-70% (2018, 2022)",
            "P/S 22x vs 歷史 2-4x 已 fully priced AI 故事 (空頭觀點:Chamath W23 點名記憶體已過熱)",
            "中國長存 (YMTC) NAND 突破 + 國家補貼,DRAM 中國國產替代 2027 前可能放量",
            "Forward PE 9.6x 看似便宜,但前提是 FY27 EPS $118 共識成真 — 若 HBM4 良率不及預期,EPS 砍半即 PE 跳到 20x+",
            "Beta 2.17,跌起來幅度比大盤大 2 倍以上;Memory 一旦轉空頭,52w 跌 50% 是 base case",
        ],
        "briefing_mentions": [
            {"week": "2026-W21", "category": "IPO + 估值",
             "snippet": "Gavin Baker 點出 AI 板塊 cross-sectionally inefficient:memory(SK Hynix 5x / Samsung 6x / Micron 7x)、NVDA(forward PE 低 teens)被低估"},
            {"week": "2026-W23", "category": "IPO + 估值",
             "snippet": "Coatue Laffont 直接點名:沒有 TSMC 級別代工的對應產業,每用戶記憶體需求隨 AI memory/context 可 5x → 重估邏輯仍未走完"},
        ],
    },
}


def safe_float(v, default=None):
    try:
        return float(v) if v is not None else default
    except (TypeError, ValueError):
        return default


def round_price(v):
    if v is None:
        return None
    return round(float(v), 2)


def fetch_yfinance(symbol: str) -> dict:
    """從 yfinance 抓所有需要的欄位,回傳 raw dict (含 None 表示抓不到)"""
    import yfinance as yf

    tk = yf.Ticker(symbol)
    raw = {}

    # 1. info (PE, P/S, mcap, FCF, beta, 52w high/low)
    info = tk.info or {}
    raw["info"] = info

    # 2. analyst price targets
    try:
        raw["price_targets"] = tk.analyst_price_targets or {}
    except Exception as e:
        print(f"  ⚠️  analyst_price_targets fail: {e}", file=sys.stderr)
        raw["price_targets"] = {}

    # 3. recommendations summary (rating distribution)
    try:
        rs = tk.recommendations_summary
        if rs is not None and not rs.empty:
            raw["recommendations"] = rs.to_dict("records")
        else:
            raw["recommendations"] = []
    except Exception as e:
        print(f"  ⚠️  recommendations fail: {e}", file=sys.stderr)
        raw["recommendations"] = []

    # 4. earnings_estimate (EPS forecast)
    try:
        ee = tk.earnings_estimate
        if ee is not None and not ee.empty:
            raw["earnings_estimate"] = ee.reset_index().to_dict("records")
        else:
            raw["earnings_estimate"] = []
    except Exception as e:
        print(f"  ⚠️  earnings_estimate fail: {e}", file=sys.stderr)
        raw["earnings_estimate"] = []

    # 5. revenue_estimate
    try:
        re_ = tk.revenue_estimate
        if re_ is not None and not re_.empty:
            raw["revenue_estimate"] = re_.reset_index().to_dict("records")
        else:
            raw["revenue_estimate"] = []
    except Exception as e:
        print(f"  ⚠️  revenue_estimate fail: {e}", file=sys.stderr)
        raw["revenue_estimate"] = []

    # 6. eps_trend (90d 前的 EPS estimate)
    try:
        et = tk.eps_trend
        if et is not None and not et.empty:
            raw["eps_trend"] = et.reset_index().to_dict("records")
        else:
            raw["eps_trend"] = []
    except Exception as e:
        print(f"  ⚠️  eps_trend fail: {e}", file=sys.stderr)
        raw["eps_trend"] = []

    # 7. upgrades_downgrades (最近 analyst actions)
    try:
        ud = tk.upgrades_downgrades
        if ud is not None and not ud.empty:
            ud_sorted = ud.sort_index(ascending=False).head(8).reset_index()
            raw["upgrades_downgrades"] = ud_sorted.to_dict("records")
        else:
            raw["upgrades_downgrades"] = []
    except Exception as e:
        print(f"  ⚠️  upgrades_downgrades fail: {e}", file=sys.stderr)
        raw["upgrades_downgrades"] = []

    # 8. 1y history (DMA + S/R)
    try:
        hist = tk.history(period="1y", interval="1d")
        if not hist.empty:
            raw["history"] = {
                "closes": [round(float(c), 2) for c in hist["Close"].dropna().tolist()],
                "highs": [round(float(c), 2) for c in hist["High"].dropna().tolist()],
                "lows": [round(float(c), 2) for c in hist["Low"].dropna().tolist()],
            }
        else:
            raw["history"] = {"closes": [], "highs": [], "lows": []}
    except Exception as e:
        print(f"  ⚠️  history fail: {e}", file=sys.stderr)
        raw["history"] = {"closes": [], "highs": [], "lows": []}

    return raw


def build_analyst_consensus(raw: dict) -> dict:
    """從 raw 整理出 analyst_consensus 結構"""
    pt = raw["price_targets"]
    recs = raw["recommendations"]
    info = raw["info"]

    cur_period = next((r for r in recs if str(r.get("period")) == "0m"), {})
    prev_period = next((r for r in recs if str(r.get("period")) == "-1m"), {})

    rating_dist = {k: int(cur_period.get(k, 0) or 0)
                   for k in ["strongBuy", "buy", "hold", "sell", "strongSell"]}
    rating_dist_1m = {k: int(prev_period.get(k, 0) or 0)
                      for k in ["strongBuy", "buy", "hold", "sell", "strongSell"]}

    total = sum(rating_dist.values())
    # 加權平均 1-5 (1=strongBuy, 5=strongSell)
    weighted = (1 * rating_dist["strongBuy"] + 2 * rating_dist["buy"]
                + 3 * rating_dist["hold"] + 4 * rating_dist["sell"]
                + 5 * rating_dist["strongSell"])
    avg_rating = weighted / total if total else None
    label = "—"
    if avg_rating is not None:
        if avg_rating < 1.6: label = "Strong Buy"
        elif avg_rating < 2.4: label = "Buy"
        elif avg_rating < 3.4: label = "Hold"
        elif avg_rating < 4.4: label = "Sell"
        else: label = "Strong Sell"

    return {
        "count": total,
        "rating_dist": rating_dist,
        "rating_dist_1m_ago": rating_dist_1m,
        "avg_rating_score": round(avg_rating, 2) if avg_rating else None,
        "consensus_label": label,
        "price_target": {
            "current": round_price(pt.get("current") or info.get("currentPrice")),
            "mean": round_price(pt.get("mean")),
            "median": round_price(pt.get("median")),
            "high": round_price(pt.get("high")),
            "low": round_price(pt.get("low")),
        },
    }


def build_forecasts(raw: dict) -> list[dict]:
    """整理 EPS / Revenue forecast,只取 0y (current) 與 +1y"""
    ee = {str(r.get("period")): r for r in raw["earnings_estimate"]}
    re_ = {str(r.get("period")): r for r in raw["revenue_estimate"]}
    et = {str(r.get("period")): r for r in raw["eps_trend"]}

    out = []
    period_map = {"0y": "FY 當期", "+1y": "FY +1年", "+2y": "FY +2年"}
    for period, label in period_map.items():
        e = ee.get(period)
        r = re_.get(period)
        t = et.get(period, {})
        if not e and not r:
            continue
        eps_avg = safe_float(e.get("avg")) if e else None
        eps_90d = safe_float(t.get("90daysAgo")) if t else None
        # eps 修正方向
        if eps_avg is not None and eps_90d is not None and eps_90d > 0:
            eps_revision_pct = round((eps_avg - eps_90d) / eps_90d * 100, 1)
        else:
            eps_revision_pct = None

        out.append({
            "period": label,
            "period_key": period,
            "eps_avg": round(eps_avg, 2) if eps_avg else None,
            "eps_low": round(safe_float(e.get("low")), 2) if e and e.get("low") else None,
            "eps_high": round(safe_float(e.get("high")), 2) if e and e.get("high") else None,
            "eps_90d_ago": round(eps_90d, 2) if eps_90d else None,
            "eps_revision_pct": eps_revision_pct,
            "rev_avg_b": round(safe_float(r.get("avg")) / 1e9, 2) if r and r.get("avg") else None,
            "rev_low_b": round(safe_float(r.get("low")) / 1e9, 2) if r and r.get("low") else None,
            "rev_high_b": round(safe_float(r.get("high")) / 1e9, 2) if r and r.get("high") else None,
            "n_analysts": int(e.get("numberOfAnalysts", 0)) if e else 0,
            "growth_pct": round(safe_float(e.get("growth")) * 100, 2) if e and e.get("growth") else None,
        })
    return out


def build_valuation_models(raw: dict, forecasts: list[dict], params: dict, mean_target: float) -> list[dict]:
    """根據既有 forecast + ticker_config 參數計算 6 個估值模型"""
    info = raw["info"]
    fy0 = next((f for f in forecasts if f["period_key"] == "0y"), {})
    fy1 = next((f for f in forecasts if f["period_key"] == "+1y"), {})
    shares = safe_float(info.get("sharesOutstanding"))
    mcap = safe_float(info.get("marketCap"))
    ev = safe_float(info.get("enterpriseValue"))
    ebitda_margin = safe_float(info.get("ebitdaMargins")) or 0.4  # fallback

    models = []

    # 1. Base PE × FY current EPS
    eps0 = fy0.get("eps_avg")
    if eps0:
        p = eps0 * params["fwd_pe_base"]
        models.append({
            "model": f"PE × FY 當期 EPS (歷史均 P/E {params['fwd_pe_base']}x)",
            "implied_price": round(p, 2),
            "rationale": f"Memory cyclical 歷史中段 fwd P/E {params['fwd_pe_base']}x × FY{fy0['period_key']} EPS ${eps0}",
        })

    # 2. Bull PE × FY +1y EPS (AI premium)
    eps1 = fy1.get("eps_avg")
    if eps1:
        p = eps1 * params["fwd_pe_bull"]
        models.append({
            "model": f"PE × FY +1y EPS (AI premium 維持 {params['fwd_pe_bull']}x)",
            "implied_price": round(p, 2),
            "rationale": f"若 HBM 故事兌現,FY+1 EPS ${eps1} 維持中段 P/E",
        })

    # 3. P/S × FY current Revenue
    rev0 = fy0.get("rev_avg_b")
    if rev0 and shares:
        rev_per_share = rev0 * 1e9 / shares
        p = rev_per_share * params["ps_base"]
        models.append({
            "model": f"P/S × FY 當期 Rev (歷史均 P/S {params['ps_base']}x)",
            "implied_price": round(p, 2),
            "rationale": f"Memory 歷史 P/S 2-4x 取中位 {params['ps_base']}x × FY 當期 ${rev0}B 營收",
        })

    # 4. EV/EBITDA
    if rev0 and shares and ev and mcap:
        ebitda = rev0 * 1e9 * ebitda_margin
        target_ev = ebitda * params["ev_ebitda_base"]
        net_debt = ev - mcap
        target_mcap = target_ev - net_debt
        p = target_mcap / shares
        models.append({
            "model": f"EV/EBITDA × FY 當期 ({params['ev_ebitda_base']}x)",
            "implied_price": round(p, 2),
            "rationale": f"Cyclical semi 歷史 EV/EBITDA 8-12x,EBITDA 用 margin {ebitda_margin*100:.0f}% × FY 當期 Rev",
        })

    # 5. DCF (5y FCF growth → Gordon terminal)
    # 用 forward FCF 估值 (TTM 對 cyclical 股太失真;用 FY 當期 EPS × shares × 80% conversion)
    fcf_ttm = safe_float(info.get("freeCashflow"))
    eps0 = fy0.get("eps_avg")
    fcf_base = None
    if eps0 and shares:
        # cyclical semi forward FCF ≈ FY current NI × 80%
        forward_ni = eps0 * shares
        fcf_base = forward_ni * 0.80
        fcf_source = f"FY 當期 NI (EPS ${eps0} × {shares/1e9:.2f}B 股) × 80% FCF conversion"
    elif fcf_ttm:
        fcf_base = fcf_ttm
        fcf_source = f"TTM FCF ${fcf_ttm/1e9:.1f}B"

    if fcf_base and shares:
        g = params["dcf_fcf_growth_5y"]
        disc = params["dcf_disc_rate"]
        tg = params["dcf_terminal_growth"]
        pv_explicit = 0
        fcf_year = fcf_base
        for y in range(1, 6):
            fcf_year = fcf_year * (1 + g)
            pv_explicit += fcf_year / ((1 + disc) ** y)
        terminal = fcf_year * (1 + tg) / (disc - tg)
        pv_terminal = terminal / ((1 + disc) ** 5)
        ev_target = pv_explicit + pv_terminal
        net_debt = (safe_float(info.get("totalDebt")) or 0) - (safe_float(info.get("totalCash")) or 0)
        mcap_target = ev_target - net_debt
        p = mcap_target / shares
        models.append({
            "model": f"DCF ({int(disc*100)}% disc, 5y FCF {int(g*100)}% → 終值 {int(tg*100)}%)",
            "implied_price": round(p, 2),
            "rationale": f"基準 FCF ${fcf_base/1e9:.1f}B (= {fcf_source}),5 年 {int(g*100)}% CAGR 後降至 {int(tg*100)}% terminal",
        })

    # 6. Analyst Mean Target
    if mean_target:
        models.append({
            "model": "Analyst Mean Target",
            "implied_price": round(mean_target, 2),
            "rationale": f"yfinance 共識:{raw['price_targets'].get('mean')} (n={len(raw['upgrades_downgrades']) or '?'})",
        })

    return models


def build_support_resistance(raw: dict, current_price: float) -> dict:
    """從 1y history + 整數關卡 + DMA 推導 S/R 位

    優先順序 (high → low): DMA / 52w / 整數心理關
    各取近 4 位。"""
    h = raw["history"]
    closes = h["closes"]
    if not closes or len(closes) < 50:
        return {"support_levels": [], "resistance_levels": []}

    ma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else None
    ma200 = sum(closes[-200:]) / 200 if len(closes) >= 200 else None
    w52_high = max(closes)
    w52_low = min(closes)

    def round_levels(p, span=0.20):
        out = []
        for step in [100, 50]:
            base = (p // step) * step
            for k in range(-3, 4):
                lvl = base + k * step
                if abs(lvl - p) / p <= span and lvl > 0:
                    out.append(lvl)
        return sorted(set(out))

    psych = round_levels(current_price)

    # 收集所有 levels 分類 below (支撐) / above (壓力),含優先級
    # priority: 1=高 (DMA/52w強), 2=中, 3=低 (整數關)
    below = []  # list of (price, type, strength, priority)
    above = []

    if ma200:
        if ma200 < current_price:
            dist = abs(ma200 - current_price) / current_price
            below.append((round(ma200, 2), "200 DMA", "強" if dist > 0.15 else "中", 1))
        else:
            above.append((round(ma200, 2), "200 DMA", "中", 1))
    if ma50:
        if ma50 < current_price:
            dist = abs(ma50 - current_price) / current_price
            below.append((round(ma50, 2), "50 DMA", "強" if dist > 0.05 else "中", 1))
        else:
            above.append((round(ma50, 2), "50 DMA", "中", 1))

    if w52_high > current_price * 1.005:
        above.append((round(w52_high, 2), "52 週新高", "強", 1))
    elif w52_high >= current_price * 0.995:
        # 當前正在 52w high 附近 (±0.5%) — 列為當前壓力,別重複放支撐
        above.append((round(w52_high, 2), "正測 52 週新高", "強", 1))
    else:
        # 52w high 已被遠遠突破,變支撐
        below.append((round(w52_high, 2), "前壓變支撐 (52 週前高)", "強", 1))
    if w52_low < current_price:
        below.append((round(w52_low, 2), "52 週低", "強 (深支撐)", 1))

    for lvl in psych:
        if lvl < current_price:
            below.append((round(lvl, 2), f"整數心理關 ${int(lvl)}", "弱", 3))
        elif lvl > current_price:
            above.append((round(lvl, 2), f"整數心理關 ${int(lvl)}", "弱", 3))

    # 排序:先按 priority asc, 再按距離當前價 asc。各取 4
    below_sorted = sorted(below, key=lambda x: (x[3], abs(x[0] - current_price)))[:4]
    above_sorted = sorted(above, key=lambda x: (x[3], abs(x[0] - current_price)))[:4]

    # 各自再按 price 排序 (支撐:由近到遠 desc;壓力:由近到遠 asc)
    below_sorted = sorted(below_sorted, key=lambda x: -x[0])
    above_sorted = sorted(above_sorted, key=lambda x: x[0])

    return {
        "support_levels": [{"price": p, "type": t, "strength": s} for p, t, s, _ in below_sorted],
        "resistance_levels": [{"price": p, "type": t, "strength": s} for p, t, s, _ in above_sorted],
    }


def build_recent_actions(raw: dict, mean_target: float | None = None) -> list[dict]:
    """整理最近 analyst 行動。過濾 yfinance 對 stock split 未調整的 stale PT
    (任何 priorPriceTarget < mean_target × 0.5 視為過期不顯示)"""
    out = []
    threshold = (mean_target * 0.5) if mean_target else 0
    for r in raw["upgrades_downgrades"][:20]:
        gd = r.get("GradeDate") or r.get("index")
        if hasattr(gd, "strftime"):
            ds = gd.strftime("%Y-%m-%d")
        else:
            ds = str(gd)[:10] if gd else "—"
        old_pt = safe_float(r.get("priorPriceTarget"))
        new_pt = safe_float(r.get("priceTarget"))
        # 過濾 split 未調整的 stale PT
        if old_pt and threshold and old_pt < threshold and (not new_pt or new_pt < threshold):
            continue
        out.append({
            "date": ds,
            "firm": str(r.get("Firm", "—")),
            "action": str(r.get("Action", "—")),
            "from_grade": str(r.get("FromGrade", "")),
            "to_grade": str(r.get("ToGrade", "")),
            "old_target": old_pt,
            "new_target": new_pt,
        })
        if len(out) >= 8:
            break
    return out


def build_valuation_entry(symbol: str) -> dict:
    cfg = TICKER_CONFIG.get(symbol)
    if not cfg:
        raise ValueError(f"{symbol} not in TICKER_CONFIG, please add manual params first")

    print(f"📊 fetching yfinance for {symbol}...")
    raw = fetch_yfinance(symbol)

    info = raw["info"]
    current_price = round_price(info.get("currentPrice") or info.get("regularMarketPrice"))

    consensus = build_analyst_consensus(raw)
    forecasts = build_forecasts(raw)
    mean_target = consensus["price_target"]["mean"]
    models = build_valuation_models(raw, forecasts, cfg["valuation_params"], mean_target)
    sr = build_support_resistance(raw, current_price)
    actions = build_recent_actions(raw, mean_target)

    # Fair value 三段:bear = min(P/S, lowest), base = analyst median, bull = max bullish model
    implied_prices = [m["implied_price"] for m in models if m.get("implied_price")]
    if implied_prices:
        bear = round(min(implied_prices), 0)
        bull = round(max(implied_prices), 0)
        base = round(consensus["price_target"]["median"] or consensus["price_target"]["mean"] or current_price, 0)
    else:
        bear = base = bull = current_price

    return {
        "ticker": symbol,
        "name": cfg["name"],
        "category_label": cfg["category_label"],
        "updated_at": date.today().isoformat(),
        "current_price": current_price,
        "key_stats": {
            "trailing_pe": safe_float(info.get("trailingPE")),
            "forward_pe": safe_float(info.get("forwardPE")),
            "ps_ttm": safe_float(info.get("priceToSalesTrailing12Months")),
            "pb": safe_float(info.get("priceToBook")),
            "ev_ebitda": safe_float(info.get("enterpriseToEbitda")),
            "peg": safe_float(info.get("pegRatio")),
            "mcap_b": round(safe_float(info.get("marketCap")) / 1e9, 1) if info.get("marketCap") else None,
            "fcf_ttm_b": round(safe_float(info.get("freeCashflow")) / 1e9, 2) if info.get("freeCashflow") else None,
            "gross_margin": round(safe_float(info.get("grossMargins")) * 100, 1) if info.get("grossMargins") else None,
            "profit_margin": round(safe_float(info.get("profitMargins")) * 100, 1) if info.get("profitMargins") else None,
            "beta": safe_float(info.get("beta")),
            "w52_high": safe_float(info.get("fiftyTwoWeekHigh")),
            "w52_low": safe_float(info.get("fiftyTwoWeekLow")),
        },
        "analyst_consensus": consensus,
        "forecasts": forecasts,
        "valuation_models": models,
        "fair_value_summary": {
            "bear": bear,
            "base": base,
            "bull": bull,
            "comment": f"區間反映 cyclical 風險:空頭以保守模型算 (${bear:.0f}),多頭給 AI 全週期溢價 (${bull:.0f})。",
        },
        "support_resistance": sr,
        "recent_actions": actions,
        "bull_thesis": cfg["bull_thesis"],
        "bear_thesis": cfg["bear_thesis"],
        "briefing_mentions": cfg["briefing_mentions"],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ticker", help="只跑指定 ticker (預設跑 TICKER_CONFIG 全部)")
    ap.add_argument("--dry-run", action="store_true", help="只印不寫")
    args = ap.parse_args()

    tickers = [args.ticker] if args.ticker else list(TICKER_CONFIG.keys())

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    if "valuations" not in data:
        data["valuations"] = []

    new_entries = []
    for sym in tickers:
        try:
            entry = build_valuation_entry(sym)
            new_entries.append(entry)
            print(f"  ✓ {sym} 完成 — current=${entry['current_price']}, "
                  f"fair value bear=${entry['fair_value_summary']['bear']:.0f} / "
                  f"base=${entry['fair_value_summary']['base']:.0f} / "
                  f"bull=${entry['fair_value_summary']['bull']:.0f}")
        except Exception as e:
            print(f"  ✗ {sym} 失敗: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()

    if args.dry_run:
        print("\n--- dry-run ---")
        print(json.dumps(new_entries[0] if new_entries else {}, ensure_ascii=False, indent=2))
        return

    # merge: 用 ticker 當 key 替換
    existing = {v["ticker"]: v for v in data["valuations"]}
    for e in new_entries:
        existing[e["ticker"]] = e
    data["valuations"] = list(existing.values())

    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n💾 寫入 {DATA_FILE.name},valuations 共 {len(data['valuations'])} 檔")
    print("👉 記得跑 python run.py --no-update --update-only 重新嵌入 index.html")


if __name__ == "__main__":
    main()
