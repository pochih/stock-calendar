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

## 增量 2026-06-30 (cron 22:33)

**本地素材**: 今日無新股癌 (EP673 仍最新) / All-In (最新 2026-06-19) 無新片

**Gmail 增量**: 抓到 3 封新信 — M報 #534 + 馬斯克 #75 (新編號改名為 #78?) + 富果 6/30 長榮航太

### M報 #534 (2026-06-30) — iPhone 18 漲價 + SPCX 估值 1.05 兆 + 瓦基談 AI

**iPhone 18 漲價已成定局**
- Tim Cook 親口告訴 WSJ「漲價不可避免」,9 月卸任前先承擔輿論壓力分散給繼任 John Ternus
- 漲價三主因:DRAM 從 2025 初 → 2026 中**現貨價漲 300%**,蘋果採購成本約 +100~200%;NAND Flash 至少 +50%、多數已翻倍;**A20 升 2nm 製程成本 +80%**
- M觀點預估:**iPhone 18 Pro 從 $1,099 → $1,399 (漲 $300)**;入門款 $799 → $999 (漲 $200)
- 受惠/受傷邏輯:**高階手機更能吸收漲價**,中低階手機 (5K~10K 區間) 受傷最重 — 蘋果反而**市占率上升**(從中低階品牌搶份額)
- 但**單機銷量未必增加**:消費者可能延後換機,iPhone 18 銷量略低於 17;New Siri 是潛在催化但需驗證
- **受惠**:AAPL (估值結構性上修) / MU/海力士/三星 (DRAM 短缺紅利) / TSM (2nm 訂單)

**SPCX 估值方法論 — 1.05 兆美元合理價,84 美元/股**
- M觀點分部估值法 (DCF 不適用):
  - 火箭發射 (含 Starship): **$2,000 億** (Rocket Lab 折價 25% 後 x 5 倍)
  - Starlink: **$2,000 億** (10 年後全球電信市場 10% 約 $6,000 億,11% 折現)
  - xAI 模型 + X 資料 + Cursor: **$2,000 億** (OpenAI/Anthropic 接近 $1 兆,Cursor 自身 $500-600 億)
  - xAI 地面算力 (NeoCloud): **$1,500 億** (CoreWeave x 3 倍)
  - 太空 AI 資料中心: **$2,000 億** (10 年後相當於 AWS 一半 = $1 兆,17.5% 高折現率)
  - 太空商機選擇權 + 馬斯克溢價: **$1,000 億**
- 總計 **$1.05 兆**,合理股價約 $83-84 美元 (現價 $152 ≈ 兩倍合理價)
- M觀點實作:目前已建 2% 部位 (目標 4%),計畫未來半年分批攤平 — 「即使估值偏貴也要 skin in the game」

**瓦基訪談 — AI 對知識型創作者的衝擊與適應**
- 從衝擊到正面利用:AI 是放大器,讓知識型創作者把時間從「整理/排版」轉到「對話/思考」
- 護城河來自**人與人的稀缺對話 + 故事**,不是知識點 (AI 已普及)
- 用 AI 三層次:(1)專案包/技能包系統化 (2)固定流程便於跨模型比較 (3) 強烈意圖感倒推工程
- 4 象限 AI 應用框架:資料來源(內/外) x 目的(過程/結果) — 學習筆記 / 觀點作品 / 決策報告 / 內心覺察
- 模型現況:瓦基用 Claude Max (Opus + Fable), M觀點用 GPT-5.5 (取代 Q1 用的 Grok 4.2),Gemini 雙人都冷凍

### 馬斯克帝國觀察 #75 → 修正:應為 #78 (2026-06-30) — Cybercab 上路 + FSD V14 Lite + Grok 4.5

**Tesla FSD V14 Lite 推送 HW3 (舊車型)**
- AI 主管 Ashok Elluswamy 表示 V14 Lite 已開始向部分 AI3 (HW3) 早期測試用戶推送
- **模型蒸餾技術**:從 AI4 駕駛行為「壓縮」到 AI3 (有效記憶體頻寬僅 AI4 的 15%)
- 影響:**HW3 車主軟體支援週期延長 + 新舊硬體功能差距縮小** — TSLA 二手車保值率提升
- 利多 TSLA:全車型 fleet 都能享 FSD 升級,長期積累更多里程數據訓練 → 強化先發優勢

**Cybercab (無方向盤/踏板) 在 Austin 公共道路測試**
- 量產版上路,完全無方向盤與踏板,標誌**無人駕駛技術進入實際驗證階段**
- SAE Level 4,支援中度雨雪天氣;低電量自動前往充電,異常閃燈靠邊
- 配備至少 10 個安全氣囊 + 主動式引擎蓋 (碰撞抬起降低行人傷害)
- 緊急機械釋放雙段門把手 + 雙重救援迴路 + 橙色電池冷卻液
- **印證 W26 NHTSA FMVSS 修訂利多 Cybercab 邏輯** — Robotaxi/Cybercab 商業化大幅加速

**SpaceX 7/7 納入 Nasdaq 100 指數**
- 6/26 Nasdaq 正式宣布,SPCX 將於 **2026-07-07 開盤前加入 Nasdaq 100**
- 7/6 收盤後指數追蹤基金開始買入,預計帶來 **$80-100 億美元被動資金流入**
- 短期 SPCX 股價支撐;但需觀察是否被市場提前 price in

**SpaceX + Charter Communications 洽談美國手機服務**
- Bloomberg + FT 報導:SpaceX 計畫推出 Starlink 行動通訊面向消費者
- 不再只補既有電信商死角,**直接進入消費者手機市場** → 未來與 Verizon/AT&T/T-Mobile 正面競爭
- 影響:電信三巨頭估值雙刃 (短期競爭壓力 vs 衛星補強合作)

**Grok 4.5 (1.5T 參數) 進入 SpaceX/Tesla 私人 Beta**
- 比 Grok 4.3 (0.5T) **大三倍**,接近/超越 Claude Opus 等級 (Elon 估)
- Cursor 團隊已參與 Grok v9 的 SFT + RL 訓練,**下一代 Grok 將更完整吸收 Cursor 程式開發資料**
- 下一代 2T 模型已啟動訓練,7 月底完成、8 月推出
- Elon 透露:**Grok 將每月推出一款重訓模型** + 3 個月後用 C/C++ 重寫推論堆疊「刪除大多數軟體層」大幅降低延遲
- **印證 W26 SPCX 併 Cursor 後算力 + 模型雙軌邏輯** — xAI 重返前沿模型競賽具體成型

### 富果直送 (2026-06-30) — 長榮航太 (2645.TW) 軍工無人機長單核心受惠

**核心邏輯**
- 國防無人載具採購全面轉向「大量、長單」批量模式
- **台灣 2,100 億特別預算**直接排除紅色供應鏈,小額試作紅利結束 → **訂單去碎片化暴力洗牌**
- 消耗性中小型載具的**產能與品保門檻**(AS9100 航太品保)將小型新創排除

**受惠標的**
- **長榮航太 (2645.TW)**:挾 AS9100 + 全球 MRO 規模,鎖定軍工長單核心溢價
- 21 萬架載具的不對稱作戰商機 → 大型航太巨頭規模 + 技術底蘊勝出

**Narrative 連結 W26-W27**
- 與 W27 軟板 (4958/6269) + 功率半導體 (W26 ON/TXN/IFNNY) 形成**台股供應鏈轉型主題**
- 國防 + AI 伺服器 + 摺疊機三條都跑「**高品保門檻 + 規模供應商勝出**」邏輯
- 後續觀察:長榮航 (2645) Q2/Q3 軍工訂單能見度、台灣國防特別預算撥款時程

## 走勢預測 — W27 中段觀察點 (週二補充)

- **iPhone 18 漲價 narrative** 印證 W26 Tim Cook 記憶體短缺說 → AAPL 估值與 TSM/MU 三線受惠;同時拖累中低階手機品牌 (Xiaomi/Transsion 等)
- **SPCX 估值兩極化**:M觀點 $84 vs 現價 $152,後續需觀察 7/7 Nasdaq 100 納入後 $80-100 億被動資金能否撐起估值;若無就回測 130-140 美元
- **FSD V14 Lite 蒸餾到 HW3** + **Cybercab 上路測試** + **NHTSA 法規 (W26)** → 三線同步推進,TSLA 2026 H2 雙催化 (銷量 + 估值) narrative 強化
- **Grok 4.5 + 2T 訓練中 + 每月推新模型** → xAI 重返競賽具體化,後續 W28+ 觀察 Grok 4.5 公開測試評價、2T 模型 8 月上線
- **長榮航太 + 富果 6/30** → W27 台股新主軸:國防 + 規模供應鏈


## 增量 2026-07-05 (cron 22:33)

**本地素材**: 今日無新股癌 / All-In 集數

**Gmail 增量**: 抓到 6 封新信 (M報 #315 + 馬斯克 #79 + 富果 7/1/7/2/7/3/7/4 共 4 篇);其中富果 7/2 FPC 是 7/1 FPC 的重寄,7/4 創新服務是 7/1 重寄,無需重複收錄

### 富果直送 (2026-07-01) — 創新服務 (6541.TW):自動植針機 + 台積電銅柱獨家夥伴

**核心邏輯**
- 傳統人工植針面臨晶片大面積化產能極限 (AI 晶片測試針數 3 萬 → 15 萬根)
- 創新服務**雙臂式自動植針機**暴力顛覆,合作全球二哥 **Technoprobe** 策略入股 + 鎖定美系巨頭大單
- 作為**台積電獨家夥伴**,卡位 2027 年**玻璃基板 TGV 巨量銅柱**移轉藍海
- 明後年 EPS 挑戰 30 元;產能翻倍 + 台積電獨家

**Narrative 連結**
- 印證 W25-W26 SoIC / 先進封裝主題延伸,測試介面成為 AI 晶片產能新瓶頸
- 台積電獨家夥伴地位,反映**先進封裝供應鏈集中度提升**

### 富果直送 (2026-07-02) — 金居 (8358.TW):AI 銅箔 HVLP4 首波贏家

**核心數據**
- 新一代 AI 平台 + 自研 ASIC 全面強推 **HVLP4** 極低粗糙度銅箔規格
- **加工費翻數倍**,每月數百噸剛性供需缺口
- 金居填補日廠保守擴產真空,毛利率跨越 30% 大關;第三座新廠明後年產能翻倍
- **2027 年 EPS 預估 19 元**

**受惠標的**: 金居 (8358.TW)

**Narrative 連結 W26-W27**
- 印證 W26『AI 伺服器破千瓦帶動材料規格升級』(CCL 銅箔基板 → HVLP4 銅箔)
- 與 W27 富果 7/1 創新服務 + 6/30 長榮航太 + 6/29 FPC 軟板 → **W27 富果四連發:AI 材料鏈全面升級主題**

### 富果直送 (2026-07-03) — AES-KY (6781.TW):BBU 龍頭通吃 CSP 大單

**核心數據**
- 傳統鉛酸 UPS 因效率低下加速淘汰;**輝達 GB300 將備援電池 (BBU) 列為標配** → 剛性需求
- AES-KY 通吃**四大 CSP 巨頭大單**,年底放量**高壓直流 (HVDC)** 等高階新品
- **2027 年 BBU 營收佔比衝上 76%**,EPS 挑戰 61 元,現價 18 倍本益比

**受惠標的**: AES-KY (6781.TW)

**Narrative 連結 W26-W27**
- 印證 W25『AI 資料中心缺電危機』narrative,BBU 是電力防線關鍵一環
- 與 W27 富果四連發同源:**AI 伺服器規格升級 (功耗 + 材料 + 電力)** 三線受惠
- 後續 W28 觀察:GB300 出貨後 BBU 訂單能見度 + HVDC 新品滲透

### 馬斯克帝國觀察 #79 (2026-07-03) — Tesla Q2 交車歷史新高 + Neuralink 硬腦膜穿透

**Tesla Q2 交車 480,126 輛,年增 25%**
- **遠超華爾街預估 406,000 輛**;Model 3+Y 合計 467,762 輛占絕大多數
- 能源儲存部署 **13.5 GWh** (雙引擎持續擴張)
- 歐洲市場明顯回升 (瑞典 +56% / 葡義 +43% / 丹麥 +39% / 法國 +100%),但挪威 -43% 西班牙 +5.6%
- **中國生產基地出口動能強勁,全球工廠利用率 77%**
- 7/22 (美中部時間) 財報直播;Model Y L 長軸版美國推出 $61,990 起
- 台灣 6 月進口車冠軍 (4,369 台 vs Toyota 4,256)

**Cybercab 量產進度 + 邁阿密 Robotaxi 培訓**
- Cybercab 產線自動化 >90%,virtual commissioning 提前驗證避免 Model 3 production hell
- 邁阿密 Coral Gables 消防隊接受 Tesla Robotaxi 緊急處理培訓 (電池系統 / 事故應變)
- Lars Moravy (車輛工程副總) 訪談 **強調 real world AI**:未來 5 年最看重的是把 AI 放進真實世界 (Robotaxi + Cybercab + Optimus 閉環)
- Optimus 生產線在 Fremont 部署,設計者跨自汽車產線團隊
- **印證 W26 NHTSA FMVSS 修訂利多 Cybercab 邏輯 + FSD V14 Lite 蒸餾** — Tesla 全 fleet 都能享 FSD 升級

**Tesla 挖角 Intel Gary Jiang 主導 TERAFAB 晶片計畫**
- Jiang 曾負責 Intel 14nm/22nm 大規模製造,亞利桑那廠區運營
- 顯示 Tesla 從**自行設計晶片 → 大規模製造**跨界

**SpaceX 相關**
- Merlin 1D 引擎第 1000 台完工;單一助推器最高飛 35 次
- Starship 第 13 次發射前 60 秒靜態點火測試
- **馬斯克否認 SpaceX 做 AI 手機** (雖 WSJ 報導 Snapdragon + xAI 原型),但 1 月曾稱「Starlink 手機未來不排除」
- **NHTSA 結束 69.5 萬輛 Tesla 意外減速調查** (2022 軟體更新已解決)

**Neuralink 硬腦膜穿透手術突破**
- 2026-05 加拿大 UHN 首例 Transdural Surgery,**省略切開硬腦膜步驟**
- ICG 螢光血管攝影 + OCT 光學同調斷層掃描,精準避血管
- 「第一性原理」設計哲學:先思考能否刪除步驟

**Narrative 連結**
- 印證 W26 Cybercab 量產 + FSD 蒸餾 + Robotaxi 商業化三線邏輯
- Q2 交車 480K 是 TSLA 2026 H2 銷量催化最強實證
- 後續 W28-W29:7/22 財報是關鍵 anchor

### M報 #315 (2026-07-03) — GPT-5.6 限定推出 + 蘋果漲價 + Meta 智能眼鏡

**注**: M報改採「與直播集數同步」編號,從此期 #315 開始,不再延續舊 #534 序列;新舊序列**兩套並存**約 220 期差

**GPT-5.6 有限預覽 → OpenAI 追上 Anthropic**
- **Terminal-Bench 2.1**: GPT 5.6 Sol Ultra **91.9%** > Fable 5 (原 Mythos) **88%**;中階 GPT 5.6 Terra 84.3% 打平 Fable 5 高階
- **Exploit Bench**: GPT 5.6 Sol 用 <一半 token 達 Fable 5 類似成績 → 資安能力也追平
- **OpenAI vs Anthropic 真實差距約 1-1.5 個月**,不是「Google 被甩開」等級
- 前沿模型監管成新難題:中國開源 GLM 5.2 已接近 GPT 5.4,若美方限制太久 → 失去領先時間窗

**蘋果全球調漲 Mac / iPad / Vision Pro / Apple TV (iPhone 暫未動)**
- Tim Cook 承諾漲價後**同日突然執行**,反彈比預期大
- **美光 Sadana 補槍**: 過去客戶 (影射蘋果) 殺價太兇 → 現在供給不足是必然結果
- 成本合理性分析:8GB RAM 半年漲 NT$1,200 / 512GB SSD 漲 NT$1,000 → MacBook Neo 成本增 NT$2,500,漲 NT$3,000 合理
- **記憶體大缺 → 整個消費電子壓力擴散**,3 大廠 (MU/Samsung/SK Hynix) 擴產保守
- 通路預購被迫加價/取消訂單,顯示漲價**溝通不細膩**

**Meta Glasses 自有品牌推出**
- 脫離 Ray-Ban 品牌授權,**便宜 $80** (從 1 萬多 → 9 千多台幣)
- 三種鏡框 26 種組合,提供**非墨鏡款式** → 可日常配戴 → 使用場景大幅擴大
- Ray-Ban Meta Smart Glasses 已升級 **Muse Spark AI 版本**
- **Q3-Q4 Google 智能眼鏡對決**:Google 搭配 Gemini 4.0 Flash 進場
- **智能眼鏡 = 比手機更自然的 AI 入口**,Meta 已領先 2 年
- **台灣至今未開放 AI 功能** → M觀點強烈抱怨,擔心 Google 先在台灣推出 → 削弱 Meta 先發優勢

**受惠/受傷邏輯**
- 受惠: OpenAI (估值防線守住) / MU + Samsung + SK Hynix (DRAM+NAND 漲價紅利) / Meta (眼鏡 + Muse Spark)
- 受傷: Anthropic (領先窗被壓縮) / 蘋果 (漲價 PR 危機) / Google (Q4 眼鏡對決壓力)
- 潛在: PLTR × NVDA / Claude Sonnet 5 (下一期 EP316 主題)

**Narrative 連結 W25-W27**
- 印證 W26『Google 痛失 Shazeer + Jumper』narrative,但**同時給 Anthropic 反面警訊**:OpenAI 沒被甩開
- 蘋果漲價**回扣 W26 M報 #534 iPhone 18 漲價預測** → **W27 蘋果已實作** (iPhone 尚未,但其他線先動)
- **記憶體漲價 narrative** 從 W26 (Tim Cook + Elon 同調) → W27 (蘋果實際漲價 + 美光補槍) 具體化
- Meta 眼鏡 vs Google 眼鏡對決 → W28-W30 觀察 Google 眼鏡發表時程 (預定 Q3-Q4)
- 下一期 M報 #316 主題已預告:**Claude Sonnet 5、Meta 也要賣算力、PLTR 合作 NVDA** → W28 重點監控

### 富果直送 (2026-07-04) — 元山 (6275.TW):車用跨足 AI 伺服器液冷

**核心邏輯**
- AI 邊緣運算把氣冷逼向物理極限
- 元山避開一線大廠正面殺價,以 **Sidecar 側櫃式水對氣方案**卡位**中小企業機房不需全面改建**的客製化液冷藍海
- 高階 120kW / 150kW 液冷新品出貨驗收最後階段;十月完工東莞新廠
- **2027 年獲利爆發 +77.67%,EPS 挑戰 3.39 元**;現價僅 14 倍預期本益比

**受惠標的**: 元山 (6275.TW)

**Narrative 連結**
- 與 W27 富果 AES-KY (BBU 電力) + 金居 (HVLP4 銅箔) 形成 **AI 伺服器規格升級三大子題** (電力 + 散熱 + 材料)
- 印證 W25『AI 伺服器功耗突破 1kW 帶動液冷普及』
- Sidecar 中小企業機房定位 → **避開 NVDA 直供大 CSP 的紅海**,較長線的獲利可預測性

## 走勢預測 — W27 收尾觀察點 (7/5 更新)

- **Tesla Q2 交車 480K 遠超預期** → TSLA 2026 H2 銷量催化力確立,7/22 財報看能源毛利與 Robotaxi 商業化 guidance
- **GPT-5.6 追上 Anthropic** → AI 模型競賽仍雙頭馬車,MSFT (OpenAI 主要投資者) 與 GOOGL / NVDA 三線都受惠 (需求持續)
- **蘋果漲價 + 美光補槍** → MU/Samsung/SK Hynix Q3 財報 guidance 上修可能性大;iPhone 18 漲價預期強化
- **富果四連發** (創新服務 / 金居 / AES-KY / 元山) 加上 W27 首日的 FPC 缺貨 / 長榮航太 → **W27 台股 6 檔完整 AI 供應鏈主題** (測試介面 / 銅箔 / BBU / 液冷 / FPC / 國防航太)
- **Neuralink 硬腦膜穿透**:對 NVDA/BCI 生態長期利多,但短期不影響股價
- **M報 EP316 預告 PLTR × NVDA + Meta 賣算力 + Claude Sonnet 5** → W28 三大重點提前部署
