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


## 增量 2026-06-25 (cron 22:33)

**本地素材**: 今日無新股癌 / All-In 集數

**Gmail 增量**: 已 cross-check 本週至今 6 封信 (M報 #532 / 馬斯克 #76 / 富果 4 篇),全部在 2026-06-24 段已收錄完畢 → 今日無增量素材。下次 EP672 / All-In 新片或週四 (6/26+) 新信再追加。

```
mcp__gmail__search_emails(query='from:mviewpoint@substack.com after:2026-06-22 before:2026-06-26', maxResults=5)
mcp__gmail__search_emails(query='from:muskempire0628@substack.com after:2026-06-22 before:2026-06-26', maxResults=5)
mcp__gmail__search_emails(query='from:service@fugle.tw after:2026-06-22 before:2026-06-26', maxResults=10)
```

若 Gmail 抓到的 subject 已存在於上方 drafts,跳過;否則 mcp__gmail__read_email 抓正文後在此 append 摘要 (2-4 行/封)。

## 增量 2026-06-26 (cron 22:33)

**本地素材**: 今日無新股癌 / All-In 集數

**Gmail 增量**: 抓到 2 封新信 (M報 #533 + 馬斯克 #77) — 富果今日無新信。

### M報 #533 (2026-06-26) — Google 痛失 AI 大將 / Fable 5 配方解密 / Meta 士氣低落 / FSD 入台

**Google 痛失兩名 AI 大將**
- Noam Shazeer (Transformer 共同作者、Gemini 共同負責人) 2024 年 Google 花 $27B 找回,2 年後再離開 → **加入 OpenAI** 任 AI Architecture Research Lead
- John Jumper (AlphaFold 核心、2024 諾貝爾化學獎得主) **加入 Anthropic**,可能負責 AI 科學/生物化學
- 一天內兩人離開 → 對 Google 心理層面與組織士氣形成明顯打擊
- 同時市場流傳 Gemini 3.5 Pro 可能不如預期 (預定 6 月底登場)
- Sensor Tower:ChatGPT 市占率首次跌破 50%,但 Gemini 從 22% → 27.7% 持續成長
- M觀點:Google 不至於被打趴 (TPU/算力/資料/人才庫仍強),但 Agentic Workflow / 企業 API 是真正落後 OpenAI/Anthropic 的戰場

**Fable 5 配方解密 + 解禁可能性升高**
- G7 川普與 Dario 談得好,「上週可能還這麼認為,但現在已不再把 Anthropic 視為國家安全威脅」
- 但 NSA 議員 Mark Warner 引述:Mythos 能在數小時內找出 NSA 高度機密系統弱點
- Pliny the Liberator 在 X 公開 ~12 萬字元的 Fable 5 系統提示詞 — 證明 Anthropic 把 Claude Code 級的 Agent Harness 大量搬進 Claude.ai
- Fable 5 在背後可能啟動 sub-agent 沙盒,搜尋/寫程式/分析/檢查多步驟流程
- 2026 AI 顯學:**Agent Harness** — 評估模型已不能只比底層,要看 model + harness 整合
- M觀點預估 Fable 5 可能在 2-4 週內重新上線 (取決於 Anthropic 願不願意修 jailbreak)

**Meta 士氣低落 (預演 AI 時代 Data Creation Job)**
- 技術長 Bosworth 親口承認「20 年來最差的幾次之一」
- 裁員 8,000 → 7,000 人調入 Applied AI 部門 (替模型出題/評分/改答案)
- 預演「高熵值資料創作」工作 — AI 時代可能大量出現,但成就感是大問號
- M觀點推測 Applied AI 是 placeholder,暫時安置人力,半年後人才會自然汰換

**FSD 入台 (Q3 可能通過)**
- Tesla 台灣已正式向車輛安全審驗中心送件,**Q3 可能通過**
- 一次性買斷 NT$22.2 萬期限 6/30,期限後改月費
- 荷蘭 4 月先核准,愛沙尼亞/比利時跟進;歐盟統一表決 2026-10
- 影響:**TSLA 全球銷量今年有機會重新成長** (FSD 對購車意願影響去年底才開始明顯)

### 馬斯克帝國觀察 #77 (2026-06-26) — 特斯拉能源歐洲爆發 / 自駕車法規鬆綁 / SpaceX Starmind

**Tesla 能源業務歐洲大爆發 (數十億美元級訂單)**
- **NatPower 義英 $5B 合約**:25+ GWh 儲能 (第一階段,總目標 100+ GWh),已超過加州 Megapack 工廠年產能一半
- **GIGA Storage 比利時 $700M 合約**:2.8 GWh「Green Turtle」儲能設施,2027 投產,歐洲規模最大之一
- **柏林工廠 10 月起每週 6,250 → 7,500 輛 (+20%)**,新增 3,500 個職位
- TSLA 能源業務本季營收結構性放大 (能源 + 汽車雙引擎更明確)

**美自駕車法規大鬆綁**
- NHTSA 啟動 FMVSS 修訂:全自駕車**可取消手動煞車踏板**強制規定
- 川普政府 5 項 AV 法規更新之一,目的:移除「以人類駕駛為基礎」的過時規範
- **直接利多 Tesla Cybercab** (無方向盤/踏板設計) — 認證障礙降低
- Lemonade 推 FSD 里程 50% 折扣保險 (第 4 州科羅拉多;Tesla 數據:FSD 安全是人駕 2x)
- 芬蘭可能在歐盟 10 月統一表決前提前核准 FSD
- Cybertruck 獲 IIHS Top Safety Pick+ (皮卡車唯一)

**SpaceX 重大進展**
- **Starmind**:Elon 確認下代 AI 衛星星座定名,計畫 100 萬顆 (軌道資料中心,AI1 衛星 120kW + 150kW 太陽能)
- **Starfall** 首飛成功:小型無人貨運返回艙 (2,100 kg, 1,000 kg payload),Falcon 9 發射 + 太平洋濺落,鎖定太空製造市場 (特殊藥物/單晶光纖/生物列印)
- **$25B 債券發行完成**:5 期 (2031-2056 到期, 5.35%~6.65%),總認購超 $89B (3.5x 超額),IPO 後資本結構 ✓

**xAI / Neuralink / 其他**
- **記憶體短缺警告 (Elon + Tim Cook 同調)**:Tim Cook 稱「40 年職涯前所未見」,AI HBM 排擠消費電子 DRAM 供應 → **直接利多 MU / 海力士 / 三星 + 國巨/華新科 MLCC**
- Elon「Deflation is inevitable」回應 Cathie Wood — AI/機器人/自動化 → 豐裕型通縮
- Neuralink 計劃年底首次嘗試**腦對腦直接通訊** (跳過語言中介,latent space 直傳)
- Dell 股東 97% 通過遷總部到德州 (DExit 趨勢)

## 增量 2026-06-26 (cron 22:33) — 後補:股癌 EP672 + EP673

抓 fetch_gooaye.py --refresh 才發現本地 cache 沒更新,實際 EP672 (6/20) 與 EP673 (6/24) 已釋出。EP672 屬 W25 末端,EP673 屬 W26 — 都跟本週 narrative 高度相關。

### 股癌 EP672 (2026-06-20) — 功率元件缺貨論與軟體職涯重整
- 台股創新高 + **功率半導體 IDM 缺貨** — 歐美廠商 lead time 拉超長
- 台灣**二線廠受惠** (需注意產能能否真的開出來)
- 後半:軟體工程師面對 AI 衝擊 → 認為是過去科技大廠 over hiring 的修正,要思考用 AI 工具產生更大價值
- 印證 W25 EP671 + W26 富果 6/22 + 我們已加的 ON/IFNNY/TXN — narrative 三方共振

### 股癌 EP673 (2026-06-24) — 全聯淘酒記與電阻漲浪論
- 盤面:最近回檔只是創新高後正常休息,**被動元件持續看好,尤其是電阻即將漲價**
- **聯發科 (2454.TW) 拿到 Google TriggerFish 晶片案** → 競爭力提升
- 短期市場沒特別變化,**持續做多為主**
- 印證 W26 富果 CCL/被動元件 + Tim Cook/Elon 記憶體短缺 → **MLCC + 電阻雙線** narrative

## 走勢預測 — W26 末段補充 (含 EP672/673)

- **Google 雙人才離職** → 印證 W25 「AI 三巨頭差距」narrative,但 M觀點認為 Google 仍是第一線玩家,別輕信「Google 完蛋」論
- **Fable 5 12 萬字系統提示詞**(Agent Harness 顯學) → 強化 NVDA / hyperscaler 算力需求 (Sub-agent 多步驟 = token 消耗倍增,**反 Token Maxxing 退燒**論)
- **記憶體短缺 (Tim Cook + Elon 同調) + 股癌 EP673 電阻漲價** → 印證 W25 ON/IFNNY/TXN + 國巨/華新科 narrative,**MU + MLCC + 電阻三線估值上修 catalyst**
- **FSD 入台 Q3** → 2026 H2 TSLA 銷量數據可期,搭配 NHTSA 法規鬆綁 → Robotaxi/Cybercab 雙催化
- **Starmind 100 萬顆 AI 衛星**:SpaceX 從 Colossus → 軌道資料中心,長線重估邏輯延伸


## 增量 2026-06-27 (cron 22:33)

**本地素材**: 今日無新股癌 (EP673 仍最新, EP674 預計週日/週一發) / All-In 無新片

**Gmail 增量**: 已 cross-check 三家本週至今 — M報 / 馬斯克 / 富果 6/27 均 0 新信。本週已抓的 8 封 (M報 #532 + #533 / 馬斯克 #76 + #77 / 富果 4 篇) 全部在 6/24 + 6/26 段已收錄。**今日真實無增量,週日 cron 將以整週素材生成 final entry**。


## 增量 2026-06-28 (cron 22:33)

**本地素材**: 今日無新股癌 / All-In 集數

**Gmail 增量**: Claude 用 MCP 抓本週至今所有信,並比對既有 drafts 是否已收錄

```
mcp__gmail__search_emails(query='from:mviewpoint@substack.com after:2026-06-22 before:2026-06-29', maxResults=5)
mcp__gmail__search_emails(query='from:muskempire0628@substack.com after:2026-06-22 before:2026-06-29', maxResults=5)
mcp__gmail__search_emails(query='from:service@fugle.tw after:2026-06-22 before:2026-06-29', maxResults=10)
```

若 Gmail 抓到的 subject 已存在於上方 drafts,跳過;否則 mcp__gmail__read_email 抓正文後在此 append 摘要 (2-4 行/封)。
