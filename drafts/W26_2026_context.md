# Weekly Briefing Draft Context — 2026-W26

**範圍**: 2026-06-22 ~ 2026-06-28 (週一至週日)

## 任務

請為 `data.json` 的 `weekly_briefing` 區段產生本週 entry。輸出 JSON,
格式參照既有的條目 (week / date_range / sources / headlines)。

**目標**: 4-8 條 headlines,涵蓋:
- 1 macro / Fed (category: 宏觀資金 / 市場修正)
- 1-2 AI 模型 / 雲端 (category: AI 模型 / AI 軟體)
- 1 Tesla / SpaceX / 馬斯克 (category: Tesla / Tesla / FSD / 馬斯克)
- 1 IPO / M&A (若有,category: IPO + 估值 / 併購)
- 1 台股 (category: 股癌觀點 / 台股個股)

**重要**: 在 `implication` 欄位提及『後續可能影響 X』或『印證 W25 的 Y』
以建立週次間的因果鏈。讀者(博的)很重視這條 narrative thread。

## 來源

### Gmail 訂閱 (需 Claude 用 Gmail MCP 抓)

Claude 請執行以下 search:

```
# M報
mcp__gmail__search_emails(
  query='from:mviewpoint@substack.com after:2026-06-22 before:2026-06-29',
  maxResults=5)

# 馬斯克帝國觀察
mcp__gmail__search_emails(
  query='from:muskempire0628@substack.com after:2026-06-22 before:2026-06-29',
  maxResults=5)

# 富果直送
mcp__gmail__search_emails(
  query='from:service@fugle.tw after:2026-06-22 before:2026-06-29',
  maxResults=10)
```

找到的每封信都用 `mcp__gmail__read_email` 看內文。

## 輸出格式

```json
{
  "week": "2026-W26",
  "date_range": "2026-06-22 ~ 2026-06-28",
  "sources": ["M報 #X", "馬斯克帝國觀察 #Y", "富果直送 (個股名)", "股癌 EP?-#?", "All-In 6/13"],
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
git commit -m 'feat: weekly_briefing 2026-W26'
git push
python send_briefing.py --week 2026-W26 --json  # 寄信
```
## 增量 2026-06-24 (cron 22:33)

**本地素材**: 今日無新股癌 / All-In 集數

**Gmail 增量**: Claude 用 MCP 抓本週至今所有信,並比對既有 drafts 是否已收錄

```
mcp__gmail__search_emails(query='from:mviewpoint@substack.com after:2026-06-22 before:2026-06-25', maxResults=5)
mcp__gmail__search_emails(query='from:muskempire0628@substack.com after:2026-06-22 before:2026-06-25', maxResults=5)
mcp__gmail__search_emails(query='from:service@fugle.tw after:2026-06-22 before:2026-06-25', maxResults=10)
```

若 Gmail 抓到的 subject 已存在於上方 drafts,跳過;否則 mcp__gmail__read_email 抓正文後在此 append 摘要 (2-4 行/封)。
