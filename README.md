# stock-calendar

A lightweight, self-hosted market dashboard inspired by Google Finance. It tracks earnings dates, IPO calendars, FOMC meetings, macro releases, Polymarket prediction markets, and a customizable watchlist — all rendered as a single static `index.html` page backed by `data.json`.

一個輕量、可自架的市場儀表板 (靈感來自 Google Finance)。整合財報日、IPO、FOMC、總經數據、Polymarket 預測市場、以及自訂 watchlist —— 全部在單一靜態 `index.html` 頁面呈現,資料由 `data.json` 驅動。

> **Live demo:** https://pochih.github.io/stock-calendar/

---

## Features / 功能

- **Real-time prices** — yfinance-powered tickers with PE, Forward PE, gross margin, FCF, dividend yield
- **Sparkline + watchlist + leaderboard** — at-a-glance view of your tracked symbols
- **ETF chart prefix table** — covers 20 major ETFs
- **Earnings & IPO calendar** — upcoming reports and listings
- **Macro events** — FOMC meetings, CPI/NFP/GDP releases
- **Polymarket integration** — top trending prediction markets
- **Auto-update via GitHub Actions** — twice-daily refresh (pre-market + post-close ET)
- **Auto-deploy via GitHub Pages** — push to `main`, your dashboard goes live

---

## Quick start / 快速開始

```bash
git clone https://github.com/pochih/stock-calendar.git
cd stock-calendar
pip install -r requirements.txt
python run.py
```

`run.py` will:
1. Pull fresh data from yfinance + Polymarket
2. Stamp `data.json` with timestamp + auto-bumped semver
3. Start a local HTTP server on port `8080`
4. Open your browser to `index.html`

### Useful flags / 常用旗標

```bash
python run.py --no-update     # 只啟動 server,不抓新資料
python run.py --no-open       # 更新 + server,不自動開瀏覽器
python run.py --update-only   # 只更新 data.json,不啟動 server
python run.py --port 9000     # 指定 port

python update_data.py                  # 只更新 tickers 區段
python update_data.py --polymarket     # 加上 Polymarket 更新
python update_data.py --earnings       # 用 yfinance 重抓財報日
python update_data.py --all            # 全部更新
```

---

## Project structure / 專案結構

```
stock-calendar/
├── index.html         # Single-page dashboard (vanilla JS, no build step)
├── data.json          # All market data — read by index.html at runtime
├── run.py             # One-shot: update data + serve + open browser
├── update_data.py     # Refresh data.json (tickers / earnings / Polymarket)
├── requirements.txt   # yfinance, requests
└── .github/workflows/ # Auto-update + GitHub Pages deploy
```

---

## Contributing / 貢獻指南

Contributions are welcome — bug fixes, new tickers, better data sources, or UI tweaks.
歡迎貢獻 —— bug 修復、新增 ticker、更好的資料來源、或 UI 改進都歡迎。

### How to contribute / 如何貢獻

1. **Fork** this repository
2. **Create a branch** from `main`:
   ```bash
   git checkout -b feat/your-feature   # 新功能
   git checkout -b fix/the-bug         # 修 bug
   ```
3. **Make your changes** and test locally with `python run.py`
4. **Commit** following the existing style (see commit history):
   - `feat: ...` — new feature
   - `fix: ...` — bug fix
   - `chore: ...` — tooling / data updates
   - `ci: ...` — workflow changes
5. **Push** and open a **Pull Request** against `main`

### Guidelines / 規範

- **Test before pushing** — run `python run.py` and verify the dashboard renders correctly
- **Don't commit `data.json` updates manually** — the GitHub Action handles auto-refresh; manual data commits create merge conflicts
- **Keep `index.html` self-contained** — no build step, no bundlers; vanilla JS / CSS only
- **One concern per PR** — easier to review, easier to revert

### Reporting issues / 回報問題

Found a wrong price, a missing ticker, or a broken UI element? Open an issue with:
發現價格錯誤、ticker 缺漏、或 UI 異常?請開 issue 並附上:

- What you saw vs. what you expected / 看到什麼 vs. 預期什麼
- Browser + OS / 瀏覽器與作業系統
- Screenshot if applicable / 如果可以,附上截圖

---

## License / 授權

See repository for license details. / 授權資訊請見 repository。
