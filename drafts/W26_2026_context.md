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
## 增量 2026-06-24 (cron 22:33,週三 daily + Wed cron 合併)

**本地素材**: 今日無新股癌 / All-In 集數 (EP671 在 W25 已用,EP672 應週末發)

**Gmail 摘要** (本週至今 6 封信):

### M報 #532 (2026-06-23) — SPCX 併購 Cursor / Fable 5 仍禁 / AI 產業新利空

**SPCX 600 億美元收購 Cursor (全換股)**
- Cursor 2025 年 ARR 從 $1B → $10B (10x),2026 年中接近 $40B,年底估 $80B
- 從 Anthropic 最佳夥伴變成 Claude Code 直接受害者 — Anthropic 高層曾承諾 Claude Code 只是 research project 卻變商業產品
- SPCX 需要 Cursor 補上原 xAI 創始團隊離職空缺 (2-3 月幾乎全部離職)
- Cursor Composer 2.5 證明調教能力:基於 Kimi K2.5 重訓 85%,效果達 Claude Opus 4.8 / GPT-5.5 的 98-99% 成本只 1/10
- xAI 手中模型:兩個 1T、兩個 1.5T、6T、10T 訓練中;1.5T 已完成 pretrain → 給 Cursor 調教,有機會追上 GPT-5.5 / Claude Opus 4.8
- M觀點:SPCX 600 億是合理價,讓 SPCX AI 估值有具體支撐
- 受影響 ticker:**xAI / SPCX 估值結構性受惠**;Anthropic / OpenAI 競爭壓力增大

**Fable 5 仍禁,華盛頓信任崩壞**
- Anthropic 派高層赴華盛頓但仍未解禁
- Mythos 白名單放韓國電信 (疑與中國有關),動搖政府信任
- jailbreak 案例:guardrails 可被「改善安全性」問法繞過,等於提供漏洞清單
- Ben Thompson:Anthropic 禁止蒸餾時會偷改 prompt 降低品質 → 證明它是國防供應鏈風險
- Cloudflare CEO 拒絕加入 Anthropic 董事會、送政治學書給 Dario
- M觀點建議:Dario 該轉任 Chief Scientist,找懂政府的人當 CEO

**AI Token Maxxing 退燒 → 新利空**
- Uber 4 月就花完全年 AI 預算,但 6 月仍無明確營收效果
- Citadel「Token 經濟學」報告:AI 走向兩極化,大部分日常工作用便宜模型
- 微軟 Copilot Cowork 走 usage-based + Model Router,自動把簡單請求導向便宜模型
- OpenRouter Fusion:Gemini 3 Flash + Kimi K2.6 + DeepSeek V4 Pro 組隊擊敗 GPT-5.5 / Claude Opus,甚至小贏 Fable 5
- Frontier Model (OpenAI/Anthropic) 壓力較大,中階模型受惠
- 短期 AI 類股逆風 narrative,長期需求仍上升

### 馬斯克帝國觀察 #76 (2026-06-23) — SPCX 算力商業化加速 + 千億現金發債

**SpaceX 算力大單繼續累積**
- Reflection AI 簽 63 億美元算力合約 (2026-07-01 起每月 $150M、3 年期)
- Reflection 估值 $25B,目標美國開源 AI 對抗 OpenAI/Anthropic
- 加上 Google ($920M/月) + Anthropic ($1.25B/月) + Reflection ($150M/月) = 月收 $2.32B = 年化 ~$278 億
- Colossus 已從 Grok 內部設施 → 商業算力平台

**SpaceX 首發 200 億美元優先無擔保債券**
- 截至 6/19 手中現金 + 約當現金 $1,008 億
- 用途:償還 bridge loan、AI 基礎設施、Starship 等
- 顯示 IPO 後資本結構持續優化

**Tesla 動態**
- Semi 配備 FSD 驗證設備被目擊,可能為商用卡車自駕鋪路
- 物理學家克勞斯 (Lawrence Krauss) 用 FSD 一路開到奧勒岡州,公開稱讚
- Robotaxi 服務 1 週年 (Austin 啟動於 2025-06-22),已擴至 Dallas/Houston

**xAI / Neuralink / 政治**
- Grok 整合 Interactive Brokers (170+ 市場投資分析)
- Neuralink 第 26 位植入者:加拿大 ALS 警官 Lee Marten
- 民主黨眾議員 Ro Khanna 提議對馬斯克課 5% 一次性財富稅 — 馬斯克回擊「邪惡騙子」、「該被關的是你」
- JD Vance 透露 Trump 支持「主權財富基金」持有 OpenAI/Anthropic 部分股權;馬斯克反提「直接發錢給人民」更好

### 富果直送 (2026-06-22, 06-23, 06-24, 2 篇 6-24) — 被動 + 功率元件 + CCL + 先進封裝 + 大甲

- **6/22 被動 + 功率元件升級紅利**:AI 伺服器功耗破千瓦,村田/TDK 加速轉高階車用,標準品 + 商用高階市場板塊挪移。**呼應股癌 EP671 + 我們已加的 ON/TXN/IFNNY 三檔** + 國巨 (2327)/華新科 (2492) 受惠
- **6/24 CCL 銅箔基板**:AI 伺服器跨千瓦,訊號損耗 + 散熱問題的底層 CCL 規格升級。**雙鍵 (4764)** 樹脂材料卡位 AI 高毛利、**台燿 (6274)** 高頻高速 CCL 龍頭、**亞泰金屬 (6179)** 含浸設備 70%+ 市佔在手訂單到 2028
- **6/24 先進封裝**:台積電 SoIC 引領 3D 先進封裝、開啟新一波算力革命 (深度報告)
- **6/23 大甲**:台灣半導體潔淨管領導者,晶圓擴廠潮隱形冠軍

## 走勢預測 — W26 連結到 W27+ 伏筆

- **SPCX 600 億收 Cursor** 短期是 NVDA / OpenAI / Anthropic 利空 (xAI 重返競賽),長期算力需求仍升
- **Token Maxxing 退燒**(M觀點) — 投資人需重新檢視 NVDA / hyperscaler capex 增速;但 Burry W47 2025 放空陣營邏輯被印證
- **CCL + 被動 + 功率元件** 主題形成完整鏈條:股癌 EP671 (W25) → 富果 6/22 + 6/24 (W26) → 後續週可能看到台積電 SoIC 帶動 ABF / CCL / 銅箔大漲
- **SpaceX 千億現金 + 算力月收 $2.3B**:估值結構性上修,可能催化 IPO 重估

