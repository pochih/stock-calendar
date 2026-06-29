# Weekly Briefing Draft Context — 2026-W27

**範圍**: 2026-06-29 ~ 2026-07-05 (週一至週日)

## 任務

請為 `data.json` 的 `weekly_briefing` 區段產生本週 entry。輸出 JSON,
格式參照既有的條目 (week / date_range / sources / headlines)。

**目標**: 4-8 條 headlines,涵蓋:
- 1 macro / Fed (category: 宏觀資金 / 市場修正)
- 1-2 AI 模型 / 雲端 (category: AI 模型 / AI 軟體)
- 1 Tesla / SpaceX / 馬斯克 (category: Tesla / Tesla / FSD / 馬斯克)
- 1 IPO / M&A (若有,category: IPO + 估值 / 併購)
- 1 台股 (category: 股癌觀點 / 台股個股)

**重要**: 在 `implication` 欄位提及『後續可能影響 X』或『印證 W26 的 Y』
以建立週次間的因果鏈。讀者(博的)很重視這條 narrative thread。

## 來源

### Gmail 訂閱 (需 Claude 用 Gmail MCP 抓)

Claude 請執行以下 search:

```
# M報
mcp__gmail__search_emails(
  query='from:mviewpoint@substack.com after:2026-06-29 before:2026-07-06',
  maxResults=5)

# 馬斯克帝國觀察
mcp__gmail__search_emails(
  query='from:muskempire0628@substack.com after:2026-06-29 before:2026-07-06',
  maxResults=5)

# 富果直送
mcp__gmail__search_emails(
  query='from:service@fugle.tw after:2026-06-29 before:2026-07-06',
  maxResults=10)
```

找到的每封信都用 `mcp__gmail__read_email` 看內文。

## 輸出格式

```json
{
  "week": "2026-W27",
  "date_range": "2026-06-29 ~ 2026-07-05",
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
git commit -m 'feat: weekly_briefing 2026-W27'
git push
python send_briefing.py --week 2026-W27 --json  # 寄信
```

## 增量 2026-06-29 (cron 22:33,W27 首日)

**本地素材**: 今日無新股癌 (EP673 仍最新, EP674 預計本週中發) / All-In (最新 2026-06-19) 無新片

**Gmail 增量**: 抓到 1 封新信 — 富果 FPC 軟板缺貨潮深度報告 (M報 / 馬斯克本週尚未發信)

### 富果直送 (2026-06-29) — 全球 FPC 驚傳狂漲 38%,缺貨潮燒到 2027

**核心數據**
- FPC (軟板) 最新合約價 **逆勢暴漲 38%** — 違背市場對「軟板=低毛利消費電子耗材」的舊認知
- 上游高階材料 (PI 膜 / 銅箔基板 / 高階基材) 近年**零擴產**,缺貨潮**延續至 2027**
- 三大需求引擎:**高階 AI 伺服器 + 摺疊機 + 系統功能件**強烈虹吸高階產能
- 軟板從「傳統連接線路」拉升為「關鍵系統功能件」,技術壁壘 + 材料通膨**汰換低端標準品**

**受惠標的**
- **臻鼎 (4958.TW)**:砸百億升級技術壁壘,卡位高階 AI 伺服器軟板
- **台郡 (6269.TW)**:急轉**穿戴 + AI 應用**,布局摺疊機
- 整體:中下游大廠**獲利天花板重構**

**Narrative 連結 W26**
- 印證 W26『記憶體 (Tim Cook + Elon 同調) + 電阻漲價 + 功率半導體缺貨』供需主題鏈
- 加入第四線:**FPC 軟板缺貨**,缺貨主題從「半導體 → 被動元件 → 軟板」全面擴散
- 印證『AI 伺服器破千瓦帶動材料規格升級』邏輯 — CCL (W26) + FPC (W27) 同源 PCB 產業鏈

**走勢預測 — W27 早期觀察點**
- 臻鼎 (4958.TW) / 台郡 (6269.TW) 短線可能跟著富果報告反應
- 摺疊機需求 (蘋果摺疊機傳聞 2027 / Samsung Galaxy Z Fold) 是另一條 narrative
- 軟板漲價是否帶動中游 PCB ABF / CCL 漲價的後續訊號 (W27-W28 觀察)
- 後續 W27 中段觀察:M報 / 馬斯克 7 月新發信,主題可能聚焦『AI capex Q2 財報季前瞻』『Cybercab 量產時程』『Fable 5 解禁進度』

```
mcp__gmail__search_emails(query='from:mviewpoint@substack.com after:2026-06-29 before:2026-07-06', maxResults=5)
mcp__gmail__search_emails(query='from:muskempire0628@substack.com after:2026-06-29 before:2026-07-06', maxResults=5)
mcp__gmail__search_emails(query='from:service@fugle.tw after:2026-06-29 before:2026-07-06', maxResults=10)
```
