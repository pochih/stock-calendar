# Weekly Briefing Draft Context — 2026-W25

**範圍**: 2026-06-15 ~ 2026-06-21 (週一至週日)

## 任務

請為 `data.json` 的 `weekly_briefing` 區段產生本週 entry。輸出 JSON,
格式參照既有的條目 (week / date_range / sources / headlines)。

**目標**: 4-8 條 headlines,涵蓋:
- 1 macro / Fed (category: 宏觀資金 / 市場修正)
- 1-2 AI 模型 / 雲端 (category: AI 模型 / AI 軟體)
- 1 Tesla / SpaceX / 馬斯克 (category: Tesla / Tesla / FSD / 馬斯克)
- 1 IPO / M&A (若有,category: IPO + 估值 / 併購)
- 1 台股 (category: 股癌觀點 / 台股個股)

**重要**: 在 `implication` 欄位提及『後續可能影響 X』或『印證 W24 的 Y』
以建立週次間的因果鏈。讀者(博的)很重視這條 narrative thread。

## 來源

### 股癌 (1 集)

**EP671 (2026-06-17) — 離散元件覓蹤與隨機人生論**

> 聊被動元件炒作風向漸轉、為何要警惕市場上假借孟恭名義推薦個股的詐騙；談林口餐飲投資計畫和房地產觀察；觀察市場百花齊放現象，認為資金可能會從主流族群輪轉到離散元件、功率半導體等題材；分析 Nexperia 制裁事件如何推動廠商做非中國佈局，以及 DrMOS、800V DC 等高階功率元件的商機；最後反思人生充滿隨機性，成功同樣仰賴環境與運氣。

### All-In Podcast (1 集)

**2026-06-19 — World's First Trillionaire, Anthropic Fable Banned, The New Oligarchs, Iran Peace Deal**

全文位於: `transcripts/allin/EP3Amlu4y94Ho_World-s-First-Trillionaire-Anthropic-Fable-Banned-The-New-Ol.txt`

用 Read tool 載入,然後萃取 1-3 個對應到本週事件的觀點。

### Gmail 訂閱 (需 Claude 用 Gmail MCP 抓)

Claude 請執行以下 search:

```
# M報
mcp__gmail__search_emails(
  query='from:mviewpoint@substack.com after:2026-06-15 before:2026-06-22',
  maxResults=5)

# 馬斯克帝國觀察
mcp__gmail__search_emails(
  query='from:muskempire0628@substack.com after:2026-06-15 before:2026-06-22',
  maxResults=5)

# 富果直送
mcp__gmail__search_emails(
  query='from:service@fugle.tw after:2026-06-15 before:2026-06-22',
  maxResults=10)
```

找到的每封信都用 `mcp__gmail__read_email` 看內文。

## 輸出格式

```json
{
  "week": "2026-W25",
  "date_range": "2026-06-15 ~ 2026-06-21",
  "sources": ["M報 #X", "馬斯克帝國觀察 #Y", "富果直送 (個股名)", "股癌 EP671-#671", "All-In 6/13"],
  "headlines": [
    {
      "category": "宏觀資金",
      "title": "...",
      "tickers": ["NVDA", "..."],
      "summary": "事實 / 數據點",
      "stance": "M觀點:... / 股癌:... / All-In:...",
      "implication": "後續...",
      "themes_touched": ["..."]
    }
  ]
}
```

產出後請插入 `data.json` 的 `weekly_briefing` 陣列開頭,然後跑:

```bash
python run.py --no-update --update-only  # 重新嵌入 index.html
git add data.json index.html
git commit -m 'feat: weekly_briefing 2026-W25'
git push
python send_briefing.py --week 2026-W25 --json  # 寄信
```