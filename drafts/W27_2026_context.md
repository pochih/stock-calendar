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

