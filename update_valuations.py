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
            "fwd_pe_base": 15, "fwd_pe_bull": 15, "ps_base": 3,
            "ev_ebitda_base": 10, "dcf_disc_rate": 0.10,
            "dcf_fcf_growth_5y": 0.12, "dcf_terminal_growth": 0.03,
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
            {"week": "2026-W21", "category": "IPO + 估值", "snippet": "Gavin Baker 點出 AI 板塊 cross-sectionally inefficient:memory(SK Hynix 5x / Samsung 6x / Micron 7x)、NVDA(forward PE 低 teens)被低估"},
            {"week": "2026-W23", "category": "IPO + 估值", "snippet": "Coatue Laffont 直接點名:沒有 TSMC 級別代工的對應產業,每用戶記憶體需求隨 AI memory/context 可 5x → 重估邏輯仍未走完"},
        ],
    },
    "NVDA": {
        "name": "NVIDIA",
        "category_label": "AI 算力 GPU 龍頭 (CUDA + Blackwell / Vera Rubin Inference Factory)",
        "valuation_params": {"fwd_pe_base": 25, "fwd_pe_bull": 30, "ps_base": 18, "ev_ebitda_base": 22, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.30, "dcf_terminal_growth": 0.04},
        "bull_thesis": [
            "Jensen 親上 All-In W12 (3/19):Vera Rubin Inference Factory 報價 $500 億 vs ASIC/AMD $250-300 億,但 $500 億工廠 token 單位成本是對手的 1/10 — 『產的 token 越多越便宜,我們絕對在 1 million X 的路上』,inference 比 generative 已漲 10,000 倍",
            "Gavin Baker (W21) 直接點名 AI 板塊 cross-sectionally inefficient:NVDA forward PE 低 teens 被低估 — Q1 26 報 $81.6B 營收 +85% YoY、$58B 淨利、$48B FCF、加碼 $80B 買回,股價今年只 +16%",
            "Friedberg (W12) 補刀 Physical AI / Robotics 是『$50T 產業首次數位化』TAM 故事;Brad Gerstner W19 估 Anthropic ARR 已 $44B 並 10x/年",
            "Chamath W21:Cursor Composer 2.5 在 Colossus 2 上做 3 週 RL 就上 Pareto 前緣超過 Codex/Claude;NVDA 老 H100 透過 disaggregated inference 可用 10-15 年",
            "Mark Benioff (W20) 親口『讓 Jensen 賣晶片』成國家戰略,Trump-Xi 主軸『要 Nvidia 贏不要讓 Huawei 補位』",
            "Burry (W47 2025) 主打 depreciation schedule 造假被 Chamath/Freeberg 公開反駁:GPU 經濟學每 token 直接連結廣告/coding 售價,『house of cards』論述被技術性拆穿",
        ],
        "bear_thesis": [
            "Sacks (W19) 把 Anthropic Colossus 1 整廠 $45B 三年單算成 Rockefeller 級壟斷;若 FDA-for-AI EO 通過,NVDA 客戶結構從 5-7 家 hyperscaler 壓到 3-4 家",
            "Burry (W47 2025) NVDA + PLTR 同框放空:hyperscaler 把 GPU 攤提從 4 年拉到 6 年人為墊高 EPS 10-12%、$600B OpenAI compute 承諾 vs 二級市場估值 1:1 是『定時炸彈』",
            "ASIC 替代壓力升級:Bernstein 估 ASIC 滲透 2026-2028 從 15% → 30% — 即便 Jensen W12 嘴硬,75% Vera Rubin 留給 GPU、25% 切給 Groq LPU 已是默認 ASIC 會吃份額",
            "Chamath W47 2025 直言『risk-off + capex digestion』:NVDA/MSFT/ORCL/AVGO 同週跌 6-20%;DeepSeek-R1 2025/1/27 NVDA -17% / -$600B 是預演",
            "AVGO 指引保守 W24 觸發 SOX -10%;forward PE 16x 建立在 FY27 EPS 共識線性外推,若 Anthropic ARR 增速從 10x/年掉到 3x,NVDA forward EPS 直接砍半",
            "Sacks (W47 2025 OpenAI Code Red) 點 Sam 對 NVDA 的『options not real deals』揭穿 — 那筆投資只是『option to invest』,NVDA + OpenAI 互相 round-tripping 部分敘事破功",
        ],
        "briefing_mentions": [
            {"week": "2026-W12", "category": "AI 硬體", "snippet": "Jensen 親上 All-In:Vera Rubin Inference Factory $500 億報價、ASIC/AMD 只要 $250–300 億卻仍能贏,token 單位成本是對手的 1/10。『兩年算力需求漲 10,000 倍,我們絕對在 1 million X 的路上』"},
            {"week": "2026-W21", "category": "IPO + 估值", "snippet": "Gavin Baker:NVDA(forward PE 低 teens)被低估,power/cooling/optical 反而過熱。NVDA Q1 $81.6B 營收 +85% YoY、$80B 買回 + 季配息 25x,股價今年只 +16%"},
            {"week": "2026-W19", "category": "AI 算力", "snippet": "Sacks 警告 Anthropic Colossus 1 整廠 $45B 三年是 Rockefeller 級壟斷。NVDA 長線最大不確定性是『主權 GPU 配額制』KYC over GPU access"},
            {"week": "2026-W22", "category": "財報", "snippet": "NVIDIA 財報 Q1 26 強勁但市場已完全 priced in,小回檔;AI Infra 從『無腦多』走入『區分受惠程度』階段"},
            {"week": "2026-W24", "category": "市場修正", "snippet": "Broadcom 指引保守 + 美就業太強 → SOX 單日 -10%,AI Infra 群修(NVDA 同步)"},
        ],
    },
    "AVGO": {
        "name": "Broadcom",
        "category_label": "AI ASIC + 半導體 IP + 網通 (Google TPU / Meta MTIA / OpenAI custom silicon)",
        "valuation_params": {"fwd_pe_base": 22, "fwd_pe_bull": 28, "ps_base": 18, "ev_ebitda_base": 20, "dcf_disc_rate": 0.09, "dcf_fcf_growth_5y": 0.22, "dcf_terminal_growth": 0.035},
        "bull_thesis": [
            "AVGO 已成 hyperscaler 自研 ASIC 唯一全方案供應商:Q4 25 Google TPU + Meta MTIA + OpenAI 三大客戶同框,Bernstein 估 ASIC 滲透 2026-2028 從 15% → 30%",
            "Jensen W12 親自確認 25% Vera Rubin 工作負載要留給 Groq LPU / 混合 ASIC — 連 NVDA 都默認 ASIC 會吃份額",
            "Sacks (W47 2025) 把 AVGO 與 MSFT/NVDA/ORCL 並列為『有錢可花、需要花錢』的四家公司",
            "Hock Tan 訂價克制 + 保守財測讓 AVGO 一向給 sandbagging 數字(W24 M報比喻『大谷打 50 全壘打卻說下季 55』)",
            "VMware 軟體業務提供 stable cash flow + 80%+ 毛利,讓 AVGO 比純晶片廠有更低 beta",
            "Coatue Laffont (W23):『邊際成本不為零』結構性偏好客製化 ASIC — AVGO 是這波從 training 走入 inference 的最大結構性贏家",
        ],
        "bear_thesis": [
            "W24 (6/5) AVGO 指引保守觸發 SOX -10%、AVGO 單日 -7%;P/S 25.9x 在 deep cyclical 看更脆弱",
            "Jensen W12 嘴硬:CUDA + Dynamo + 整廠 token economics 仍是 ASIC 短版;AVGO 若拿不到 inference 主場成長天花板比預期低",
            "客戶集中度極端:Google + Meta + OpenAI 三家貢獻 ASIC 業務大部分營收;Google TPU 自製深化反而可能在 2027-28 內製化",
            "Chamath (W47 2025) 痛批 risk-off + capex digestion,AVGO 連帶 MSFT/NVDA/ORCL 同跌 6-20%",
            "DeepSeek-R1 2025/1/27 NVDA -17% 那天 AVGO -17%(同幅度暴跌),beta 與 NVDA 同步",
            "Anthropic 簽 Colossus 1 (NVDA H100) 而非全部走 AVGO ASIC;當 GPU 供給瓶頸打開,hyperscaler 可能臨時把訂單從 ASIC 轉回 GPU 規避 ASIC 開發週期 18-24 個月",
        ],
        "briefing_mentions": [
            {"week": "2026-W24", "category": "市場修正", "snippet": "Broadcom 指引保守 + 美就業太強 → SOX 單日 -10%。AVGO 沒上調展望(它一向給保守財測,但市場期待大谷打 50 全壘打卻說下季 55)"},
            {"week": "2026-W18", "category": "AI 鬼故事", "snippet": "WSJ 翻出 OpenAI 沒達標,引發市場擔心 OpenAI CapEx 採購承諾履行 → NVDA + AVGO 同步修正"},
            {"week": "2026-W12", "category": "AI 硬體", "snippet": "Jensen 親上 All-In:『ASIC 路線(MRVL/AVGO)短線會有雜訊但難撼動 CUDA』,但 Chamath 讓 Jensen 確認 Vera Rubin 25% 留給 Groq LPU/GPU 混合"},
            {"week": "2026-W23", "category": "IPO + 估值", "snippet": "Coatue Laffont:『邊際成本不為零』結構性偏好客製化 ASIC — AVGO 是這波 AI capex 從 training 走入 inference 的最大結構性贏家"},
            {"week": "2026-W02", "category": "微軟/OpenAI", "snippet": "Build 2026:AVGO/AMD/INTC 列名 MRC 開放網路協議共同開發者,證明 AVGO 不只 ASIC 也在 Ethernet/NIC 路線拿到 hyperscaler 鎖定"},
        ],
    },
    "AAPL": {
        "name": "Apple",
        "category_label": "消費電子 / Services (iPhone + App Store) + AI laggard",
        "valuation_params": {"fwd_pe_base": 28, "fwd_pe_bull": 32, "ps_base": 8, "ev_ebitda_base": 18, "dcf_disc_rate": 0.08, "dcf_fcf_growth_5y": 0.06, "dcf_terminal_growth": 0.025},
        "bull_thesis": [
            "WWDC 2026 AFM3 五大模型陣列 + Siri 接 Gemini 該補的都補了 (M觀點 W25 給 70 分);摺疊 iPhone 18 預期 H2 2026 上市開啟新 super-cycle,Services 毛利率 >74% 為穩定壓艙石",
            "Apple Silicon (M5 / 新 Mac Studio 1TB 統一記憶體) 跑開源模型成企業 AI『主權對沖』選項 (All-In W22 共識點);Anthropic Fable 5 出口管制風波後,本地 SLM 路線進一步合理化 (W24)",
            "Tim Cook 9 月卸任、John Ternus 接班 (M報 W18) — 工程主導 CEO 換血為新階段催化",
            "巴菲特 13F 雖持續減持但仍是最大持股,加上 fwd PE 31x 對應 Services 毛利結構支撐合理估值底;Apple 下單 Intel 18A 代工 MacBook Neo (W20) 為自家成本結構降本鋪路",
            "現金 + 投資組合 $160B+,每季 $25B+ buyback 提供 floor;低 beta + 全球品牌議價力讓宏觀降息環境下仍是 risk-off 首選",
        ],
        "bear_thesis": [
            "All-In W19 (Four CEOs) 直言『Apple seems to be MIA. They don't seem to want to play』— frontier AI 競賽完全缺席,自研 AFM 進度落後 (M觀點 W14)",
            "WWDC 2026 AFM3 首次低頭跟 Google Gemini 合作 (蒸餾 + Cloud Pro on Google Cloud),自研進度落後訊號 → AAPL 估值結構性壓力 (M觀點 W25);New Siri 兩年延期後仍未真正交卷,歐盟/中國 (~30% 營收) 不上線引發失望",
            "Sacks W20 點出 OpenAI 傳考慮告 Apple『Siri 整合失敗,billions in subscription revenue 沒到位』— LLM 廠商與 platform 客戶關係極度脆弱",
            "Mean target $314 vs 當前 $298 僅 +6% upside (12 檔中最低);Services 反壟斷風險 + Google search 默認搜索引擎 $20B/年合約 (DOJ 案) 為估值上方天花板",
            "成長放緩 — iPhone 銷量歷年顯示創新疲乏;Forward PE 31x 已偏高,若 AI 自研持續落後,結構性 de-rating 風險",
            "中國市場壓力延續 (Chamath W13『品牌歸零』論述適用),加上歐盟 DMA 對 App Store 30% 抽成的結構性侵蝕",
        ],
        "briefing_mentions": [
            {"week": "2026-W25", "category": "蘋果", "snippet": "WWDC 2026 AFM3 五大模型陣列 + Siri 接 Gemini。M觀點給 70 分:該補的都補了,但 New Siri 還沒真正交卷。AAPL 估值結構性壓力 — 首次低頭跟外部模型合作,被視為自研進度落後訊號"},
            {"week": "2026-W22", "category": "AI 軟體", "snippet": "All-In 共識:Apple Silicon (M5 / 新 Mac Studio 1TB 統一記憶體) 跑開源模型成為企業 AI 主權對沖選項"},
            {"week": "2026-W20", "category": "SaaS / 蘋果", "snippet": "Sam Altman 傳考慮告 Apple (Siri 整合失敗,billions in subscription revenue 沒到位);Apple vs OpenAI 法律戰升溫"},
            {"week": "2026-W18", "category": "馬斯克 / 接班", "snippet": "Tim Cook 將卸任,John Ternus 9 月接任 (Cook 最後 WWDC);蘋果接班過渡到工程主導"},
            {"week": "2026-W14", "category": "AI 軟體", "snippet": "Siri 接 Gemini (後續 6 月 WWDC 正式版)。M觀點:Apple 開放多模型 (GPT/Gemini) 說明自研 AFM 進度落後 → Apple AI 故事承壓,Google 受惠 Gemini 進手機 OS"},
        ],
    },
    "AMZN": {
        "name": "Amazon",
        "category_label": "雲端 (AWS) + 廣告 + Robotics (倉儲機器人)",
        "valuation_params": {"fwd_pe_base": 28, "fwd_pe_bull": 35, "ps_base": 4, "ev_ebitda_base": 18, "dcf_disc_rate": 0.09, "dcf_fcf_growth_5y": 0.18, "dcf_terminal_growth": 0.035},
        "bull_thesis": [
            "Jason W02『2026 預測』直接喊 Amazon 是『第一家企業奇點』(機器人取代員工貢獻超越人類);Optimus / 倉儲 robotics 落地後,Retail 利潤結構性翻轉",
            "AWS Q1 26 財報 +28.4% YoY (W19),雖低於 Google +63.4% 但 M觀點 認為差距沒這麼大 — Azure OM 下滑反讓 AWS 取得 OpenAI 模型供應大利多",
            "Anthropic 大客戶吃 Bedrock 算力 — Brad W15 拆解 Anthropic ARR 衝 $30B 為『AI 算力鏈 NVDA、AMZN Bedrock、CRWV 強烈正面催化』",
            "AWS Trainium 2/3 + Strands Agents (re:Invent 2025) 為自研 ASIC 路線,降低對 NVDA 依賴",
            "Mean target $313 vs 當前 $244 給 +28% upside (Mag 7 中段);Druckenmiller / Ackman 13F 重押 AMZN+GOOGL",
            "廣告業務年化 ~$60B 已成第三引擎,Prime Video 廣告填補 Retail 邊際利潤",
        ],
        "bear_thesis": [
            "Chamath W11『Amazon agent 寫的程式造成 sev-1,下令 AWS 必須人類 review』警鐘 — critical workflow 還沒一個成功案例",
            "三大雲『供給面經濟』供給端皆飽和 (W19);Azure OM 下滑可能讓市場質疑 hyperscaler 議價力已到頂",
            "Retail 部門毛利率仍受工會 + 物流通膨壓力,robotics 落地時程若推遲到 2027+,『企業奇點』故事提前承壓",
            "Anthropic Fable 5 出口管制 (W25, Amazon 紅隊找到 jailbreak) 雖短期讓 AMZN 取得守門人位置,但長線 anti-trust 風險上升",
            "fwd PE 24.8x 看似合理但 Retail 占營收 60%+,若消費走弱 + 廣告同業競爭加劇 → AWS 單獨支撐估值結構困難",
            "Bernie Sanders 提案沒收 AI 公司 50% 股權 (W24);Amazon 同時是『AI capex 大戶』+『裁員大戶』雙重 PR 風險源",
        ],
        "briefing_mentions": [
            {"week": "2026-W02", "category": "宏觀資金", "snippet": "Jason 2026 預測:Amazon 是『第一家企業奇點』(機器人超越人類員工貢獻)"},
            {"week": "2026-W11", "category": "宏觀政治 / AI", "snippet": "Chamath 警鐘:Amazon 剛因為 agent 寫的程式造成 sev-1 才下令 AWS 必須人類 review,『critical workflow 還沒一個成功案例』"},
            {"week": "2026-W15", "category": "AI 模型", "snippet": "Brad Gerstner 拆解 Anthropic 衝 $30B run rate → 對 AI 算力鏈 (NVDA、AMZN Bedrock、CRWV) 是強烈正面催化"},
            {"week": "2026-W19", "category": "AI 雲端 / 微軟", "snippet": "三大雲財報:Google +63.4% / AWS +28.4% / Azure +40%。MSFT『放開』OpenAI,AWS 取得 OpenAI 模型供應大利多"},
            {"week": "2026-W25", "category": "AI 模型", "snippet": "Anthropic Fable 5 被下架:Amazon 紅隊 jailbreak 成功 → 5+ 家科技高層警告白宮 → 商務部以國安為由禁外國人存取"},
        ],
    },
    "META": {
        "name": "Meta Platforms",
        "category_label": "廣告 (FB/IG) + Reality Labs + Llama 開源",
        "valuation_params": {"fwd_pe_base": 22, "fwd_pe_bull": 28, "ps_base": 8, "ev_ebitda_base": 15, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.15, "dcf_terminal_growth": 0.035},
        "bull_thesis": [
            "Mean target $827 vs 當前 $577 = +43% upside (12 檔中最大 upside);fwd PE 15.9x (相對便宜!) 結構性低於 Mag 7 平均",
            "Llama 開源策略是 hyperscaler 中最 contrarian — Chamath W24 透露已買 2GW Arizona 數據中心專門 host 開源模型;若 Anthropic 走 KYC 預審路線受挫,Llama / DeepSeek 系開源模型轉成企業 alternative",
            "Druckenmiller 13F MSFT + META + AMZN 三 AI 大押,極集中策略代表頂級配置者仍把 META 列為 AI capex 受惠核心",
            "Reality Labs 智能眼鏡 + Agent 是 CapEx 持續攀升的合理理由;Ray-Ban Meta 銷量超預期 + Meta Quest 與 Apple Vision Pro 雙寡頭格局",
            "Meta 啟動新一輪大裁員 (中階主管為主,W22) — AI 取代部分職能後人力結構優化;Goldman David Solomon 紐時投書 (W22)『AI Job Apocalypse 被誇大』為敘事轉折點",
            "Meta 廣告 ARPU 持續成長 + Agentic AI Tool (廣告主自動生成 creative) 提升小客戶 TAM",
        ],
        "bear_thesis": [
            "Chamath W21 公開警告:『Zuckerberg 邊裁 8K 邊在員工電腦裝錄影軟體訓練模型』— PR 災難正餵養 anti-AI 民意,『America Turns on AI』政治反撲已成形",
            "Meta 同步推 MCI 員工工作電腦監控以蒐集 AI Agent 訓練資料 (W19);中國發改委擋下 Meta $20 億併購 Manus AI Agent — Meta 訴訟與監管風險疊加",
            "Chamath W13『品牌歸零』論述 — Tesla 對 BMW、BYD 對 Mercedes 才是 AI 時代範本;Meta 雖在廣告佔有率高,但 LVMH/Ferrari 訂價權都在掉的同樣邏輯適用",
            "Reality Labs 持續虧損 ($15B+/年),CapEx 持續攀升 (智能眼鏡 + Agent + ASIC),若智能眼鏡銷量 plateau,投資人會質疑 Zuck『all-in metaverse』第二季",
            "TikTok / ByteDance (Coatue Magnificent 8) 在年輕用戶端持續分食 Instagram Reels 用戶時間",
            "fwd PE 15.9x 反映市場對 Reality Labs 永久虧損 + AI capex ROI 不確定的 discount;Chamath『500 天後的 ROI 大檢視』提前發生風險",
        ],
        "briefing_mentions": [
            {"week": "2026-W21", "category": "IPO + 估值", "snippet": "Chamath 警告『America Turns on AI』政治反撲已成形:Zuckerberg 邊裁 8K 邊在員工電腦裝錄影軟體訓練模型 — 這些 PR 災難正餵養 anti-AI 民意"},
            {"week": "2026-W22", "category": "財報 / AI 軟體", "snippet": "Meta 啟動新一輪大裁員 (中階主管為主),AI 取代部分職能。M觀點:Meta 裁員是 AI 落地後的人力結構優化,不是業務衰退"},
            {"week": "2026-W19", "category": "Meta", "snippet": "中國發改委擋下 Meta $20 億併購 Manus AI Agent。Meta 同步推 MCI 員工工作電腦監控以蒐集 AI Agent 訓練資料"},
            {"week": "2026-W13", "category": "AI 模型", "snippet": "All-In 為 Anthropic 一代盛世背書,Chamath 預言『品牌歸零』— Tesla 對 BMW、BYD 對 Mercedes 才是 AI 時代範本,只有 abundance + value 能存活"},
            {"week": "2026-W24", "category": "股癌觀點", "snippet": "股癌:Meta AI 模型受美國監管管制可能反推 edge computing 發展"},
        ],
    },
    "TSM": {
        "name": "TSMC ADR",
        "category_label": "全球先進製程晶圓代工獨佔",
        "valuation_params": {"fwd_pe_base": 22, "fwd_pe_bull": 28, "ps_base": 12, "ev_ebitda_base": 15, "dcf_disc_rate": 0.09, "dcf_fcf_growth_5y": 0.20, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "AI capex super-cycle 主要受惠者:Sacks (W07) 指四大 hyperscaler 2026 CapEx 6,000 億美元等同 2% GDP 順風,全部 GPU/ASIC/Maia/TPU/AI5/MTIA 都得排隊到台積電做 — 訂單能見度拉到 2028",
            "SoIC + CoWoS 先進封裝壟斷:富果 W22 點出 AI 晶片光罩面積撞牆後,從『平房擴建』走向『垂直堆疊』,3D 封裝是下一個十年戰場且唯有台積電有完整方案",
            "Coatue Laffont (All-In Summit W23) 點名『沒有 TSMC 級別代工的對應產業』— 把台積電擺在 Mag 7 級別 monopoly 位置",
            "Intel Foundry 重生未撼動 TSMC:W20 蘋果下單 Intel 18A 當天 TSM ADR 僅 -0.6%,Intel 拿到關鍵驗證但短期仍只能當『第二選項』",
            "Tesla Terafab 100M sqft 計畫 (W13) + SpaceX Starlink V2 衛星晶片全部仍要台積電",
            "FY27 EPS 共識上修 + CapEx W03 從 $42-44B 拉到 >$50B,代表管理層自己對 2027 訂單能見度確認",
        ],
        "bear_thesis": [
            "M觀點 (W20) 直言『TSMC 合理估值 NT$2200-2500,2027 H2 後毛利率將自高位回落為正常化』",
            "AI capex 在 datacenter NIMBY 加劇下面臨修正風險:Chamath (W16) 拋『五級火警』警告,Maine 全面禁建 + 6B 案 town board 一夜被罷免",
            "fwd PE 23.5x 已是過去 10 年 90 百分位估值;Dalio (W10) 警告『AI 技術會留下但大多數公司不會留下』",
            "地緣政治尾風險:川習會 (W21) 雖暫穩台海但中美 AI 算力競爭框架不變,台積電 ADR 與本尊 7-8% 折溢價反映美中脫鉤情境下的 valuation discount",
            "Chamath (W18) 強調 power supply 卡關才是真瓶頸 (9GW 計畫 50% 遭抗議);『500 天後 ROI 大檢視』可能提前到來",
            "Mean target $473 vs 當前 $462 隱含 upside 僅 2.4% (n=11 analysts,台廠 ADR coverage 偏少),共識已 fully priced",
        ],
        "briefing_mentions": [
            {"week": "2026-W20", "category": "宏觀市場", "snippet": "M觀點:蘋果下單 Intel 18A 當天 TSM ADR 僅 -0.6% — Intel 拿到關鍵驗證但短期難撼動 TSMC。TSMC 合理估值 NT$2200-2500,2027 H2 後毛利率將自高位回落為正常化"},
            {"week": "2026-W22", "category": "台股深度", "snippet": "富果直送 SoIC 深度報告:AI 晶片光罩面積撞牆 → 垂直堆疊 (SoIC + 混合鍵合)。封裝向晶圓製造靠攏,3D 封裝是下一個十年戰場"},
            {"week": "2026-W23", "category": "IPO + 估值", "snippet": "Coatue Laffont (All-In Summit) 點名:『沒有 TSMC 級別代工的對應產業』,直接把台積電擺在不可複製的 monopoly 位置"},
            {"week": "2026-W03", "category": "股癌觀點", "snippet": "股癌:台積電 CapEx 2026 預估上修 (後續 Q1 財報全年 $42-44B 修到 >$50B)。家登/高力/帆宣/京鼎/世禾 後續確定性提升"},
            {"week": "2026-W21", "category": "宏觀政治", "snippet": "川習會聚焦半導體出口管制與台海。M觀點:中美 AI 算力競爭框架不變,台積電仍是核心 — foundry 獨佔地位讓 TSM 始終是中美兩端都得買單的標的"},
        ],
    },
    "2330.TW": {
        "name": "台積電 (TWSE)",
        "category_label": "全球先進製程晶圓代工獨佔 (台股本尊)",
        "valuation_params": {"fwd_pe_base": 20, "fwd_pe_bull": 25, "ps_base": 11, "ev_ebitda_base": 14, "dcf_disc_rate": 0.09, "dcf_fcf_growth_5y": 0.20, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "投信法規鬆綁帶動本季資金行情:股癌 (W17) 觀察台積電解封後資金行情啟動,W20 進一步點出『額度放寬後投信輪動效應 — 中小股投信停利救火台積電』",
            "AI capex super-cycle 直接受惠 + W22 富果 SoIC 報告把先進封裝定位為『下一個十年戰場』— foundry 龍頭吃最大紅利",
            "Coatue Laffont (All-In Summit W23) 把台積電擺在不可複製的全球 monopoly 位置 — 即便 NT-listed 存在流動性折價,長線估值錨點仍跟 ADR 同源",
            "FY27 EPS 與 CapEx 上修同步 (W03 CapEx 從 $42-44B 修到 >$50B)",
            "33 位分析師 vs ADR 僅 11 位 — 台廠 coverage 完整,mean target NT$2647 vs 當前 NT$2410 upside ~9.8%",
            "Intel 18A 蘋果驗證未撼動本尊:W20 TSM ADR 僅 -0.6%,本尊修正幅度更小",
        ],
        "bear_thesis": [
            "M觀點 (W20) 直接點名『TSMC 合理估值 NT$2200-2500』— 當前 NT$2410 已在區間上緣,2027 H2 後毛利率將自高位回落為正常化",
            "台股 +42% YTD 上 4 萬點 (W20)、融資餘額創高;台積電作為權值王首當其衝面臨技術性回檔",
            "Chamath (W16) datacenter『五級火警』警告:若全美 NIMBY 擴散導致 hyperscaler 砍 capex,台積電海外設廠的高成本擴張面臨需求面下修",
            "地緣政治尾風險:川習會 (W21) 議題涵蓋台海 — 台廠 ADR 折溢價長期反映此風險,本尊在台股直接交易反而是流動性最大、衝擊最直接的標的",
            "Forward PE 19.6x 看似合理,但前提是 FY27 EPS 共識成真;若 Dalio (W10) 警告的『AI 技術留下但公司不一定留下』情境兌現,本尊比 ADR 跌幅更大 (融資斷頭壓力)",
            "Chamath (W18) 點名 power supply 才是真正瓶頸,若 hyperscaler 單位 token 經濟學沒改善,台積電作為最大 picks-and-shovels 標的會跟著估值修正",
        ],
        "briefing_mentions": [
            {"week": "2026-W20", "category": "宏觀市場", "snippet": "M觀點:台股 +42% YTD 融資餘額創高,情緒 90 度但資金面 80 度。Intel 18A 蘋果驗證當天 TSM ADR 僅 -0.6%,台積電合理估值 NT$2200-2500"},
            {"week": "2026-W17", "category": "股癌觀點", "snippet": "股癌 EP655-#656:市場大幅反彈、台積電解封後資金行情啟動。投信法規鬆綁帶動本季資金輪動"},
            {"week": "2026-W20", "category": "股癌觀點", "snippet": "股癌 EP661-#662:台積電額度放寬後投信輪動效應 — 中小股投信停利救火台積電,盤面修正反而是汰弱留強好機會"},
            {"week": "2026-W22", "category": "台股深度", "snippet": "富果 SoIC 深度報告:AI 晶片光罩面積撞牆 → 垂直堆疊。封裝向晶圓製造靠攏,3D 封裝是下一個十年戰場"},
            {"week": "2026-W03", "category": "股癌觀點", "snippet": "股癌:台積電 CapEx 2026 預估上修。家登/高力/帆宣/京鼎/世禾 後續確定性提升"},
        ],
    },
    "MSFT": {
        "name": "Microsoft",
        "category_label": "雲端 (Azure) + 365/GitHub Copilot + OpenAI 戰略合作",
        "valuation_params": {"fwd_pe_base": 25, "fwd_pe_bull": 32, "ps_base": 12, "ev_ebitda_base": 18, "dcf_disc_rate": 0.09, "dcf_fcf_growth_5y": 0.15, "dcf_terminal_growth": 0.035},
        "bull_thesis": [
            "Satya Nadella 親上 All-In (W04 Davos):Azure 定位為『token factory』+ Foundry App Server 同時編排所有家模型 — 模型不可知論比 OpenAI 單押更穩,All-In 隱含背書",
            "微軟 MAI-Thinking-1 發表 (W24):1T 總參數 / A35B MoE,盲測對 Claude Sonnet 4.6 勝出 — GitHub Copilot / 365 Copilot 內部 Sonnet token 成本可大降",
            "微軟『放開』OpenAI (W19):換到 (1) OpenAI 產品優先推出權 (2) 技術授權延長至 2032 (3) 自家平台賣 OpenAI 服務不用分潤",
            "Bill Ackman 公開看好 MSFT (W22) — 對沖基金大佬背書 + Azure +40% YoY (W19 三大雲財報);Azure 純 OM 估仍 35%+",
            "Chamath (W18) 點名:OpenAI miss 1B WAU + 2025 營收目標,『迫使 OpenAI/Anthropic 把更多股權交給 hyperscaler 換算力』— 真正受益者是 MSFT/GOOGL",
            "Forward PE 19.6x 異常低 (歷史 28-35x),mean target $561 vs 當前 $379 隱含 upside +48% — 共識上修空間在 Mag 7 中數一數二",
        ],
        "bear_thesis": [
            "Azure OM 下滑訊號 (W19):雲服務佔比提高 + Copilot token 暴增 + Maia ASIC 進度慢 — 短期 unit token economics 比 AWS/GCP 差",
            "Sacks (W18) 直言『消費端輸給 Google Gemini (已 700M WAU)』— Copilot consumer 端被 Gemini 結構性壓制",
            "OpenAI 解除 Azure 獨家枷鎖後可進 AWS/Oracle/GCP (W19) — Azure 短期成長率受影響,微軟最強 distribution 護城河之一被自己讓出",
            "MAI-Thinking-1 取代 Claude (W24) 短期省成本但長線是雙面刃:Copilot 用戶若認知到底層換成自家模型而非 frontier model,定價權與品牌溢價可能受損",
            "Dalio (W10) 雙重警告 — 美債危機 + AI 估值泡沫並行;Chamath W11 同步警告 hyperscaler Amazon-style sev-1 隨時可能再次擴散",
            "Google 發 $847.5 億新股 (W25) 把 AI CapEx 金融化 — MSFT/AMZN 暫未跟進,意味同業已感受到現金流壓力",
        ],
        "briefing_mentions": [
            {"week": "2026-W04", "category": "微軟/OpenAI", "snippet": "Satya Nadella 親上 All-In 駁 SaaS 死亡論:Azure 是 token factory,模型像資料庫會百花齊放。MSFT 估值錨點:Azure tokens 量 + Foundry orchestrator + 本機 NPU/DGX 工作站業務"},
            {"week": "2026-W19", "category": "微軟/OpenAI", "snippet": "微軟『放開』OpenAI:失去 Azure 獨家換到 (1) OpenAI 產品優先推出權 (2) 技術授權延長至 2032 (3) 自家平台賣 OpenAI 服務不用分潤"},
            {"week": "2026-W19", "category": "AI 雲端", "snippet": "三大雲財報:Google +63.4% / AWS +28.4% / Azure +40%。Azure OM 下滑是雲服務佔比提高 + Copilot token 暴增,純 OM 估仍 35%+"},
            {"week": "2026-W22", "category": "SpaceX", "snippet": "Bill Ackman 公開看好 MSFT — 對沖基金大佬背書 MSFT 為 AI 時代核心持股"},
            {"week": "2026-W24", "category": "AI 模型", "snippet": "微軟 MAI-Thinking-1 對 Claude Sonnet 4.6 盲測勝出。M觀點:通路品牌取代供應商品牌邏輯 → GitHub Copilot / 365 Copilot 內部 Sonnet token 成本可大降"},
        ],
    },
    "GOOGL": {
        "name": "Alphabet",
        "category_label": "搜尋 + YouTube + Google Cloud + Waymo + Gemini",
        "valuation_params": {"fwd_pe_base": 22, "fwd_pe_bull": 28, "ps_base": 10, "ev_ebitda_base": 16, "dcf_disc_rate": 0.09, "dcf_fcf_growth_5y": 0.15, "dcf_terminal_growth": 0.035},
        "bull_thesis": [
            "Sacks (W05) 直接點名 Google 是『AI Agent 元年』最大贏家 — 『他們已有你所有 email/calendar/docs,而你信任他們』",
            "Gemini 已超越 ChatGPT consumer 端:Sacks (W18) 揭露 OpenAI miss 1B WAU 目標時點出『消費端輸給 Google Gemini (已 700M WAU)』",
            "Google Cloud +63.4% YoY (W19 三大雲財報) 把市場給分推到 100 — AI Cloud 進入『供給面經濟』後 Google 因 TPU 自研垂直整合反而最具成本優勢",
            "Berkshire (Greg Abel 時代) 大買 GOOGL (W25),可能成 Abel 代表作 — 巴菲特繼承人押注",
            "Google 發 $847.5 億新股把 AI CapEx 金融化 (W25):M觀點『Google 寧可稀釋股權踩油門 = 它看到的 AI 機會大到「現在減速才是最大風險」』",
            "TPU 供應鏈持續強化:股癌多次點名 Google TPU v7 為 ASIC 領域最強訊號,博通 + GUC + Marvell + Blackstone 合作外銷",
        ],
        "bear_thesis": [
            "GOOGL 發新股 (W25 $847.5 億) 兩面解讀:悲觀解讀『連 GOOGL 都缺錢 = 泡沫頂部訊號』— 過去從不發新股的科技股王首次稀釋",
            "Google 2026 CapEx 預估 $1900B vs 營業現金流 $2000B,緩衝僅 $100B (W25) — 風險集中度極高",
            "Chamath (W16) 拋『五級火警』警告 datacenter NIMBY:Maine 全面禁建 + 6B 案 town board 一夜被罷免 — GOOGL 自建 datacenter 成本暴增",
            "Google 在 Agent 工作流追趕落後 (W22):NVIDIA 財報季點出『Google 在 Agent 工作流 strike team 努力追趕』— 雖然 Gemini 在 consumer 端領先,但 enterprise agent 場景被 OpenAI/Anthropic + PLTR/MSFT 卡位",
            "Dalio (W10) 警告中國 AI 接近美國水準但『免費 + 開源 + 公用事業』模型運作 — Search 護城河面臨 binary 估值風險",
            "Forward PE 25.4x + P/S 10.6x 都在歷史高位,mean target $433 vs 當前 $368 upside 僅 17.7%",
        ],
        "briefing_mentions": [
            {"week": "2026-W05", "category": "AI 軟體", "snippet": "Sacks:這是『AI Agent 元年』— 『最大贏家是 Google (他們已有你所有 email/calendar/docs,而你信任他們)』,Cloudbot 把對手 SaaS 自家 AI 副駕變成『sandbox 玩具』"},
            {"week": "2026-W18", "category": "微軟/OpenAI", "snippet": "Sacks 揭露『Sam 會因錯誤理由賺到對的結果 — 消費端輸給 Google Gemini (已 700M WAU)』"},
            {"week": "2026-W19", "category": "AI 雲端", "snippet": "三大雲財報:Google +63.4% / AWS +28.4% / Azure +40% — Google Cloud 市場給分 100,AI Cloud 進入『供給面經濟』後 Google TPU 自研垂直整合最具成本優勢"},
            {"week": "2026-W21", "category": "股癌觀點", "snippet": "股癌:Google 與 Blackstone 合作 TPU 外銷將掀起晶片與零組件搶產能大戰。AI 算力 → 電源 (800V HVDC、PSU、DrMOS) 為下一個受惠族群"},
            {"week": "2026-W25", "category": "宏觀資金", "snippet": "Google 發 $847.5 億新股 — 最會印鈔的科技巨頭把 AI CapEx 金融化。Berkshire (Greg Abel 時代) 大買 GOOGL,可能成 Abel 代表作"},
        ],
    },
    "TSLA": {
        "name": "Tesla",
        "category_label": "EV + Robotaxi + Optimus 機器人 + Energy (馬斯克帝國)",
        "valuation_params": {"fwd_pe_base": 80, "fwd_pe_bull": 120, "ps_base": 10, "ev_ebitda_base": 30, "dcf_disc_rate": 0.11, "dcf_fcf_growth_5y": 0.25, "dcf_terminal_growth": 0.04},
        "bull_thesis": [
            "Optimus 量產時程具體化:V3 工程驗證 5 月通過,Fremont 5 月小規模試量產、7 月供應商正式量產訂單、年底前 1000-3000 台,Jason (W03 CES)『沒人會記得 Tesla 曾經做車,大家只會記得 Optimus』",
            "FSD 歐洲開花 + 全球擴張:荷蘭 RDW 4/10 首批准,立陶宛 / 愛沙尼亞 / 比利時 / 丹麥跟進(W23/W25),FSD 一次性買斷 6/30 截止改訂閱制 = 長期穩定現金流",
            "Robotaxi 規模化:Cybercab 整備重量僅 1414kg / 48kWh / 續航 673km,EPA 史上最節能 EV (W25);Robotaxi 從 Austin 擴張到 Dallas/Houston",
            "SpaceX-Tesla 合併耳語 + 帝國敘事:Chamath W02 押 99.999% Tesla+SpaceX 最終合併、W14 確認,W23 馬斯克再公開談合併『Optimus 與 FSD 都需要 SpaceX 太空算力支持』",
            "AI5/AI6 晶片自研 + Terafab:馬斯克稱 AI5 成本是 Blackwell <10%,Terafab 100M sqft 晶圓廠計畫 = Gigafactory 10x (W13),Intel 加入 Terafab",
            "Elon 鎖定持股 + 信仰結構:馬斯克 W25 行使 3.04 億股選擇權直接持股升至 19.9%;Sacks/Chamath/Friedberg 把『trillionaire 仇富敘事』反甩 Bernie/Warren",
        ],
        "bear_thesis": [
            "fwd PE 160x 是極端值:當前 $400 / fwd EPS ~$2.5 = PE 160x,接近泡沫頂部訊號 — 即使給 fwd PE 80x (已是歷史車廠 10 倍),理論價也只 ~$200",
            "mean target $421 vs 當前 $400 = 僅 +5% upside,賣方共識其實不挺:華爾街早已把 narrative 折現,任何 Optimus 跳票就是估值殺手",
            "EV 業務本體基本面承壓:Model S/X Fremont 停產 (W05)、FSD 取消買斷雖長期利多但短期銷售動能受影響",
            "Robotaxi / FSD 監管風險:歐洲 ETSC 致函要求暫停 FSD 認證 (W23 / W25),捷克拒絕互認 — 任一重大事故可能讓多年認證一夜倒退",
            "Elon key man + 政治風險:馬斯克 OpenAI 訴訟 4 週內二度敗訴 (W21);Bernie 提案沒收 AI 公司 50% 股權 (W24) 把 trillionaire 列為政治標靶",
            "P/S 15.4 vs 歷史車廠 1-2x:即使 narrative 全部兌現,從 P/S 角度看也已透支 2030 之後的營收 — Humanoid 題材太早,本田/上銀/減速機供應鏈 2026-2027 才會放量",
        ],
        "briefing_mentions": [
            {"week": "2026-W25", "category": "馬斯克", "snippet": "Sacks 走完 SpaceX IPO 最大 IPO 內幕 + Elon trillionaire 拆解 (25 年累積 paper wealth、鎖定期還有一年);SpaceX-Tesla 合併耳語延燒 → TSLA 估值結構性重評,Optimus + FSD 接 SpaceX 軌道算力"},
            {"week": "2026-W23", "category": "Tesla", "snippet": "馬斯克再度公開談 SpaceX 併購 Tesla,主因 Optimus 與 FSD 都需要 SpaceX 太空算力支持"},
            {"week": "2026-W21", "category": "馬斯克 / IPO", "snippet": "Chamath 拆 SpaceX $2T 估值:『xAI + Tesla 合併後 Elon 是唯一還能 one more thing 級驚喜的 CEO,溢價合理』。同週馬斯克 OpenAI 訴訟 4 週內第二次敗訴"},
            {"week": "2026-W20", "category": "Tesla", "snippet": "Optimus V3 通過工程驗證,5 月 Fremont 工廠轉產線:AI4→AI5 晶片升級、靈巧手 ~50 個致動器,7 月供應商正式量產訂單,年底前 1000-3000 台"},
            {"week": "2026-W14", "category": "IPO + 估值", "snippet": "Chamath 押 99.999% Tesla+SpaceX 最終會合併;SpaceX 4/1 秘密遞 S-1、目標估值 $1.75T,IPO 提供 mark-to-market 才能讓 Elon 擺脫『股東勒索稅』"},
            {"week": "2026-W03", "category": "AI 算力", "snippet": "Jason Calacanis CES:『沒人會記得 Tesla 曾經做車,大家只會記得 Optimus』,humanoid 將達 1:1 人類比例 — 受惠股 TSLA (Optimus + FSD) 被定錨成新估值基準"},
        ],
    },
    "005930.KS": {
        "name": "Samsung Electronics 三星電子",
        "category_label": "Memory / NAND / Foundry / Display (Korean cyclical semi)",
        "valuation_params": {"fwd_pe_base": 8, "fwd_pe_bull": 10, "ps_base": 4, "ev_ebitda_base": 8, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.08, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "Gavin Baker (W21) 直接點名:『memory (SK Hynix 5x / Samsung 6x / Micron 7x) 被低估』,Samsung 在三家中估值最便宜",
            "Coatue Laffont (W23 All-In Summit) 點名記憶體股:『每用戶記憶體需求隨 AI memory/context 可 5x → 重估邏輯仍未走完』",
            "DRAM 雙引擎:HBM (AI 訓練) + 一般 DRAM (SOCAMM、推論層級) 同步漲價 — Samsung 是唯一同時做 HBM、DRAM、NAND、Foundry、Display 的垂直整合廠",
            "mean target KRW 428,076 vs 當前 KRW 354,000 = +21% upside,35 個分析師覆蓋",
            "Foundry 翻身 narrative:Tesla x Intel 合作 (W16) + Terafab 故事讓美國本土晶圓供應鏈題材熱炒,Samsung Foundry 是少數能跑先進製程的選項",
            "P/S 6.0 看似貴但 mcap $1.38T 內含手機 + Foundry + Display 雜訊 — 真實記憶體業務 P/S 仍在歷史中段",
        ],
        "bear_thesis": [
            "歷史 cyclical:DRAM 每次景氣高峰後股價回吐 50-70% (2018, 2022);股癌『當 Micron 變共識交易,反而要小心』",
            "HBM 落後 Hynix 1-2 個世代:NVDA 主供仍是 SK Hynix,若 HBM4 進度不及預期 = 失去重估的核心理由",
            "Foundry 燒錢 vs TSMC 差距持續:Samsung Foundry 2nm 良率長期低於 TSMC,Tesla 選 Intel 而非 Samsung",
            "Korea retail 槓桿訊號 (W21):Chamath/Gavin Baker 警告『Korea retail 槓桿買 AI 晶片股 + 10Y 4.6% 構成派對最後階段訊號』",
            "Broadcom W24/W25 指引保守觸發 SOX -10%;Samsung beta 與 cyclical 屬性意味 SOX 大修時跟跌幅度仍高",
            "中國長存 (YMTC) NAND 突破 + 國家補貼;手機部門面臨蘋果 + 中國品牌雙重夾擊,Display 業務 OLED 給蘋果議價力下降",
        ],
        "briefing_mentions": [
            {"week": "2026-W23", "category": "IPO + 估值", "snippet": "Coatue Laffont 直接點名記憶體股 (MU / 海力士 / 三星):每用戶記憶體需求隨 AI memory/context 可 5x → 重估邏輯仍未走完"},
            {"week": "2026-W21", "category": "IPO + 估值", "snippet": "Gavin Baker:memory (SK Hynix 5x / Samsung 6x / Micron 7x) 被低估。但同週警告 Korea retail 槓桿是『派對最後階段訊號』"},
            {"week": "2025-W52", "category": "股癌觀點", "snippet": "股癌:記憶體 supercycle 持續。Micron / SK Hynix / Samsung 三家 HBM/SOCAMM 訂單能見度推到 2027"},
            {"week": "2026-W02", "category": "股癌觀點", "snippet": "股癌:NVIDIA 存儲革命 (GB200 NVL72 SOCAMM)。美光 / SK 海力士 SOCAMM2 訂單 H2 2026 起放量 (隱含 Samsung 二供跟進)"},
            {"week": "2026-W12", "category": "股癌觀點", "snippet": "股癌:記憶體共識交易過熱警訊。對 Samsung 而言,fwd PE 6x 反而是『還沒過熱』的相對防禦倉位"},
        ],
    },
    "000660.KS": {
        "name": "SK Hynix",
        "category_label": "HBM 龍頭 / DRAM (NVDA 主供應商)",
        "valuation_params": {"fwd_pe_base": 10, "fwd_pe_bull": 13, "ps_base": 6, "ev_ebitda_base": 10, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.10, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "Gavin Baker (W21 SpaceX S-1 揭密) 點名:『memory (SK Hynix 5x / Samsung 6x / Micron 7x) 被低估』— SK Hynix 是三家中 fwd PE 最低",
            "Coatue Laffont (W23 All-In Summit, $55B AUM) 點名記憶體股:『每用戶記憶體需求隨 AI memory/context 可 5x → 重估邏輯仍未走完』,SK Hynix 是 HBM 龍頭 (NVDA 主供應 ~70-80% 份額)",
            "NVDA Q1 26 $81.6B 營收 +85% YoY + Anthropic 簽 SpaceX Colossus $45B / 3 年 (W19 W21),意味 HBM 需求結構性",
            "資料中心建造週期從 122 → 91 → 66 天 (Gavin W21),『Jensen 願意把 GPU 給能最快插電的人』 — HBM 是真正瓶頸",
            "Anthropic / OpenAI / xAI ARR 倍速擴張 (W15 Brad 拆 Anthropic 2026/4 $30B run rate / 4 月衝到 $44B) → 下游 capex 倍增",
            "mcap $1.03T USD-eq、33 分析師覆蓋,與 NVDA 客戶綁定深度 + HBM 結構性溢價,EV/EBITDA 10x 在 AI super-cycle 中性偏低",
        ],
        "bear_thesis": [
            "mean target KRW 2,712,489 vs 當前 KRW 2,764,000 = -2% downside,賣方共識已『fully priced』:33 個分析師中位數模型給出空間為負",
            "客戶集中度過高:NVDA 占 HBM 出貨 70-80%,任何 NVDA capex 放緩 (W25 Broadcom 指引保守 → SOX -10%) 直接砸 SK Hynix EPS",
            "Korea retail 槓桿訊號 (W21):Chamath 警告『Korea retail 槓桿買 AI 晶片股 + 10Y 4.6% + 30Y 5.2% 構成派對最後階段訊號』— SK Hynix 是韓國散戶最大持倉之一",
            "歷史 cyclical:DRAM 每次景氣高峰後股價回吐 50-70%;P/S 14.9 vs 歷史 4-7x 已 fully priced",
            "Broadcom W24/W25 指引保守觸發 SOX -10%,M報觀點『漲多的 Micron / Credo / Coherent (一年 3-5x) 可能修 20-30%』",
            "三星 HBM4 + 中國長存追趕:Samsung HBM3E/HBM4 良率追上即直接侵蝕 SK Hynix 二供份額;Korean memory 股是 AI 多殺多時跌得最深的板塊",
        ],
        "briefing_mentions": [
            {"week": "2026-W21", "category": "IPO + 估值", "snippet": "Gavin Baker:資料中心建造週期從 122 → 91 → 66 天,Jensen 願意把 GPU 給能最快插電的人。memory (SK Hynix 5x / Samsung 6x / Micron 7x) 被低估"},
            {"week": "2026-W23", "category": "IPO + 估值", "snippet": "Coatue Laffont ($55B AUM):每用戶記憶體需求隨 AI memory/context 可 5x → 重估邏輯仍未走完"},
            {"week": "2026-W19", "category": "AI 算力", "snippet": "Elon 把 Colossus 1 全部租給 Anthropic (220K GPU / 300MW),Anthropic Q1 ARR 從 $10B → $30B,4 月衝 $44B — HBM 直接受惠每一波 frontier compute 擴張"},
            {"week": "2025-W52", "category": "股癌觀點", "snippet": "股癌:記憶體 supercycle 持續。Micron / SK Hynix / Samsung 三家 HBM/SOCAMM 訂單能見度推到 2027"},
            {"week": "2026-W02", "category": "股癌觀點", "snippet": "股癌:NVIDIA 存儲革命 (GB200 NVL72 SOCAMM)。美光 / SK 海力士 SOCAMM2 訂單 H2 2026 起放量"},
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

    # 7. upgrades_downgrades (最近 analyst actions + 全歷史用於 by-grade 分桶)
    try:
        ud = tk.upgrades_downgrades
        if ud is not None and not ud.empty:
            ud_desc = ud.sort_index(ascending=False).reset_index()
            # all: 給 build_analysts_by_grade 算每位 firm 最新評等
            raw["upgrades_downgrades_all"] = ud_desc.to_dict("records")
            # top 8: 給 build_recent_actions 顯示最近行動
            raw["upgrades_downgrades"] = ud_desc.head(8).to_dict("records")
        else:
            raw["upgrades_downgrades"] = []
            raw["upgrades_downgrades_all"] = []
    except Exception as e:
        print(f"  ⚠️  upgrades_downgrades fail: {e}", file=sys.stderr)
        raw["upgrades_downgrades"] = []
        raw["upgrades_downgrades_all"] = []

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
    """根據既有 forecast + ticker_config 參數計算 6 個估值模型。

    幣值注意:
    - eps / mean_target 用 stock currency (info["currency"])
    - fcf / revenue / mcap / EV 用 financial currency (info["financialCurrency"])
    - 大多時候兩者相同;TSM ADR 例外 (stock=USD, fin=TWD) — 此情況跳過
      EV/EBITDA + DCF (避免幣值混算),只保留 PE + P/S + Analyst Target
    """
    info = raw["info"]
    fy0 = next((f for f in forecasts if f["period_key"] == "0y"), {})
    fy1 = next((f for f in forecasts if f["period_key"] == "+1y"), {})
    shares = safe_float(info.get("sharesOutstanding"))
    mcap = safe_float(info.get("marketCap"))
    ev = safe_float(info.get("enterpriseValue"))
    ebitda_margin = safe_float(info.get("ebitdaMargins")) or 0.4  # fallback

    stock_ccy = str(info.get("currency", "") or "")
    fin_ccy = str(info.get("financialCurrency", "") or "")
    ccy_mismatch = stock_ccy and fin_ccy and stock_ccy != fin_ccy

    models = []

    # 1. Base PE × FY current EPS (EPS 是 stock currency,安全)
    eps0 = fy0.get("eps_avg")
    if eps0:
        p = eps0 * params["fwd_pe_base"]
        models.append({
            "model": f"PE × FY 當期 EPS ({params['fwd_pe_base']}x)",
            "implied_price": round(p, 2),
            "rationale": f"歷史中段 fwd P/E {params['fwd_pe_base']}x × FY 當期 EPS {eps0}",
        })

    # 2. Bull PE × FY +1y EPS
    eps1 = fy1.get("eps_avg")
    if eps1:
        p = eps1 * params["fwd_pe_bull"]
        models.append({
            "model": f"PE × FY +1y EPS ({params['fwd_pe_bull']}x bull)",
            "implied_price": round(p, 2),
            "rationale": f"FY+1 EPS {eps1} 維持 {params['fwd_pe_bull']}x P/E",
        })

    # 3. P/S × FY current Revenue (rev_avg_b 是 financial currency,shares 是股數通用 → rev_per_share 在 fin_ccy)
    rev0 = fy0.get("rev_avg_b")
    if rev0 and shares and not ccy_mismatch:
        rev_per_share = rev0 * 1e9 / shares
        p = rev_per_share * params["ps_base"]
        models.append({
            "model": f"P/S × FY 當期 Rev ({params['ps_base']}x)",
            "implied_price": round(p, 2),
            "rationale": f"歷史中段 P/S {params['ps_base']}x × FY 當期 {rev0}B 營收",
        })

    # 4. EV/EBITDA (純 financial currency → 不能跟 stock price 比較)
    if rev0 and shares and ev and mcap and not ccy_mismatch:
        ebitda = rev0 * 1e9 * ebitda_margin
        target_ev = ebitda * params["ev_ebitda_base"]
        net_debt = ev - mcap
        target_mcap = target_ev - net_debt
        p = target_mcap / shares
        models.append({
            "model": f"EV/EBITDA × FY 當期 ({params['ev_ebitda_base']}x)",
            "implied_price": round(p, 2),
            "rationale": f"歷史 EV/EBITDA {params['ev_ebitda_base']}x,EBITDA = margin {ebitda_margin*100:.0f}% × FY 當期 Rev",
        })

    # 5. DCF (純 financial currency)
    fcf_ttm = safe_float(info.get("freeCashflow"))
    fcf_base = None
    if eps0 and shares and not ccy_mismatch:
        # FY current NI × 80% FCF conversion
        forward_ni = eps0 * shares
        fcf_base = forward_ni * 0.80
        fcf_source = f"FY 當期 NI (EPS {eps0} × {shares/1e9:.2f}B 股) × 80% FCF conversion"
    elif fcf_ttm and not ccy_mismatch:
        fcf_base = fcf_ttm
        fcf_source = f"TTM FCF {fcf_ttm/1e9:.1f}B"

    if fcf_base and shares and not ccy_mismatch:
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
            "rationale": f"基準 FCF {fcf_base/1e9:.1f}B (= {fcf_source})",
        })

    # 6. Analyst Mean Target (stock currency,安全)
    if mean_target:
        models.append({
            "model": "Analyst Mean Target",
            "implied_price": round(mean_target, 2),
            "rationale": f"yfinance 共識:{raw['price_targets'].get('mean')}",
        })

    # 若跨幣值,加說明
    if ccy_mismatch:
        models.append({
            "model": f"⚠️ 跨幣值 ({stock_ccy} stock / {fin_ccy} financials)",
            "implied_price": 0,
            "rationale": f"P/S / EV/EBITDA / DCF 因股價 ({stock_ccy}) 與財報 ({fin_ccy}) 幣值不同已跳過。請參考相同基本面的同公司本國股 (如 2330.TW for TSM ADR) 之 P/S/EV/EBITDA/DCF 模型。",
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


def build_analysts_by_grade(raw: dict, mean_target: float | None = None) -> dict:
    """從 upgrades_downgrades 推每位 firm 最新評等,按桶分組。
    PT < mean × 0.3 視為 stale (yfinance split 未調整),仍納入但標記。"""
    GRADE_MAP = {
        "Strong Buy": "strongBuy",
        "Buy": "buy", "Outperform": "buy", "Overweight": "buy", "Positive": "buy",
        "Hold": "hold", "Neutral": "hold", "Market Perform": "hold",
        "Equal-Weight": "hold", "Sector Perform": "hold", "Mixed": "hold",
        "Sell": "sell", "Underperform": "sell", "Underweight": "sell", "Negative": "sell",
        "Strong Sell": "strongSell",
    }
    stale_threshold = (mean_target * 0.3) if mean_target else 0

    # Map firm -> latest record (yfinance 已 desc 排序,只記第一次見到的)
    latest_by_firm = {}
    for r in raw.get("upgrades_downgrades_all", raw["upgrades_downgrades"]):
        firm = str(r.get("Firm", "")).strip()
        if not firm or firm == "—":
            continue
        if firm in latest_by_firm:
            continue
        cur_pt = safe_float(r.get("currentPriceTarget"))
        prior_pt = safe_float(r.get("priorPriceTarget"))
        pt = cur_pt if cur_pt else prior_pt
        is_stale = bool(stale_threshold and pt and pt < stale_threshold)
        gd = r.get("GradeDate") or r.get("index")
        ds = gd.strftime("%Y-%m-%d") if hasattr(gd, "strftime") else str(gd)[:10]
        latest_by_firm[firm] = {
            "firm": firm,
            "date": ds,
            "grade": str(r.get("ToGrade", "")),
            "pt": pt,
            "stale": is_stale,
        }

    # 按桶分組
    buckets = {"strongBuy": [], "buy": [], "hold": [], "sell": [], "strongSell": []}
    for firm, rec in latest_by_firm.items():
        bucket = GRADE_MAP.get(rec["grade"], "hold")
        buckets[bucket].append(rec)
    # 按 PT 排序 (高 → 低),stale 的排最後
    for k in buckets:
        buckets[k].sort(key=lambda x: (x["stale"], -(x["pt"] or 0)))
    return buckets


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
        # yfinance 新欄位名 currentPriceTarget (舊版 priceTarget 已不填)
        new_pt = safe_float(r.get("currentPriceTarget") or r.get("priceTarget"))
        pt_action = str(r.get("priceTargetAction", "") or "")
        # 過濾 split 未調整的 stale PT (兩端都低於 mean × 0.5)
        if threshold and old_pt and old_pt < threshold and (not new_pt or new_pt < threshold):
            continue
        # action label: 優先用 priceTargetAction (Raises/Lowers/Maintains/Initiates)
        action_label = pt_action if pt_action else str(r.get("Action", "—"))
        out.append({
            "date": ds,
            "firm": str(r.get("Firm", "—")),
            "action": action_label,
            "pt_action": pt_action,  # 顯式保留供 UI 上色
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
    analysts_by_grade = build_analysts_by_grade(raw, mean_target)

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
        "currency": str(info.get("currency", "USD")),
        "financial_currency": str(info.get("financialCurrency", "USD")),
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
        "analysts_by_grade": analysts_by_grade,
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
