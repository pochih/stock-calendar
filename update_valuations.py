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
    "AMD": {
        "name": "Advanced Micro Devices",
        "category_label": "AI GPU 二供 (Instinct MI400) + 資料中心 CPU (EPYC) + 客戶端 (Ryzen)",
        "valuation_params": {"fwd_pe_base": 22, "fwd_pe_bull": 30, "ps_base": 8, "ev_ebitda_base": 18, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.25, "dcf_terminal_growth": 0.035},
        "bull_thesis": [
            "OpenAI 6GW MI400/MI500 大單 + 認股權至 10% 股份 (股癌 EP599 2025-W41):AMD 第一次拿到 hyperscaler tier-1 真實訂單,2026 起 ramp",
            "Lisa Su 親上 All-In『Winning the AI Race Part 3』(2025-07,與 Jensen 並列):強調 open ecosystem,Chamath (W24) 點名 Trump 已收 Intel/MP/AMD/SPCX 戰略持股組合",
            "Agentic AI Q1 推升 server CPU 需求 (M觀點 W18):GPU:CPU 從 1:4 走向 1:1,EPYC 缺貨『售完只能買 Xeon 6』",
            "Brad Gerstner W15 拆 Anthropic ARR $30B → $44B + Sacks W19 Anthropic Colossus $45B/3 年 → AI 算力鏈受惠;Bernstein 估 2026-2028 ASIC + 替代 GPU 滲透 15%→30%",
            "ZT Systems 整合 + rack-scale 系統能力補強:Jason W12 直球問 Jensen『AMD $250-300 億只是 NVDA $500 億的一半』,Jensen 答 token 單位成本不同 — 默認 AMD 已是合格替代",
            "Build 2026 (W02) AVGO/AMD/INTC 列名 MRC 開放網路協議共同開發者:AMD 在 hyperscaler 自研網路堆疊路線拿到結構性卡位",
        ],
        "bear_thesis": [
            "Jensen W12 親自回擊:CUDA + Dynamo + 整廠 token economics 是 AMD ROCm 短期難跨越的軟體護城河",
            "fwd PE ~41x vs NVDA 低 teens (Gavin Baker W21):AMD 估值已 fully priced,殺估值幅度遠大於 NVDA",
            "Vendor financing 風險 (股癌 EP599):『連 Microsoft 都很難推動 ROCm 取代 CUDA,何況 OpenAI 這種正在賠錢的公司?』",
            "股癌 W23 點 Google + Blackstone TPU 外銷:AMD 卡在『GPU 龍頭 vs ASIC 客製化』中間定位最尷尬",
            "Chamath W47 2025『risk-off + capex digestion』NVDA/MSFT/ORCL/AVGO 同週跌 6-20%,AMD beta 同步",
            "Mean target $483 vs 當前 $537 = -10% downside (n=48):賣方共識已 fully priced",
        ],
        "briefing_mentions": [
            {"week": "2025-W41", "category": "股癌觀點", "snippet": "股癌 EP599:OpenAI 與 AMD 大單合作 — MI400/MI500 拿到 OpenAI 訂單 6GW + 認股權 up to 10% 股份。但 vendor financing 已是吹泡泡開始"},
            {"week": "2026-W12", "category": "AI 硬體", "snippet": "Jensen 親上 All-In:Vera Rubin Inference Factory $500 億 vs ASIC/AMD $250-300 億。Chamath 讓 Jensen 確認 Vera Rubin 25% 留給 Groq LPU/GPU 混合"},
            {"week": "2026-W18", "category": "Intel 復活", "snippet": "Intel 財報暴擊 +123% YTD,Agentic AI 讓 CPU 需求暴增,AMD EPYC 售完只能買 Xeon 6"},
            {"week": "2026-W19", "category": "股癌觀點", "snippet": "股癌 EP659:AMD 上修 server CPU TAM、Agent AI 帶動 CPU/GPU 比從 1:4 走向 1:1"},
            {"week": "2026-W24", "category": "AI 鬼故事", "snippet": "Chamath 揭露 Trump 已收 Intel/MP/AMD/SPCX 戰略持股組合;Bernie 提案沒收 AI 公司 50% 股權"},
        ],
    },
    "ORCL": {
        "name": "Oracle",
        "category_label": "雲端 OCI + AI infrastructure (Stargate $500B 主合作方) + 企業資料庫",
        "valuation_params": {"fwd_pe_base": 22, "fwd_pe_bull": 28, "ps_base": 8, "ev_ebitda_base": 16, "dcf_disc_rate": 0.09, "dcf_fcf_growth_5y": 0.20, "dcf_terminal_growth": 0.035},
        "bull_thesis": [
            "Stargate $500B AI 基建主要合作方:Chamath『18 個月前大家還在笑,謝天謝地美國跑這麼快』— Stargate + Oracle 是國家 AI 戰略核心",
            "微軟『放開』OpenAI (W19):OpenAI 解除 Azure 獨家後可進 AWS/Oracle/GCP — Oracle 成為 OpenAI 第二大算力供應商,RPO 跳升至 $480B+,OCI 共識成長率 >85%",
            "Chamath 隱含 trillionaire 路徑 (W25):Elon 之後是 Jensen Huang + Larry Ellison;Oracle 直接列入 trillionaire-maker 名單",
            "Sacks (W47 2025) 把 ORCL 與 NVDA/MSFT/AVGO 並列『有錢可花、需要花錢』四家公司:中長線 Oracle 是 hyperscaler 算力短缺最直接受惠者",
            "Oracle 拿到 $300B+ 級 RPO 是『實際採購承諾』,比 NVDA-CoreWeave round-tripping 結構更實",
            "fwd PE ~17x vs MSFT 19.6x / GOOGL 25.4x:Oracle 是 hyperscaler 群組中估值最低、ratio 重估空間最大的選項",
        ],
        "bear_thesis": [
            "FCF TTM -$20.3B:為衝 Stargate / OCI 大幅燒錢,若 OpenAI 違約或減量,$480B+ RPO 含金量瞬間打對折",
            "客戶集中度極端風險:大量 RPO 集中在 OpenAI + Anthropic 等少數 frontier labs,2025-W47 OpenAI CFO 言論引爆 MSFT/NVDA/ORCL/AVGO 同跌 6-20%",
            "Chamath W47 2025『risk-off + capex digestion』直接點名;DeepSeek-R1 2025/1/27 ORCL 隨 NVDA -17% 暴跌",
            "Vendor financing / round-tripping 升級 (股癌 EP599):『Oracle 跟大家的一些合作其實都是已經在吹泡泡了』",
            "Bernie 提案沒收 AI 公司 50% 股權 (W24) + Trump 戰略持股組合:Oracle 是『戰略物資國家持股』邏輯下次要候選",
            "fwd PE 17x 看似便宜但前提是 OCI 50%+ 成長率成真 + RPO 順利轉收入;若 datacenter NIMBY 擴散導致 capex 砍量,Oracle 沒有 SaaS/廣告緩衝",
        ],
        "briefing_mentions": [
            {"week": "2026-W04", "category": "微軟/OpenAI", "snippet": "Satya Nadella 親上 All-In Davos:Azure 是 token factory,模型像資料庫會百花齊放。為 W19 微軟『放開』OpenAI 鋪路"},
            {"week": "2026-W19", "category": "微軟/OpenAI", "snippet": "微軟『放開』OpenAI:真正受益者是 Oracle/AMZN/META/MSFT/GOOGL + Elon (EWS)"},
            {"week": "2026-W23", "category": "AI 軟體", "snippet": "All-In Summit Coatue Laffont $4T AI IPO 浪潮;PLTR Alpha / AI Lab Beta / MSFT 企業關係 / Oracle 算力 — 市場大到多家共贏"},
            {"week": "2026-W25", "category": "馬斯克", "snippet": "Chamath 隱含 trillionaire 路徑:Elon 之後最可能是 Jensen Huang(NVDA)+ Larry Ellison(Oracle)"},
            {"week": "2025-W47", "category": "AI 鬼故事", "snippet": "OpenAI Bailout 集:Chamath『Stargate 18 個月前大家還在笑』。但同週 MSFT/NVDA/ORCL/AVGO 同跌 6-20%"},
        ],
    },
    "INTC": {
        "name": "Intel",
        "category_label": "x86 CPU + Foundry (18A / EMIB 後段封裝) + AI 加速器 (Gaudi)",
        "valuation_params": {"fwd_pe_base": 18, "fwd_pe_bull": 25, "ps_base": 4, "ev_ebitda_base": 12, "dcf_disc_rate": 0.11, "dcf_fcf_growth_5y": 0.15, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "Intel 財報暴擊 +23.6% / YTD +123% (W18):Non-GAAP EPS $0.29 vs 預期 $0.01-0.02 高出 10x+。M觀點『Pat Gelsinger 種樹陳立武乘涼』",
            "蘋果下單 Intel 18A 翻身點 (W20):蘋果 MacBook Neo A21 初步協議;Intel Foundry 從『不可能』走到『第二選項』,當天 TSM ADR 僅 -0.6%",
            "EMIB 後段封裝良率 90% 突破 (股癌 EP657 W18):聯發科 + Google + 微軟 Maia 後續代數均使用 EMIB,Intel 等於『非常專業的後段封裝廠』",
            "Tesla x Intel 合作 + Terafab 計畫 (W15/W16):Intel 正式加入 Terafab 100M sqft 晶圓廠,Tesla AI5 進入製造階段",
            "Trump 政府 10% 持股 + NVDA $5B 入股 ($23.28/股,4%) — 2025 Q4 起爆漲關鍵起點,2026 W18 +123% YTD 印證",
            "Agentic AI 推升 CPU 需求 (M觀點 W18):GPU:CPU 從 1:4 走向 1:1,Intel Xeon 6 缺貨;2028 Coral Rapids 才真正補產品力",
        ],
        "bear_thesis": [
            "fwd PE ~87x (重組期失真):FCF TTM -$8.3B、毛利率 37.2% vs AMD 53.1% / TSM 58%+;mean target $89 vs 當前 $134 = -33% downside",
            "股癌定調『重組故事 / Foundry 燒錢』(EP613):『Intel 短期 (一兩年) 18A 放量或賺大錢都很困難』,缺貨紅利非結構性領先",
            "Substrate 載板良率僅 30-40% (股癌 EP657):完整 chip-to-system 良率受最弱環節壓制,『90% 良率比台積電還是蠻差的』",
            "Coral Rapids 要等到 2028 才補產品力:2026/2027 只是缺貨紅利,期間若 hyperscaler 砍 capex,Intel 紅利第一個消失",
            "客戶集中度 + 政府入股雙風險:Trump 10% 持股 passive 但長線可能變『戰略物資國家持股』樣板,商業彈性受限",
            "Chamath/Sacks W47 2025『risk-off + capex digestion』時 SOX -10%,Intel 是跌幅最深的標的之一",
        ],
        "briefing_mentions": [
            {"week": "2025-W38", "category": "股癌觀點", "snippet": "股癌 EP593:NVIDIA 入股 Intel ($5B,$23.28/股 4%) — Foundry 合作但 Intel 仍獨立。2025 Q4 起爆漲關鍵起點"},
            {"week": "2026-W18", "category": "Intel 復活", "snippet": "Intel 財報暴擊 +123% YTD,Non-GAAP EPS 高出預期 10x+。M觀點:Pat Gelsinger 種樹陳立武乘涼,Intel Foundry 長線重要性可能超過 Product"},
            {"week": "2026-W20", "category": "宏觀市場", "snippet": "M觀點:蘋果下單 Intel 18A 當天 TSM ADR 僅 -0.6%。Intel Foundry 從『不可能』走到『第二選項』"},
            {"week": "2026-W16", "category": "AI 模型", "snippet": "Anthropic Mythos + Tesla x Intel 合作傳聞;Tesla AI5 進入製造階段。美國本土先進製程供應鏈降低台積電過度集中風險"},
            {"week": "2026-W15", "category": "IPO + 估值", "snippet": "Intel 加入 Tesla/SpaceX Terafab (100M sqft 晶圓廠,Gigafactory 10x);強化美國本土晶圓供應鏈"},
        ],
    },
    "NFLX": {
        "name": "Netflix",
        "category_label": "全球串流龍頭 + 廣告層 + 直播 / Live Sports (內容 IP 變現)",
        "valuation_params": {"fwd_pe_base": 28, "fwd_pe_bull": 35, "ps_base": 8, "ev_ebitda_base": 20, "dcf_disc_rate": 0.09, "dcf_fcf_growth_5y": 0.15, "dcf_terminal_growth": 0.035},
        "bull_thesis": [
            "廣告層 + 直播 / Live Sports 兩條第二曲線同步點火:Q2 26 共識營收 $12.58B、YoY +14%,廣告 ARPU 內生定價權確立",
            "AI 製作內容降本邏輯:VFX / 翻譯 / 預告剪輯成本下殺,Netflix 為唯一垂直整合內容廠『內容支出 vs Op Margin 雙升』玩家;FCF TTM $26B、毛利率 49%",
            "Tucker Carlson @ All-In (W50 2025) Paramount vs Netflix WBD 競購事件揭露 Netflix $830 億 streaming-only 出價已被 WBD 接受",
            "股癌 EP620 (W51 2025) 點 Netflix 為『破壞式創新成功範本』;EP647 (W12)『AI 影片生成限制論』— 院線片/Netflix 級大製作很難被 AI 顛覆",
            "mean target $115 (n=44) vs 當前 $77.38 隱含 +49% upside — 跌深後估值具吸引力",
            "FCF $26B/年支撐每季 buyback,fwd PE 20x 已 priced in 訂閱成長放緩擔憂",
        ],
        "bear_thesis": [
            "訂閱戶成長見頂風險:2022 W17 (4/22) 訂閱戶 11 年首次下滑 -35% / -$50B mcap 教訓猶在",
            "內容支出黑洞:年度內容預算 $17B+,Live Sports + WBD 競購推升成本通膨,廣告 ARPU 增量未必能 cover",
            "Paramount-WBD 合併若成局 (Polymarket W50 2025 51% 機率):整合 CBS+CNN+TNT+HBO+DC 成 streaming 巨獸,Netflix 議價力面臨衝擊",
            "AI 製作降本是雙面刃 (股癌 EP647 W12):AI Slop 氾濫,Sora 廉價短影音稀釋『黃金時段』注意力",
            "fwd PE ~20x 高於傳統媒體 (DIS/WBD ~2-3x);若廣告層 miss + 訂閱淨增轉負,估值打回 fwd PE 12-15x = $50 區間",
            "Apple TV+ / Amazon Prime Video 燒錢沒結束;Anthropic Fable / Sora 2 達電影級品質後,『內容廠 vs AI 模型廠』邊界模糊化",
        ],
        "briefing_mentions": [
            {"week": "2025-W50", "category": "併購", "snippet": "Tucker Carlson @ All-In:Paramount-Skydance 對 WBD $108B 全現金敵意收購,vs Netflix 已被接受的 $83B streaming-only 出價"},
            {"week": "2026-W12", "category": "股癌觀點", "snippet": "股癌 EP647:AI 生成影片要顛覆院線片 / Netflix 級大製作極困難 — 觀眾追的是『口碑系統』"},
            {"week": "2025-W51", "category": "股癌觀點", "snippet": "股癌 EP620:Netflix 是『破壞式創新對既有企業致命衝擊』經典範本"},
            {"week": "2026-W17", "category": "財報", "snippet": "NFLX Q1 26:廣告層 + 直播 (NFL/WWE) 動能延續;市場對成長放緩敏感度極高 (2022 W17 滅頂事件對照)"},
            {"week": "2026-W25", "category": "AI 模型", "snippet": "Anthropic Fable 5 + Sora/Veo 進度加快 — Netflix 既受惠 AI 製作降本,又面臨 AI Slop 稀釋注意力雙重壓力"},
        ],
    },
    "PLTR": {
        "name": "Palantir Technologies",
        "category_label": "AI 軟體 / 平台 (Foundry + AIP,政府 + 商業雙引擎,純度最高的純 AI 股)",
        "valuation_params": {"fwd_pe_base": 80, "fwd_pe_bull": 120, "ps_base": 40, "ev_ebitda_base": 80, "dcf_disc_rate": 0.11, "dcf_fcf_growth_5y": 0.30, "dcf_terminal_growth": 0.04},
        "bull_thesis": [
            "PLTR Q1 26 財報 (W20):美國商業 +133% (扣轉移 +143%)、美國政府 +84%、NRR 150%、Rule of 40 達 145 — SaaS 史上同等量級最強",
            "M觀點 (W21/W23) 拆 PLTR 五大護城河:軟體平台 + 模型中立性 + Ontology + 責任鏈 + 文化 相乘難複製;Foundry/AIP 是真正的 AI Harness",
            "Alex Karp 親上 All-In (2025-09 + W22 2026);Chamath 直接點名 PLTR『duration + durability of cash flows 比其他 SaaS 長很多』",
            "Modern War 圓桌 (W15 2026):Palantir & Anduril 高層同框 — PLTR 政府 +84% 在 Tier-1 軍工 IT stack 已是默認標準",
            "股癌 EP659 (W19) 點 PLTR 財報 'No AI Slop Zone':FDE 模式是企業 AI 真正可規責性的關鍵",
            "股癌 EP665 (W22):未來 AI 佈署關鍵在『業務能力、商務能力、可規責性』— PLTR + Anthropic FDE 模式被進一步驗證",
        ],
        "bear_thesis": [
            "Burry (W47 2025) NVDA + PLTR 同框放空:PLTR forward P/S 137x vs Datadog/Snowflake/MSFT 13-25x 為極端值,$480B 市值對 $3.5B run rate 是『house of cards』",
            "OpenAI/Anthropic + 四大顧問 + Blackstone/Goldman 組 Deployment Company (W20/W23) 搶 PLTR 高階企業 AI 導入市場",
            "fwd PE 80-120x、P/S 40x 是 SaaS 歷史極端值;30d -6.26% 反映市場焦慮,任一季 NRR 降破 130% 即啟動估值殺",
            "Chamath W21 + Bernie W24 提案沒收 AI 公司 50% 股權:PLTR 高比例美政府合約 + Karp 公開挺政府 immigration enforcement,是左翼政治反撲首要標靶",
            "M觀點 (W20/W21) 增速 84.7% YoY 已是高峰,未來 12-24 個月 NRR + USCom +133% 都難線性外推",
            "Cathie Wood ARKK 持續減持 PLTR;股價對 Karp media 出鏡頻率高度敏感",
        ],
        "briefing_mentions": [
            {"week": "2026-W20", "category": "AI 軟體", "snippet": "PLTR 財報年增 84.7% Rule of 40 達 145:美國商業 +133%、美國政府 +84%、NRR 150%。OpenAI 與四大顧問 + Anthropic 與 Blackstone/Goldman 組 Deployment Company 搶 PLTR 高階市場"},
            {"week": "2026-W23", "category": "AI 軟體", "snippet": "M觀點:PLTR 五大護城河相乘難複製。OpenAI/Anthropic + 私募基金組 Deployment Company,但只能做 Beta 版,PLTR 走 Alpha 路線"},
            {"week": "2026-W21", "category": "AI 軟體", "snippet": "M觀點:模型只是聊天框沒價值,真正創造生產力的是 Harness。PLTR 兩年來把這件事做到最好"},
            {"week": "2026-W19", "category": "股癌觀點", "snippet": "股癌 EP659:PLTR 財報『No AI Slop Zone』。FDE 模式扮演 Garbage In Garbage Out 把關角色"},
            {"week": "2025-W47", "category": "AI 鬼故事", "snippet": "Burry Scion 13F 揭露對 PLTR + NVDA put 部位。主打 hyperscaler GPU 折舊年限造假 + PLTR 137x P/S 為『house of cards』"},
        ],
    },
    "DELL": {
        "name": "Dell Technologies",
        "category_label": "AI Server ODM (ISG 含 PowerEdge + Storage) + PC (CSG) 雙引擎美系龍頭",
        "valuation_params": {"fwd_pe_base": 15, "fwd_pe_bull": 22, "ps_base": 2, "ev_ebitda_base": 12, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.18, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "Michael Dell 親上 All-In (W12 Austin Live):Dell AI Factory 已部署到 4,000+ 家企業,『需求遠大於供給,不只 hyperscaler + CSP、4,000 家 Fortune 100 + sovereign AI 都在買』",
            "ISG 占營收 ~40% 為 AI server 純度引擎:Q2 27 共識 EPS $4.88、營收 $44.38B、YoY +49%;Tier-1 客戶含 xAI Memphis Colossus / Meta",
            "NVDA 鏈最直接美系受惠股:Jensen W12 Vera Rubin + Blackwell/Rubin 訂單能見度到 2027 — Dell 是 NVDA reference design + SuperPOD 最大 OEM",
            "Travis Kalanick W12 同場 Physical AI 題材延伸:Dell 為 robotaxi / Optimus 落地後的『機器人邊緣推論伺服器』候選",
            "股價 30d +77.83% 暴衝;fwd PE ~19x 仍遠低於 NVDA/AVGO/CRWV",
            "股癌 EP666 (W22):『老 AI 股全部跑回來』,Dell 成績開得很好,ODM/EMS 估值修復進入第二段",
        ],
        "bear_thesis": [
            "歷史 OEM 利潤率結構性低:gross margin 19.2% vs 軟體股 80%+,Dell 是 dollar pass-through 模式",
            "客戶集中度 + 議價力倒掛:xAI/Meta 訂單可隨時 shift 到 SMCI/HPE/Lenovo/鴻海;HPE Juniper 整合完成後追趕 ISG 份額",
            "Burry 系空頭敘事:hyperscaler GPU 折舊 4→6 年人為墊高 EPS — Dell ISG 訂單能見度可能被質疑為循環性 over-ordering",
            "Broadcom W24/W25 指引保守觸發 SOX -10% (Dell 同期 -10% 補跌);AI server 一旦進入庫存調整,fwd PE 22x bull 打回 12-15x = $250-280",
            "Chamath W21『America Turns on AI』+ Bernie W24:Dell 作為 hyperscaler capex 主要受惠者間接承受『AI capex 政治反撲』壓力",
            "PC (CSG) 業務承壓 + AI PC 滲透緩慢:CSG 占營收 ~50% 為低成長低毛利包袱",
        ],
        "briefing_mentions": [
            {"week": "2026-W12", "category": "AI 硬體", "snippet": "Michael Dell 親上 All-In (Austin Live):Dell AI Factory 部署 4,000+ 企業,需求遠大於供給。Travis Kalanick 同場拆 Physical AI 三層 stack"},
            {"week": "2026-W22", "category": "股癌觀點", "snippet": "股癌 EP666:『老 AI 股全部跑回來』,Dell 成績好。ODM/EMS + 美系 OEM/ODM 同步走強,Server 估值修復進入第二段"},
            {"week": "2026-W12", "category": "AI 硬體", "snippet": "Jensen 親上 All-In:NVDA 訂單能見度直接轉成 Dell ISG +49% YoY 共識,Tier-1 hyperscaler 訂單能見度到 2027"},
            {"week": "2026-W24", "category": "市場修正", "snippet": "Broadcom 指引保守 → SOX 單日 -10%。Dell -10%, ANET -8%, NVDA -6% 同步補跌"},
            {"week": "2026-W18", "category": "股癌觀點", "snippet": "股癌 EP657:Meta 採用 AWS Graviton5,server CPU 需求仍熱。Dell ISG 直接受惠 Agent AI 推升 CPU 需求"},
        ],
    },
    "MRVL": {
        "name": "Marvell Technology",
        "category_label": "客製 ASIC (AWS Trainium) + 光通訊 DSP / PAM4 + Networking IP",
        "valuation_params": {"fwd_pe_base": 20, "fwd_pe_bull": 28, "ps_base": 12, "ev_ebitda_base": 18, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.25, "dcf_terminal_growth": 0.035},
        "bull_thesis": [
            "NVDA 主動入股 Marvell (股癌 W14 EP649):光通訊 1.6T / CPO 戰略卡位訊號;埋下後續 5 月 +94% / 6 月成交量爆量榜第二的伏筆",
            "AWS Trainium 2/3 主設計夥伴:hyperscaler ASIC 雙龍頭之一 (AVGO 拿 Google TPU/Meta MTIA;MRVL 拿 AWS Trainium)",
            "Computex 2026 W22 股癌 EP667:Marvell 在光通訊噴發,光與銅線並行發展,Marvell + NVDA 為直接受惠者",
            "Jensen W12 確認 Vera Rubin 25% 留給 Groq LPU/GPU 混合 — 默認 ASIC 會吃 inference 份額",
            "GTC 2026 W11 keynote 主題股 (NVDA/AMD/AVGO/TSM/MRVL 同框);Marvell 為 NVDA 軟硬整合平台 inference-tier 重要合作夥伴",
            "FY27 EPS 共識上修空間大:當前 fwd PE ~50x 看似貴但 ASIC + 光通訊 DSP 雙引擎放量;mcap $221B + FCF $2.3B + 毛利率 51.5%",
        ],
        "bear_thesis": [
            "客戶集中度極高:AWS Trainium 占 ASIC 業務大部分,任一 hyperscaler capex 放緩 (AVGO W24 SOX -10% 為預演) 直接砸 EPS",
            "光通訊『題材初升段已過』(股癌 EP641 W23 2025):進入個股分化階段,雜魚會被淘汰,與 Coherent/Lumentum/Credo 同步暴跌風險高",
            "fwd PE ~50x 在 deep cyclical 板塊極端值:若 AWS Trainium 4/5 客戶內製化 (類似 Google TPU 路徑),Marvell 設計服務角色可能 2027-28 被吃掉",
            "AVGO 仍是 hyperscaler 自研 ASIC 唯一全方案供應商;『二哥估值貼一哥』本身就有 de-rating 風險",
            "DeepSeek-R1 + Broadcom W24 兩次暴跌中,Marvell 同步跟跌 (beta 與 AVGO 同步);Chamath W47 2025『risk-off + capex digestion』適用",
            "P/S 結構性貴:即使 FY27 共識成真,Burry 對『hyperscaler 攤提造假』論述可外溢到 ASIC 設計鏈",
        ],
        "briefing_mentions": [
            {"week": "2026-W14", "category": "股癌觀點", "snippet": "股癌 EP649-#650:NVIDIA 投資 Marvell 是光通訊 1.6T/CPO 戰略卡位訊號 — 已埋下後續 5 月 +94% 漲幅伏筆"},
            {"week": "2026-W22", "category": "股癌觀點", "snippet": "股癌 EP667 Computex:Marvell 在光通訊噴發。光與銅線並行發展,Marvell + NVDA 是直接受惠者"},
            {"week": "2026-W12", "category": "AI 硬體", "snippet": "Jensen 親上 All-In:『ASIC 路線 (MRVL/AVGO) 短線會有雜訊但難撼動 CUDA』,Chamath 讓 Jensen 確認 Vera Rubin 25% 留給 Groq LPU/GPU 混合"},
            {"week": "2026-W11", "category": "AI 硬體", "snippet": "GTC 2026:MRVL 與 NVDA/AMD/AVGO/TSM 同框列為主題股"},
            {"week": "2026-W24", "category": "市場修正", "snippet": "Broadcom 指引保守 → SOX -10%。漲多的 Micron / Credo / Coherent 可能修 20-30% — Marvell 同陣營光通訊鏈須跟著震盪"},
        ],
    },
    "QCOM": {
        "name": "Qualcomm",
        "category_label": "手機 modem (Apple 流失中) + AI PC (Snapdragon X) + 汽車 / IoT",
        "valuation_params": {"fwd_pe_base": 14, "fwd_pe_bull": 18, "ps_base": 5, "ev_ebitda_base": 10, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.08, "dcf_terminal_growth": 0.025},
        "bull_thesis": [
            "估值便宜的相對防禦選項:fwd PE ~21x、mcap $209B、FCF $9.6B、毛利率 54.8%",
            "Marc Benioff (W20) 親口點 Qualcomm Cristiano Amon 隨團赴華:『賣晶片 (Nvidia、Qualcomm) 越多經濟合作越多和平』",
            "Saudi Arabia 國家 AI 計畫供應商:AMD/Groq/Nvidia/Qualcomm,主權 AI 海外輸出題材中 QCOM 不是配角",
            "Snapdragon X Elite AI PC 長線 narrative 仍在;Apple Silicon (M5) + 本地 SLM W22 共識點若擴散到 Windows,QCOM 也能分到企業 AI 主權對沖訂單",
            "車用 + IoT 雙引擎 (Snapdragon Digital Chassis + Satellite GSAT 合作)",
            "歷史 cyclical 防禦性:低 beta 高 FCF,AI Infra 深度修正時反成 risk-off 首選",
        ],
        "bear_thesis": [
            "Apple modem 結構性流失 (M報 W20/W18):蘋果自研 C1/C2 進度延續,QCOM 蘋果單佔比逐年下修",
            "AI PC Snapdragon X Elite 起飛緩慢 (股癌 EP668 W22):『高通那次嚴格上有點失敗,時間還沒到』",
            "Sacks (W18)『消費端輸給 Google Gemini (700M WAU)』:Android 端 AI 體驗主導權落到 Google,Snapdragon 8 Gen NPU 雖強但 OEM 偏好 Gemini",
            "成長題材弱 (data.json):mean target $233 (n=41) [$110-$321] 區間極寬,反映 narrative 不清晰",
            "GTC 2026 W11 / AVGO ASIC 主題股名單未列入 QCOM:hyperscaler 自研 ASIC 路線完全繞過 Qualcomm",
            "車用滲透雖在進行但對沖不掉 modem 衰退:Snapdragon Digital Chassis 毛利率低於手機 modem",
        ],
        "briefing_mentions": [
            {"week": "2026-W20", "category": "宏觀政治", "snippet": "All-In Benioff Trump-Xi Summit:Qualcomm Cristiano Amon 隨團赴華。中美 commerce 軸線『要賣飛機、賣晶片 (Nvidia、Qualcomm)』"},
            {"week": "2026-W22", "category": "股癌觀點", "snippet": "股癌 EP668 Computex:『高通那次 (AI PC) 嚴格上來說有一點失敗,不能怪他而是時間還沒到』"},
            {"week": "2026-W18", "category": "馬斯克 / 接班", "snippet": "Tim Cook 將卸任,John Ternus 9 月接任。蘋果自研模型 + 晶片路線確立後 QCOM modem Apple 單比重結構性下修"},
            {"week": "2026-W01", "category": "硬體大會", "snippet": "CES 2026 Las Vegas:NVDA/AMD/INTC/QCOM/AAPL 同框,AI PC / Auto / IoT 三大主題。Qualcomm 在 AI PC / Auto 路線雙線並行但缺強催化"},
            {"week": "2026-W24", "category": "市場修正", "snippet": "Broadcom 指引保守 → SOX 單日 -10%。QCOM fwd PE 21x 在 SOX 修正中相對抗跌,屬於防禦倉位"},
        ],
    },
    "PANW": {
        "name": "Palo Alto Networks",
        "category_label": "資安市值最大 / Platformization (Prisma + Cortex + Strata) + Mythos 漏洞掃描",
        "valuation_params": {"fwd_pe_base": 40, "fwd_pe_bull": 55, "ps_base": 14, "ev_ebitda_base": 30, "dcf_disc_rate": 0.09, "dcf_fcf_growth_5y": 0.22, "dcf_terminal_growth": 0.035},
        "bull_thesis": [
            "Nikesh Arora 親上 All-In W24『AI Found 5 Years of Bugs in 6 Weeks』:用 Mythos 在自家程式碼跑 6 週找到正常 5-7 年弱點,成本 low millions",
            "Platformization 走完 $150B 階段,再花 $25B 買 identity 公司 (CyberArk 級,3 個月前 closed) — 從綁訂單升級到綁 agentic AI 身分驗證",
            "Nikesh (W24):『AI 是 cyber 進入下一個 inflection 的鑰匙 — three months away from wild』,『cyber defenders 與 attackers 賽跑』為 PANW 銷售推進器",
            "Sacks W09『SaaS Apocalypse』被 Nikesh 直接反駁:PANW 定位『efficient enterprise AI 經營典範』Gross 90s / Net OM 40s 是新護城河",
            "Anthropic Fable 5 出口管制 + Bernie 沒收 AI 50% 股權雙催化:『AI 治理 + 漏洞掃描 + 身分驗證』被列為 Trump 政府『戰略物資』預算項",
            "Pelosi/Cathie Wood portfolio 持有 PANW Call;資安市值最大 ~$208B + FCF $3.6B",
        ],
        "bear_thesis": [
            "fwd PE ~70x、trailing PE ~250x 在 SaaS Apocalypse W07-W09 後仍偏高:Chamath『WACC 從 6% 跳 12-13%,PE 砍半,SBC 是下一個會掉的鞋』適用",
            "$25B identity 收購整合風險:Nikesh 自承『第一次 M&A 真的很難,街上 pretty skeptical』",
            "Anthropic Claude Code Security / OpenAI Codex / Cursor Composer 滲透:Friedberg『knowledge work 過渡業態』直接適用 cyber analyst",
            "客戶集中度於財富 500 大企業:小型企業端被微軟 Defender + CrowdStrike Falcon Go 分食",
            "Burry NVDA + PLTR 同框放空『hyperscaler depreciation 造假』可外溢:PANW 是 Platformization NRR 120% 模型代表股",
            "資安 ETF (CIBR/HACK) 三大權重 CRWD/PANW/ZS 同框,beta 互相強化;2024/7 CRWD 大當機教訓提醒可靠性是無形護城河",
        ],
        "briefing_mentions": [
            {"week": "2026-W24", "category": "資安", "snippet": "Nikesh Arora 親上 All-In『AI Found 5 Years of Bugs in 6 Weeks』:Mythos 6 週找到 5-7 年漏洞,成本 low millions。Platformization $150B 後再花 $25B 買 identity"},
            {"week": "2026-W24", "category": "資安", "snippet": "Nikesh:『three months away from wild — Claude 4.8/5.5 級漏洞掃描三個月內外流』。AI 是 cyber 進入下一個 inflection 的鑰匙"},
            {"week": "2026-W09", "category": "AI 軟體", "snippet": "Sacks 解讀 SaaS 大屠殺:2/20 Claude Code Security 預覽 CrowdStrike/Cloudflare/Okta 全倒。Platform 資安股同屬風險組"},
            {"week": "2026-W24", "category": "宏觀資金", "snippet": "Broadcom 指引保守 → SOX -10%。SaaS/Cyber beta 與 SOX 同步震盪須留意"},
            {"week": "2026-W12", "category": "政壇 13F", "snippet": "Pelosi 公開持有 NVDA/AVGO/PANW/GOOGL/AAPL — PANW 多用 LEAPS Call 槓桿"},
        ],
    },
    "CRWD": {
        "name": "CrowdStrike",
        "category_label": "資安龍頭 (EDR + Falcon platform) / AIDR (Agent Detection & Response)",
        "valuation_params": {"fwd_pe_base": 60, "fwd_pe_bull": 80, "ps_base": 18, "ev_ebitda_base": 50, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.25, "dcf_terminal_growth": 0.04},
        "bull_thesis": [
            "George Kurtz 親上 All-In W04 Davos 圓桌:AI 攻擊 pyramid (nation state → e-crime → activism),『attack timeline compressed, level 6 hacker 變 level 8』",
            "Kurtz (W04) 揭露 AIDR 新產品線:『每員工平均控制 90 個 agents,massive TAM』— 把 SaaSpocalypse 反轉成 CRWD TAM 放大",
            "Kurtz 經典案例:某客戶 AI agents 在 Slack 互相 reasoning 繞過 guard rails,J-Cal『太可怕,unintended consequences』",
            "2024/7 大當機後客戶留存超預期:歷經 -11% / mcap -$10B,W04 Kurtz 仍能上 All-In Davos 圓桌 — EDR 龍頭護城河仍在",
            "Falcon Flex 採用率 + ARR 結構性成長:NRR 120%+,mcap $160B + FCF $1.9B + 毛利率 75.1% best-in-class SaaS",
            "F1 贊助 + Kurtz race car driver 個人品牌為品牌溢價加分",
        ],
        "bear_thesis": [
            "fwd PE ~110x 為極端值:Burry W47 2025 NVDA + PLTR 放空陣營『EPS 線性外推』論述對 CRWD 致命 — ARR 從 30%/年降到 20%,fwd PE 直接 de-rate -45%",
            "Sacks W09 SaaS Apocalypse 直接點名:2/20 Claude Code Security 預覽『CrowdStrike、Cloudflare、Okta 全倒』",
            "2024/7 大當機後客戶流失到 SentinelOne (S):科技股可靠性是無形護城河,若再發生 outage,fwd PE 110x 沒 cushion",
            "Kurtz 自承『AI 攻擊三月內外流到 wild』雙刃:客戶 SOC 自動化可能繞過 Falcon agent",
            "Sacks Jevons paradox 推論 CRWD:軟體價格降但需求大爆發 → 既有訂閱 ARPU 是 dilution",
            "Chamath W07-W09『WACC 從 6% 跳 12-13%,PE 砍半』適用;SBC 比例若被重點檢視更會壓縮 fwd PE",
        ],
        "briefing_mentions": [
            {"week": "2026-W04", "category": "資安", "snippet": "George Kurtz 親上 All-In Davos:AI 攻擊 pyramid + 『attack timeline compressed』。揭露 AIDR『每員工 90 agents — massive TAM』"},
            {"week": "2026-W04", "category": "資安", "snippet": "Kurtz 案例:AI agents 在 Slack 互相 reasoning 繞過 guard rails 修 code。CRWD AIDR 從 EDR 擴張到 agent 防禦"},
            {"week": "2026-W09", "category": "AI 軟體", "snippet": "Sacks SaaS 大屠殺:2/20 Claude Code Security『CrowdStrike/Cloudflare/Okta 全倒』。CRWD fwd PE 110x 無 cushion"},
            {"week": "2026-W24", "category": "資安", "snippet": "Nikesh @ Palo Alto 圓桌間接定錨 CRWD:AI 漏洞掃描 + Platformization,資安兩大走 platform 共識"},
            {"week": "2024-07-19", "category": "歷史教訓", "snippet": "CRWD 全球 IT 大當機 -11% / mcap -$10B。資安股最大黑天鵝,後續客戶流失到 SentinelOne"},
        ],
    },
    "2454.TW": {
        "name": "聯發科 MediaTek (TWSE)",
        "category_label": "手機 SoC (Dimensity) + AI ASIC 設計 + 邊緣 AI (RTX Spark / N1X)",
        "valuation_params": {"fwd_pe_base": 18, "fwd_pe_bull": 25, "ps_base": 6, "ev_ebitda_base": 14, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.15, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "股癌 EP659 (W19) 自評『聯發科是今年最大的意外』 — 從 3000+ 噴到 4500+,ASIC 設計服務題材已正式啟動",
            "NVDA RTX Spark / N1X 合作 (W24 GTC Taipei):聯發科設計 ARM 20 核 + Blackwell 入門 GPU + 128GB 統一記憶體,可跑 120B 量化模型",
            "Goldman 喊『目標價 2454』(梗價暗示挑戰自家股號),反映 sell-side 持續上修共識",
            "AI ASIC 客製化題材:聯發科挖角台積電 CoWoS 大將 (股癌 EP657 W18) + Google TPU 部分代設計傳聞",
            "Forward PE 18x 看似貴但搭配 FY27 EPS 倍數成長 (Dimensity + 衛星 IoT + 車用 + RTX Spark 多引擎)",
            "毛利率 47%、FCF TTM NT$73.6B、配息率 117%",
        ],
        "bear_thesis": [
            "股癌 EP659 (W19) 自己警告『市場預估有點打得太滿』— 已『一次反應到 3000 多塊去』、市場 priced in",
            "Intel EMIB BBQ 風險 (股癌 EP657 W18):若 main die / IO die 認知錯位,分析師外推會被打臉",
            "Apple/Samsung 競爭壓力:Apple C1、Samsung Exynos 復活、Google Tensor G5 — 三大客戶都在『去聯發化』",
            "PE ~66 / Forward PE ~37 已是過去 5 年 90 百分位;若 NVDA RTX Spark 銷量不如預期 (Ben Thompson W22『chatbot circa 2023』偏空),AI PC 故事可能 2027 才驗證",
            "毛利率 47% 雖高但設計服務模式 — IP 授權 + Custom SI 利潤恐被客戶壓榨",
            "外資籌碼集中度高、融資餘額放大;若大盤從 42000 進入修正,權值前 5 大首當其衝",
        ],
        "briefing_mentions": [
            {"week": "2026-W19", "category": "股癌觀點", "snippet": "股癌 EP659-#660:『聯發科今年最大的意外』。AMD 上修 server CPU TAM、台股 ASIC 全面走強"},
            {"week": "2026-W18", "category": "股癌觀點", "snippet": "股癌 EP657:Intel EMIB 後段封裝良率 90%、聯發科挖台積電 CoWoS 大將。MTK 後續隱憂是 Intel 做不出來會 BBQ"},
            {"week": "2026-W24", "category": "AI 硬體", "snippet": "NVIDIA RTX Spark / N1X 揭曉 — 聯發科設計 ARM 20 核 + Blackwell + 128GB 統一記憶體,售價 NT$13-14 萬"},
            {"week": "2026-W17", "category": "股癌觀點", "snippet": "股癌 EP653-#654:聯發科 AI 布局深化 — 後續 5 月『意外噴出』的伏筆"},
            {"week": "2026-W25", "category": "股癌觀點", "snippet": "股癌 EP670:券商目標價迷因『聯發科 2454、台積電 2330、國巨 2327』陸續出現"},
        ],
    },
    "2308.TW": {
        "name": "台達電 Delta Electronics (TWSE)",
        "category_label": "AI 機櫃電源 (PSU + 800V HVDC) + 散熱液冷 + 工業自動化 + 車用充電樁",
        "valuation_params": {"fwd_pe_base": 25, "fwd_pe_bull": 35, "ps_base": 8, "ev_ebitda_base": 18, "dcf_disc_rate": 0.09, "dcf_fcf_growth_5y": 0.20, "dcf_terminal_growth": 0.035},
        "bull_thesis": [
            "股癌 EP663 (W21):『隔壁的 Power 櫃才是下一個金礦』— AI 算力 → 電源 (800V HVDC、PSU、DrMOS) 為下一個受惠族群",
            "GB200 機架功率密度倍增 + NVDA Vera Rubin 走 800V HVDC,股癌 EP671 (W25)『GB200 明年 5% penetration 對台廠就是破冰船級題材』",
            "股癌 EP633 (W06):『台達電/光寶/雙鴻散熱、廣達/緯穎 ODM 全面受惠』四大巨頭 CapEx 激增主受惠族群",
            "wisdom_classics EP575 (2025-W29):股癌『台達電財報強勁,長線故事無大問題』— 價值股 + 成長股雙重屬性",
            "Coatue Laffont (W23) Magnificent 8 框架隱含下游 capex 倍速擴張 — 電源/散熱為直接二階受惠者",
            "毛利率 35.5% (比 ODM 高一個量級)、FCF TTM NT$32.5B — 電源管理高 ROIC,EV 充電樁 + 工業自動化雙引擎",
        ],
        "bear_thesis": [
            "Forward PE 33x 已是過去 10 年 95 百分位,PE TTM 94x 顯示已 priced in 2028 EPS",
            "Chamath (W16) 五級火警警告 datacenter NIMBY:若 hyperscaler 砍 capex,台達電 AI 電源訂單能見度立刻打折",
            "競爭加劇:Vicor / Vertiv / Eaton 同樣 priced in AI 電源題材且美系廠商在 hyperscaler 客戶心中具地緣優勢",
            "30 天股價 -1.76% vs 大盤 +YTD 42% — 短期被動元件吸金,M觀點 W24 SOX -10% 後 AI Infra 群修",
            "AVGO 指引保守 W24 預演:若 ASIC 滲透率 2027 真的 30%、機架功率密度成長放緩,單機電源 ASP 上升速度可能不如預期",
            "Sacks (W47 2025) hyperscaler GPU 折舊 4→6 年同邏輯適用 PSU/液冷:若被延長折舊期,訂單節奏會被遞延 12-18 個月",
        ],
        "briefing_mentions": [
            {"week": "2026-W21", "category": "股癌觀點", "snippet": "股癌 EP663:『隔壁的 Power 櫃才是下一個金礦』— AI 算力 → 電源 (800V HVDC、PSU、DrMOS) 為下一個受惠族群"},
            {"week": "2026-W23", "category": "台股個股", "snippet": "富果直送 6 月 OCP 機櫃規格演進:OCP 從 IT 降本工具升級為整合電力+散熱的系統核心,規格競賽全面升級"},
            {"week": "2026-W06", "category": "股癌觀點", "snippet": "股癌 EP633:四大巨頭 CapEx 激增,『台達電/光寶/雙鴻散熱、廣達/緯穎 ODM 全面受惠』"},
            {"week": "2026-W25", "category": "股癌觀點", "snippet": "股癌 EP671:離散元件 + 功率半導體為下一波輪動;『GB200 明年 5% penetration 對台廠就是破冰船級題材』"},
            {"week": "2025-W29", "category": "股癌觀點", "snippet": "股癌 EP575:台達電 + 台積電 Q2 財報強勁、長線故事無大問題。看對大方向就能賺錢 — wisdom_classics 條目源頭"},
        ],
    },
    "2317.TW": {
        "name": "鴻海 Hon Hai / Foxconn (TWSE)",
        "category_label": "AI server ODM (GB200/GB300 機架代工) + iPhone 代工 + Foxtron EV",
        "valuation_params": {"fwd_pe_base": 14, "fwd_pe_bull": 20, "ps_base": 2, "ev_ebitda_base": 10, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.15, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "GTC Taipei 6/1 (W22) Jensen 確認:鴻海 $1.4B AI 雲超算中心 (10,000 GPU) + MoMClaw + Factory Operations Blueprint + GB300 NVL72 混合冷卻",
            "股癌 EP666 (W22):『老 AI 重新站起來 — 鴻海跟廣達都直接鎖漲停』+ 陳泰銘新首富後可能有『首富賽跑』",
            "EP666 跳跳奶油提問:券商 (Jeff Pu) 預估鴻海 TP 5000+ 都還沒把 OpenAI / Terrafab 算進去",
            "Forward PE 13.0x 在 Mag 7 + 台股核心 AI 標的中最便宜:Gavin Baker W21『AI 板塊 cross-sectionally inefficient』低估標的之一",
            "Sacks (W07) 四大 hyperscaler 2026 CapEx $6,000B,鴻海 GB200 機架代工市占規模最大",
            "FCF TTM NT$37.2B + 配息率 267% — 現金流真實;Apple iPhone 為基本盤 + Foxtron EV / 衛星終端為下一個十年期權",
        ],
        "bear_thesis": [
            "股癌 EP655 (W17):『2024 年愛潑鴻海股票槓爆的有很多人最後面就是一毛都沒有帶走,甚至倒賠』— 鴻海是台股最大融資斷頭歷史標的",
            "毛利率僅 6.2% — 鴻海本質是低毛利規模型代工,需要等到 2027 Q1『AI server 營收佔比突破 25%』才有重估邏輯",
            "ODM 競爭結構性風險 — 緯穎/廣達/緯創/和碩/英業達同台分食 GB200,純度排名 (緯穎 > 鴻海 ≈ 緯創 > 廣達) SemiAnalysis 公開,鴻海非首選",
            "Apple iPhone 出貨疲軟 + 印度產線分散 (立訊掘起):股癌 EP657 (W18) 反向暗示鴻海 iPhone 代工不會被搶,但成長到瓶頸",
            "Bernstein 估 ASIC 滲透 2026-2028 從 15% → 30%:ASIC 採用 OCP 標準化機架,意味 ODM 端議價力下降、毛利率往 5% 以下壓",
            "Dalio (W10) + Burry (W47 2025) 若兌現,鴻海作為下游 ODM 直接吃 capex 縮減訊號;Chamath W47 2025『risk-off』台廠 ODM 殺幅可達 30%+",
        ],
        "briefing_mentions": [
            {"week": "2026-W22", "category": "AI 硬體", "snippet": "GTC Taipei 6/1 Jensen keynote:鴻海 $1.4B AI 雲超算中心 (10,000 GPU) + GB300 NVL72 混合冷卻。純度:緯穎 > 鴻海 ≈ 緯創 > 廣達"},
            {"week": "2026-W22", "category": "股癌觀點", "snippet": "股癌 EP666:老 AI 重新站起來,鴻海/廣達直接鎖漲停。EP666 券商預估鴻海 TP 5000+ 都還沒把 OpenAI + Terrafab 算進去"},
            {"week": "2025-W40", "category": "股癌觀點", "snippet": "股癌 EP597:緯創從筆電 ODM 轉 AI server 王者。緯創 + 廣達 + 鴻海後續 2026 H1 持續走強"},
            {"week": "2026-W17", "category": "股癌觀點", "snippet": "股癌 EP655:2024 年愛潑鴻海股票槓爆的有很多人最後面一毛都沒有帶走甚至倒賠 — 槓桿心態需提防"},
            {"week": "2026-W18", "category": "股癌觀點", "snippet": "股癌 EP657:OpenAI 與立訊 AI 裝置難取代 iPhone — 反向確認鴻海 iPhone 代工不會被立訊搶但成長已遇瓶頸"},
        ],
    },
    "TXN": {
        "name": "Texas Instruments",
        "category_label": "類比 IC + 電源管理龍頭 (analog/embedded IDM) — DrMOS / AI server 電源受惠",
        "valuation_params": {"fwd_pe_base": 22, "fwd_pe_bull": 28, "ps_base": 7, "ev_ebitda_base": 16, "dcf_disc_rate": 0.09, "dcf_fcf_growth_5y": 0.08, "dcf_terminal_growth": 0.025},
        "bull_thesis": [
            "類比 IC 庫存週期領先指標:Q2 26 earnings (2026-07-21) sell-side 預期 yoy_rev +18%、EPS $1.92,若指引轉正等於替全行業 (ADI/MCHP/NXPI/STM) 喊回升",
            "AI server 電源 DrMOS / 多相 VRM 用量結構性放大:NVDA GB200/GB300 機櫃 48V 架構增加 TXN power IC 含金量",
            "美國 in-sourcing 政策受惠:Sherman/Lehi 12 吋廠 capex 高峰已過,2026-2027 折舊壓力轉為毛利率回升槓桿",
            "股息 cash cow:殖利率高 + 23 年連續增配,在 risk-off 期間屬於半導體中防禦角色",
            "分析師目標價中位數 $290 (n=33) 區間 $200-$400,反映 cyclical 上行共識仍有空間",
        ],
        "bear_thesis": [
            "Capex 週期未結束:LFAB/RFAB2/SM1-SM2 多廠同步推進,Free Cash Flow 短期受壓 (FCF TTM 已從歷史 $6B+ 跌到 $1B 級別)",
            "中國本土替代壓力:聖邦/思瑞浦/納芯微等類比 IC 國產替代政策性扶植,TXN 中國敏感度高",
            "PE ~57 / fwd PE ~35 在歷史區間中偏貴 (過去 5 年 fwd PE 中位 ~22),已 priced in 庫存週期回升",
            "汽車 / 工業終端需求若延遲復甦,2026 EPS 共識可能下修 — 領先指標反向也成立",
            "earnings hist_move ±5% 但分析師 PT 區間 [$200-$400] 暗示市場分歧大,財報後波動風險",
        ],
        "briefing_mentions": [
            {"week": "2026-W25", "category": "AI 硬體", "snippet": "股癌 EP671 觀察:被動元件炒作後資金可能輪動到功率半導體 (Onsemi / Infineon / 瑞薩 / TXN)。AI 機櫃 12V → 48V/800V HVDC 換代受惠"},
            {"week": "2026-W30", "category": "財報", "snippet": "TXN Q2 26 earnings 2026-07-21 AMC:類比 IC 庫存週期領先指標。sell-side 預期 EPS $1.92 / Rev $5.23B / yoy +18%"},
        ],
    },
    "ON": {
        "name": "Onsemi",
        "category_label": "功率半導體 IDM (SiC + IGBT + 離散元件全線) — EV / 工業 / AI 電源三引擎",
        "valuation_params": {"fwd_pe_base": 18, "fwd_pe_bull": 25, "ps_base": 4, "ev_ebitda_base": 12, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.10, "dcf_terminal_growth": 0.025},
        "bull_thesis": [
            "themes/功率半導體 purity 5 純度最高:SiC + IGBT + 離散元件全線,EV / 工業 / AI 電源三引擎結構性受惠",
            "AI 機櫃 12V → 48V/800V HVDC 換代:Onsemi SiC MOSFET 在 PSU / DrMOS / Super Junction 上含金量提升",
            "股癌 EP671 觀察:被動元件炒作後資金可能輪動到功率半導體,Onsemi 是純度最高的標的之一",
            "Nexperia 制裁事件推動車用 Tier-1 做非中國佈局,Onsemi 美國 + 韓國 + 馬來西亞產能受惠 supply chain re-route",
            "EV 終端雖然短期 demand 疲弱,但 SiC 滲透率長線從 ICE 切換成不可逆,Onsemi 4-8 吋 SiC 線在 2026 進入量產爬坡",
        ],
        "bear_thesis": [
            "PE ~97 / fwd PE ~30 在功率半導體同業中偏高 (vs TXN fwd 35 / MCHP / ADI),已部分 priced in AI 電源故事",
            "EV 終端需求疲弱:Tesla / 大眾 / Stellantis EV 銷量 2026 H1 indicators 偏弱,SiC 訂單能見度被質疑",
            "中國本土 SiC (基本半導體 / 三安光電 / 比亞迪自研) 政策性扶植,Onsemi 中國份額面臨擠壓",
            "FCF $1.3B 在 mcap $51B 對比下偏弱 (FCF yield ~2.5%),若 capex 不縮減則股息 / 回購受限",
            "毛利率 42.7% vs TXN 57.3% / ADI 60%+ — 離散元件比重高拖累 mix,需要 SiC mix shift 才能撐住估值",
        ],
        "briefing_mentions": [
            {"week": "2026-W25", "category": "AI 硬體", "snippet": "股癌 EP671:被動元件炒作後資金可能輪動到功率半導體 (Onsemi / Infineon / 瑞薩 / TXN)。Onsemi 是 SiC + IGBT + 離散全線純度最高"},
            {"week": "2026-W25", "category": "宏觀政治", "snippet": "Nexperia 制裁事件推動車用 Tier-1 做非中國佈局,Onsemi 美 / 韓 / 馬來西亞產能在 supply chain re-route 中受惠"},
        ],
    },
    "IFNNY": {
        "name": "Infineon Technologies (ADR)",
        "category_label": "全球功率半導體龍頭 — 汽車 + 工業 + AI Server PSU",
        "valuation_params": {"fwd_pe_base": 18, "fwd_pe_bull": 25, "ps_base": 3, "ev_ebitda_base": 11, "dcf_disc_rate": 0.09, "dcf_fcf_growth_5y": 0.10, "dcf_terminal_growth": 0.025},
        "bull_thesis": [
            "themes/功率半導體 purity 5 與 Onsemi 並列最高:全球功率半導體龍頭地位穩固,汽車 + 工業 + AI Server PSU 三大引擎",
            "AI Server PSU 直接受惠 48V/800V HVDC 換代:Infineon 在 datacenter power conversion 是 NVDA / hyperscaler 主要供應商",
            "股癌 EP671 觀察:被動元件炒作後資金可能輪動到功率半導體,Infineon 是歐洲 SiC + IGBT 唯一全棧玩家",
            "Dresden 智慧電網 12 吋廠 2026 量產:歐洲在地供應鏈受惠 EU Chips Act 補貼,降低地緣風險溢價",
            "汽車 microcontroller (Aurix) 在 ADAS / SDV 滲透率持續提升:現代汽車 / 福斯 / BMW 都是核心客戶",
        ],
        "bear_thesis": [
            "PE ~105 / fwd PE ~32 在 ADR 估值偏高 (本地股 IFX.DE 估值相對合理),ADR premium 反映流動性折價",
            "歐洲汽車終端 (Tier-1) 庫存 2026 H1 仍在去化:Bosch / Continental / Magna 訂單能見度有限,工業終端也未明確復甦",
            "中國本土功率半導體 (士蘭微 / 揚杰科技 / 華潤微) 政策性扶植 + 比亞迪自研 IGBT,Infineon 在中國 EV 市場份額面臨壓縮",
            "FCF $1.4B 在 mcap $129B 對比下偏弱 (FCF yield ~1.1%),Dresden / Kulim capex 高峰未過",
            "ADR (IFNNY) vs 本地股 (IFX.DE) 雙重風險:歐元 / 美元匯率 + ADR 折溢價波動加大",
        ],
        "briefing_mentions": [
            {"week": "2026-W25", "category": "AI 硬體", "snippet": "股癌 EP671:被動元件炒作後資金可能輪動到功率半導體 (Onsemi / Infineon / 瑞薩 / TXN)。Infineon 是歐洲 SiC + IGBT 唯一全棧"},
            {"week": "2026-W25", "category": "AI 算力", "snippet": "AI 機櫃 12V → 48V/800V HVDC 架構升級,Infineon 在 datacenter PSU 是 NVDA / hyperscaler 主要供應商"},
        ],
    },
    "ASML": {
        "name": "ASML Holding",
        "category_label": "EUV 微影獨佔 (NXE / High-NA EXE) — 先進製程命脈",
        "valuation_params": {"fwd_pe_base": 30, "fwd_pe_bull": 38, "ps_base": 10, "ev_ebitda_base": 22, "dcf_disc_rate": 0.09, "dcf_fcf_growth_5y": 0.15, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "EUV 微影獨佔護城河:TSMC N3/N2、Intel 18A、Samsung SF2 全要 ASML 機台 — 沒有第二供應商,2nm 以下 High-NA EXE 是唯一選項",
            "TSM CoWoS 擴產直接拉動 ASML 訂單:Brad Gerstner W19 Anthropic ARR $44B 推 hyperscaler capex 結構性放大,wafer demand → litho tool demand 直接傳導",
            "中國管制反向利多基本面:DUV 禁令逼中國加倍下單 (清華 2024 突破論文 Freeberg W51 點到但仍需 10+ 年才能威脅 ASML 地位)",
            "Order backlog 突破 €40B + book-to-bill >1.5:能見度延伸到 2028,景氣波動防護墊厚",
            "High-NA EXE-5200 已開始出貨給 Intel/TSMC/Samsung:每台 €380M+,毛利率 50%+ 結構性上修;FCF 在工具放量年可達 €10B+",
        ],
        "bear_thesis": [
            "PE ~65 / fwd PE ~30 在歷史區間中偏貴:景氣循環股給高 PE 是雙刃,若 2027 hyperscaler capex digestion,fwd PE 直接 de-rate -30%",
            "中國占比歷史最高 40%+,美國商務部進一步禁令 (DUV/服務)可能讓中國訂單斷崖式下滑",
            "客戶集中度極高 (TSMC + Intel + Samsung 三家佔 60%+):任一家延宕新廠計畫即影響 ASML 季度業績",
            "High-NA EXE 良率與客戶導入速度低於預期:Intel 18A 若延後量產,High-NA TAM 上修時程遞延",
            "歐洲股 ADR 流動性折溢價 + 歐元/美元匯率風險:對美股投資人多了一層雜訊",
        ],
        "briefing_mentions": [
            {"week": "2025-W51", "category": "AI 算力", "snippet": "Freeberg 拉出細節:中國 National IC Investment Fund Phase 3 (2024) $48B 鎖定 lithography 瓶頸,清華團隊發表 EUV 突破論文 — 但量產仍 10+ 年外,ASML 護城河中期穩固"},
        ],
    },
    "AMAT": {
        "name": "Applied Materials",
        "category_label": "半導體設備 (沉積 / 蝕刻 / CMP) — 先進製程 + 先進封裝雙引擎",
        "valuation_params": {"fwd_pe_base": 22, "fwd_pe_bull": 28, "ps_base": 6, "ev_ebitda_base": 16, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.12, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "先進封裝 + HBM 雙題材:CoWoS / HBM3E/HBM4 製程都需要 AMAT 沉積 + CMP 工具,TSMC 擴產與 Micron HBM 量產直接拉動營收",
            "Gate-All-Around (GAA) 技術轉換 AMAT 工具強度高:N2/SF2/Intel 18A 都採用 GAA,AMAT 工具含金量 (per wafer dollar) 結構性上修",
            "美國本土 fab 補貼受惠:CHIPS Act 撥款落地後 Intel/TSM Arizona/Samsung Taylor 工廠都需要 AMAT 工具,2026-2028 美國訂單放量",
            "毛利率 47%+ FCF $7B+ 在半導體設備中第二高 (僅次於 KLAC 之檢測高毛利);estimated FY27 EPS 雙位數成長維持",
            "中國 mature node 仍可賣 (非 EUV 禁令範圍):中國成熟製程擴產 (28nm/14nm) 是 AMAT 短線緩衝",
        ],
        "bear_thesis": [
            "PE ~60 / fwd PE ~25 在景氣循環股偏貴:hyperscaler capex digestion 可能讓 2027 fwd PE de-rate",
            "中國占比 30%+ 持續面臨地緣風險:美國商務部新一輪管制清單若擴大,AMAT 中國 mature node 業務也可能受牽連",
            "ASML / LRCX / KLAC 三家設備龍頭客戶重疊度高:競標壓力增加,毛利率長線天花板存在",
            "memory cyclical 風險:Micron / SK Hynix / Samsung 任一家砍 capex 即影響 AMAT memory 工具訂單 (Burry W47 2025 放空陣營邏輯延伸)",
            "技術轉換 (GAA / Backside Power Delivery) 客戶導入時程不一,AMAT 工具導入 ramp 可能慢於預期",
        ],
        "briefing_mentions": [
            {"week": "2025-W51", "category": "AI 算力", "snippet": "中國 National IC Investment Fund Phase 3 $48B 鎖定 lithography + 設備瓶頸 — AMAT 在中國 mature node 仍能賣但長線替代風險存在"},
        ],
    },
    "LRCX": {
        "name": "Lam Research",
        "category_label": "蝕刻 + 沉積設備 — NAND / HBM / 先進封裝核心",
        "valuation_params": {"fwd_pe_base": 22, "fwd_pe_bull": 28, "ps_base": 7, "ev_ebitda_base": 17, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.12, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "HBM3E/HBM4 製程蝕刻設備 LRCX 主導:TSV (Through-Silicon Via) 蝕刻是 HBM 量產關鍵步驟,Micron / SK 海力士 / Samsung 三家 HBM 擴產直接受惠",
            "NAND 復甦領先指標:SNDK (Sandisk) / Kioxia / Samsung NAND 庫存週期 2026 H2 觸底,LRCX NAND 工具 ramp 隨之啟動",
            "毛利率 48%+、FCF $5B+ 結構性穩定;股息 + 回購歷史紀錄一致",
            "中國 mature node 訂單緩衝:中國 28nm 以下 NAND 擴產仍可賣設備,2026 中國占比仍超 30%",
            "先進封裝題材外溢:CoWoS / 3D-IC 都需要 LRCX 蝕刻 + 沉積工具,單片晶圓含金量上修",
        ],
        "bear_thesis": [
            "PE ~67 / fwd PE ~25 偏貴:NAND 復甦若延後到 2027,fwd PE 無支撐",
            "中國占比 40%+ 為三大設備廠中最高:美國管制清單擴大時 LRCX 跌幅可能最深",
            "NAND 過剩問題未根本解決:Samsung / 美光 / Kioxia 產能擴張節奏不一致,可能再現 2022-2023 cyclical 谷底",
            "客戶集中度:Samsung + SK Hynix + Micron 三家佔 NAND/HBM 訂單 70%+",
            "技術轉換 (3D NAND 200 層 → 300 層) 工具導入時程不確定,客戶可能延後升級",
        ],
        "briefing_mentions": [
            {"week": "2025-W51", "category": "AI 算力", "snippet": "中國 National IC Investment Fund Phase 3 $48B 鎖定設備瓶頸 — LRCX 在中國蝕刻/沉積仍有市場但長線替代壓力最大"},
        ],
    },
    "KLAC": {
        "name": "KLA Corporation",
        "category_label": "晶圓檢測 / 量測獨佔 (Process Control) — 良率提升必備",
        "valuation_params": {"fwd_pe_base": 25, "fwd_pe_bull": 32, "ps_base": 9, "ev_ebitda_base": 20, "dcf_disc_rate": 0.09, "dcf_fcf_growth_5y": 0.13, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "Process Control 細分市場市占 50%+ 接近獨佔:N2 / 18A / SF2 GAA 製程良率挑戰加大,KLA 檢測設備含金量結構性上修",
            "毛利率 60%+ 為半導體設備中最高:Operating Margin 40%+ 跑贏 ASML / AMAT / LRCX,屬於『高 ROIC 工程護城河』典範",
            "HBM / CoWoS 檢測需求結構性放大:封裝越複雜,KLA 工具導入越多 (一條 CoWoS 線通常需要 5-10 套 KLA 工具)",
            "Service / Spare parts 占比 35%+:訂閱式現金流穩定 (recurring),景氣下行時防禦性比同業強",
            "FCF $4B+ + 回購歷史一致;股息殖利率雖低但成長率超過 SOX 平均",
        ],
        "bear_thesis": [
            "PE ~76 / fwd PE ~30 為設備三巨頭中最貴:premium 已 priced in 獨佔地位,景氣下行 fwd PE de-rate 空間大",
            "客戶集中度極高 (TSMC + Samsung + Intel 三家佔 60%+):任一家延宕擴產直接影響 KLA 訂單",
            "中國占比較低 (~20%) 是雙刃:地緣風險小但中國成熟製程紅利也較小",
            "Service 業務雖穩但無法完全對沖工具訂單波動;2022-2023 cyclical 谷底時 KLA 也修正 30%+",
            "AI / GAA 製程一旦良率突破成熟,客戶後續工具導入 ramp 可能放緩",
        ],
        "briefing_mentions": [
            {"week": "2025-W51", "category": "AI 算力", "snippet": "中國 National IC Investment Fund Phase 3 提及 lithography 瓶頸,但檢測設備仍是 KLA 獨佔 — 中國國產替代難度更高"},
        ],
    },
    "TER": {
        "name": "Teradyne",
        "category_label": "半導體測試設備 (ATE) + 工業機器人 — AI ASIC / HBM 測試受惠",
        "valuation_params": {"fwd_pe_base": 22, "fwd_pe_bull": 30, "ps_base": 5, "ev_ebitda_base": 16, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.13, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "AI ASIC 客製化測試需求結構性放大:Google TPU / AWS Trainium / Meta MTIA / Microsoft Maia 量產都需要 TER ATE 設備",
            "HBM 測試 ASIC 整合題材:Memory + Logic 混合測試是 TER 強項,HBM3E/HBM4 量產直接拉動營收",
            "工業機器人 (Universal Robots / MiR) 第二曲線:Friedberg W12 Physical AI 故事溢價,雖小但具備重估彈性",
            "FCF $700M+ + 回購政策積極;mcap $35B 規模中型但成長 narrative 完整",
            "客戶分散度比 ASML/AMAT 高:不僅服務 logic / memory,也服務 power / analog / RF 廠商",
        ],
        "bear_thesis": [
            "PE ~85 / fwd PE ~30 偏貴:ATE 市場景氣波動劇烈,fwd PE 高位易受 capex digestion 衝擊",
            "客戶 Apple 占比歷史曾達 40%+:近年下修但仍是單一客戶風險;Apple 自研 modem/SoC 路線若加速,TER 訂單波動加大",
            "工業機器人雖故事好但占營收比重小 (~15%),短期無法對沖 ATE 主業 cyclical 波動",
            "中國成熟製程 ATE 訂單 2025-2026 上修但長線可能受美國管制擴大影響",
            "AI ASIC 訂單能見度雖好但客戶 timeline 不確定,2027 才真正 ramp",
        ],
        "briefing_mentions": [],
    },
    "ACLS": {
        "name": "Axcelis Technologies",
        "category_label": "離子植入設備 (高能量 implanter) — 功率半導體 + 先進製程",
        "valuation_params": {"fwd_pe_base": 18, "fwd_pe_bull": 24, "ps_base": 4, "ev_ebitda_base": 12, "dcf_disc_rate": 0.11, "dcf_fcf_growth_5y": 0.10, "dcf_terminal_growth": 0.025},
        "bull_thesis": [
            "功率半導體 (SiC / IGBT) 離子植入設備龍頭:呼應 ON / IFNNY / TXN 三檔功率半導體擴產,ACLS 是上游受惠者",
            "中國 mature node 訂單 2026 仍是主要動能 (40%+ 營收):28nm/14nm 擴產直接拉動 implanter 需求",
            "EV / 工業電源終端雖短期疲弱但 SiC 滲透不可逆:長線 ACLS 高能量 implanter TAM 結構性放大",
            "毛利率 45%+ FCF $200M+ 在中型設備廠中相對穩定;FY26 共識 EPS 雙位數成長",
            "客戶分散 (功率 IDM + 中國成熟製程 + Memory) — 比 KLAC 客戶集中度低,景氣下行抗跌性較強",
        ],
        "bear_thesis": [
            "PE ~57 / fwd PE ~25 偏貴:中小型設備廠 fwd PE 給高反映 SiC 故事,但景氣下行 de-rate 空間大",
            "中國占比 40%+:美國管制清單若擴及 implanter,ACLS 中國訂單可能斷崖式下滑",
            "客戶集中度仍存:中國前 3 大 IDM 佔中國訂單 60%+,任一家延宕擴產即影響 ACLS",
            "SiC EV 終端 demand 短期疲弱:Tesla / 大眾 EV 銷量 2026 H1 偏弱,ACLS 高能量 implanter 訂單能見度被質疑",
            "mcap $5B 小型股流動性風險:風險偏好下行時跌幅可能放大 1.5-2x",
        ],
        "briefing_mentions": [
            {"week": "2026-W25", "category": "AI 硬體", "snippet": "股癌 EP671:被動 → 功率半導體輪動。功率半導體擴產直接拉動 ACLS 離子植入設備訂單"},
        ],
    },
    "CRWV": {
        "name": "CoreWeave",
        "category_label": "NeoCloud 一哥 (純 GPU IaaS) — xAI / Anthropic 主要 GPU 供應商",
        "valuation_params": {"fwd_pe_base": 50, "fwd_pe_bull": 70, "ps_base": 14, "ev_ebitda_base": 35, "dcf_disc_rate": 0.12, "dcf_fcf_growth_5y": 0.35, "dcf_terminal_growth": 0.04},
        "bull_thesis": [
            "xAI 33 個月合約近 $300 億 + Anthropic 月租 $12.5 億 (W24):年化 $260 億 ≫ CRWV+NBIS 加總,NeoCloud 一哥地位確立",
            "Agent AI Q1 爆發超出所有 hyperscaler 預期:CRWV 純 GPU IaaS 模式正好對到 Anthropic / xAI / OpenAI sub-letter 需求",
            "NVDA 親爹級客戶關係:Jensen 把 GB200/GB300 早期配額優先給 CRWV (M報多次提及『Jensen 是 CRWV 早期投資人』)",
            "AI capex 結構性放大:Brad Gerstner W19 估 Anthropic ARR $44B/10x 一年,Coatue Laffont (W23) 估『AI 算力 TAM 2030 達 $4T』,CRWV 是純度最高純打標的",
            "Gavin Baker W21 點出 AI 板塊 cross-sectionally inefficient,CRWV 雖貴但 GPU 利用率 90%+ vs hyperscaler 60% 是結構性優勢",
        ],
        "bear_thesis": [
            "PE / fwd PE 都極端 (PS 14x):IPO 後估值已 fully priced AI infra 故事,Burry W47 2025 放空陣營邏輯適用",
            "GPU 折舊周期是定時炸彈:Sacks W47 2025『hyperscaler 4 年 → 6 年折舊』邏輯適用,CRWV 若被迫從 5 年改 3 年折舊,EPS 砍半",
            "客戶集中度極高:xAI + Anthropic + OpenAI 三家佔營收 80%+,任一家自建/轉 hyperscaler 即影響 CRWV 業績",
            "DeepSeek R1 等開源模型若大幅降低 inference 算力需求,CRWV 利用率與定價權同步壓縮",
            "Burry NVDA + PLTR + CRWV 三點放空理論:GPU 經濟學若被質疑,純 GPU IaaS 是第一個垮的 — 雖被 Chamath/Freeberg 反駁,但敘事風險仍在",
        ],
        "briefing_mentions": [
            {"week": "2026-W24", "category": "AI 算力", "snippet": "xAI 33 個月合約近 $300 億 + Anthropic $12.5 億/月 → CRWV 年化 $260 億,NeoCloud 一哥確立"},
            {"week": "2026-W23", "category": "AI 算力", "snippet": "Coatue Laffont (All-In Summit) 估 AI 算力 TAM 2030 達 $4T,CRWV 是純度最高 pure-play"},
        ],
    },
    "NBIS": {
        "name": "Nebius Group",
        "category_label": "NeoCloud 二把手 (歐洲) — 從 Yandex spin-off 的純 AI infra",
        "valuation_params": {"fwd_pe_base": 40, "fwd_pe_bull": 60, "ps_base": 10, "ev_ebitda_base": 30, "dcf_disc_rate": 0.12, "dcf_fcf_growth_5y": 0.30, "dcf_terminal_growth": 0.04},
        "bull_thesis": [
            "歐洲 NeoCloud 地理套利:GDPR / Data Sovereignty 推升歐洲 AI infra 在地化需求,NBIS 是純歐洲玩家中規模最大",
            "Anthropic + Mistral + 歐洲企業客戶結構性受惠:歐洲版『主權 AI』政策推進時 NBIS 是優先選擇",
            "CRWV 模式複製 + 歐洲折價:估值低於 CRWV (PS ~10x vs 14x),若 NBIS 拿到類似 xAI/Anthropic 級別大單,股價 catch-up 空間大",
            "Yandex spin-off 後資產乾淨 (剝離俄羅斯業務):mcap ~$15B 中型成長股,流動性逐月改善",
            "AI capex 結構性放大邏輯同 CRWV:Brad Gerstner / Coatue Laffont 的 $4T TAM 故事 NBIS 同樣分到一杯",
        ],
        "bear_thesis": [
            "Burry NVDA + PLTR + CRWV 放空邏輯也適用 NBIS:GPU 折舊周期 + 客戶集中度雙風險",
            "歐洲 AI 客戶基數仍小:Mistral 雖然受捧但 ARR 不到 Anthropic 1/10,歐洲企業 AI 採用速度落後美國 12-18 個月",
            "客戶集中度未知 (披露少):若主力客戶 1-2 家,風險集中度可能比 CRWV 更高",
            "PE / fwd PE 都偏貴 (PS ~10x):若 2027 AI capex digestion,NBIS 跌幅可能超過 CRWV",
            "Yandex 歷史包袱 + 俄烏戰爭 sentiment 殘留:部分美國機構受託限制可能持續迴避",
        ],
        "briefing_mentions": [
            {"week": "2026-W24", "category": "AI 算力", "snippet": "xAI 拿下 CRWV 大單後,NeoCloud 排名 CRWV ≫ NBIS;NBIS 須加速拿下歐洲主權 AI 訂單"},
        ],
    },
    "IREN": {
        "name": "IREN Limited",
        "category_label": "比特幣礦工轉 AI 算力 (HPC pivot) — 澳洲 + 北美電力套利",
        "valuation_params": {"fwd_pe_base": 25, "fwd_pe_bull": 45, "ps_base": 6, "ev_ebitda_base": 20, "dcf_disc_rate": 0.13, "dcf_fcf_growth_5y": 0.30, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "BTC 礦工 pivot AI HPC 第二曲線:既有電力 + 機房資產可重新部署 GPU,毛利率從 BTC 30% 拉到 AI 50%+",
            "澳洲 + 加拿大 + 美國德州低電價套利:電力成本 $0.04/kWh vs 美國本土 hyperscaler $0.08+,結構性成本優勢",
            "AI capex 結構性放大邏輯:CRWV/NBIS 之外 hyperscaler 仍需要 tier-2/3 GPU 容量,IREN 是最便宜的替代選項",
            "比特幣 cyclical 反彈雙引擎:若 BTC 在 2026-2027 走多,IREN 雙故事股屬性溢價",
            "mcap 中小型 ($5-8B) 流動性逐月改善;BlackRock IBIT 入主後散戶可見度提升",
        ],
        "bear_thesis": [
            "AI HPC pivot 執行風險:GPU 採購 / 客戶簽約 / 利用率三道關卡都未驗證,執行不到位 fwd PE 直接砍半",
            "BTC 價格波動高 beta:若 BTC 從 $120K 跌回 $60K,IREN 主業現金流壓力大,AI pivot 資本支出受限",
            "客戶能見度差:不像 CRWV 有 xAI/Anthropic 級別大單,IREN 客戶 disclosure 稀少",
            "電力價格地緣風險:澳洲再生能源政策 / 德州 ERCOT 監管變化都可能侵蝕成本優勢",
            "Sacks W47 2025『risk-off』邏輯下,雙故事股 (BTC + AI) 雙重風險暴露",
        ],
        "briefing_mentions": [],
    },
    "CIFR": {
        "name": "Cipher Mining",
        "category_label": "BTC 礦工 + AI 算力 pivot — 德州低電價 + Bitfury 技術背景",
        "valuation_params": {"fwd_pe_base": 22, "fwd_pe_bull": 40, "ps_base": 5, "ev_ebitda_base": 18, "dcf_disc_rate": 0.13, "dcf_fcf_growth_5y": 0.28, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "德州 ERCOT 低電價套利 + Bitfury 集團技術背景:CIFR 比同業 (IREN/MARA/RIOT) 多一層工程文化加持",
            "AI HPC pivot 雷同 IREN 但更聚焦德州單一州:政策風險集中但執行集中度高",
            "BTC + AI 雙故事股屬性同 IREN;mcap 中小型,beta 高在多頭時跌得多但漲得也多",
            "AI capex 結構性放大紅利同 IREN:tier-2/3 GPU 容量需求是 CIFR 接單空間",
            "Bitfury 是 BTC 圈最老牌玩家之一,技術背書 + 國際關係網絡是 IREN 沒有的隱性資產",
        ],
        "bear_thesis": [
            "與 IREN 高度同質競爭:選一檔即可,雙押邊際效益遞減",
            "客戶能見度低 + AI pivot 執行風險高:BTC 價格回撤時資本支出受限",
            "規模小於 IREN (~$3B mcap):流動性風險更高,beta 更激烈",
            "德州 ERCOT 監管變化 / 電價波動 / 居民反彈三道風險集中",
            "Burry/Sacks risk-off 邏輯下小型 BTC+AI 雙故事股是第一波被砍倉位",
        ],
        "briefing_mentions": [],
    },
    "COHR": {
        "name": "Coherent",
        "category_label": "光通訊 (Datacom + Telecom) — EML / 800G optical transceiver 受惠 AI server",
        "valuation_params": {"fwd_pe_base": 25, "fwd_pe_bull": 35, "ps_base": 5, "ev_ebitda_base": 16, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.18, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "AI Datacom 光通訊全棧供應商:800G / 1.6T optical transceiver 是 NVDA GB200/GB300 機櫃必備,COHR 是少數能量產 EML 雷射的廠商",
            "Hyperscaler capex 結構性受惠:Microsoft/Meta/Google/AWS 都把光通訊列為 datacenter 升級重點,COHR 訂單能見度延伸到 2027",
            "CPO (Co-Packaged Optics) 長線題材:NVDA Spectrum-X CPO 路線確定後,COHR / LITE / FORM 都是受惠者",
            "客戶分散度好:Datacom + Telecom + Industrial + Materials 四引擎,景氣下行抗跌性比純 LITE 強",
            "毛利率 35-40% + FCF 結構性回升;mcap ~$25B 中型成長股具備重估彈性",
        ],
        "bear_thesis": [
            "PE 高 (TTM > 100) 由 II-VI 併購 goodwill 拖累:fwd PE ~25x 看似合理但需 2027 EPS 翻倍才合理化",
            "客戶集中度仍高:NVDA / Cisco / Arista 三家光通訊客戶佔比 50%+,任一家砍單即影響業績",
            "EML 雷射技術門檻雖高但日本 (Sumitomo / Mitsubishi) 在追趕,長線市佔風險存在",
            "CPO 取代 pluggable optical 時程不確定:若 2026-2027 hyperscaler 加速 CPO 採用,COHR 短期 pluggable 業務承壓",
            "Sacks W47 2025 risk-off 邏輯下,中型 AI 受惠股是被砍倉位的範圍",
        ],
        "briefing_mentions": [],
    },
    "LITE": {
        "name": "Lumentum",
        "category_label": "Datacom 光通訊 + EML 雷射 — AI 光通訊鏈純度最高之一",
        "valuation_params": {"fwd_pe_base": 30, "fwd_pe_bull": 45, "ps_base": 8, "ev_ebitda_base": 20, "dcf_disc_rate": 0.11, "dcf_fcf_growth_5y": 0.25, "dcf_terminal_growth": 0.04},
        "bull_thesis": [
            "FQ4 26 earnings (2026-08-05 AMC) 共識 yoy +105% Rev / EPS $2.96:AI Datacom 光通訊鏈核心,800G EML 出貨爆發",
            "AI 光通訊鏈純度最高之一:LITE 在 EML / DML 雷射上有結構性領先地位,NVDA / Cisco / Arista 都是大客戶",
            "CPO 長線題材紅利同 COHR:NVDA Spectrum-X 路線確定後 LITE 是上游受惠者",
            "Telecom + 3D Sensing (Apple) 雙引擎:Datacom 之外仍有第二曲線,景氣下行有緩衝",
            "mcap ~$25B 中型成長股,sell-side 共識 PT $1113 (n=24) 反映重估空間",
        ],
        "bear_thesis": [
            "fwd PE 高位 (>30x) 已 priced in AI Datacom 故事:若 800G 出貨遞延或 hyperscaler capex digestion,fwd PE de-rate 空間大",
            "客戶集中度 + 競爭激化:Cisco/Arista/NVDA 議價力強,LITE 毛利率長線壓縮風險",
            "Apple 3D Sensing 業務 cyclical:iPhone 銷量疲弱年 LITE 3D Sensing 訂單波動",
            "EML 雷射技術競爭:日本廠商 (Sumitomo/Mitsubishi) + 中國廠商 (源杰) 追趕,長線市佔風險存在",
            "earnings hist_move ±12% 波動劇烈:財報後跳水風險高",
        ],
        "briefing_mentions": [],
    },
    "FORM": {
        "name": "FormFactor",
        "category_label": "晶圓探針卡 (Probe Card) — 先進製程 + HBM 測試受惠",
        "valuation_params": {"fwd_pe_base": 22, "fwd_pe_bull": 30, "ps_base": 5, "ev_ebitda_base": 15, "dcf_disc_rate": 0.11, "dcf_fcf_growth_5y": 0.18, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "Probe Card 細分龍頭:N2 / 18A / SF2 GAA 製程測試 + HBM3E/HBM4 測試都需要 FORM 高密度探針卡",
            "TER (Teradyne) 緊密合作:ATE 設備 + Probe Card 是測試兩條腿,FORM 是 TER 的天然搭檔",
            "AI ASIC 客製化趨勢受惠:Google TPU / AWS Trainium / Meta MTIA 訂製 ASIC 都需要 FORM 客製探針卡",
            "毛利率 45%+ FCF $100M+ 在中小型設備廠中相對穩定;mcap $4B 規模小但成長 narrative 清晰",
            "MEMS 探針技術門檻高,進入者少",
        ],
        "bear_thesis": [
            "PE / fwd PE 不算便宜 (fwd PE ~25x):中小型設備廠 fwd PE 高位易受 capex digestion 衝擊",
            "客戶集中度高:TSM + Intel + Samsung + Micron 四家佔營收 60%+",
            "mcap $4B 小型股流動性風險:風險偏好下行時跌幅放大",
            "MEMS 探針技術進入者雖少,但 TSE / MJC 等日本廠商技術接近,長線市佔壓力",
            "景氣下行時設備中小型廠先被砍倉位 (Sacks W47 2025 邏輯適用)",
        ],
        "briefing_mentions": [],
    },
    "POET": {
        "name": "POET Technologies",
        "category_label": "光電整合平台 (Optical Interposer) — CPO 早期玩家 (mcap < $1B)",
        "valuation_params": {"fwd_pe_base": 35, "fwd_pe_bull": 60, "ps_base": 20, "ev_ebitda_base": 30, "dcf_disc_rate": 0.15, "dcf_fcf_growth_5y": 0.45, "dcf_terminal_growth": 0.04},
        "bull_thesis": [
            "CPO (Co-Packaged Optics) 早期純打:NVDA Spectrum-X / Quantum-X 路線確定後,POET Optical Interposer 是上游候選技術之一",
            "mcap < $1B 微型股:若拿到任一 hyperscaler 試樣訂單,股價可漲 2-5x (Sacks W19 SaaS 大屠殺反向邏輯,小型題材股 binary)",
            "Mitsubishi / Foxconn 早期合作:大廠背書降低執行風險",
            "技術授權模式可規模化:不必自建晶圓廠,IP + design service 模式毛利率潛力 60%+",
            "AI Datacom + Telecom 雙引擎雖小但成長率 100%+",
        ],
        "bear_thesis": [
            "尚未獲利 + FCF 為負:微型股 binary risk,執行不到位股價可跌 70%+",
            "客戶集中度極高 (披露少):任一試樣失敗即影響 narrative",
            "CPO 標準仍未統一:NVDA / Broadcom / Marvell 各自押技術路線,POET 可能押錯邊",
            "mcap < $1B 流動性極差:大型機構難以進場,散戶主導波動劇烈",
            "Burry/Sacks risk-off 邏輯下,微型 AI 題材股是最早跌、跌最深的範圍",
        ],
        "briefing_mentions": [],
    },
    "SNDK": {
        "name": "Sandisk Corp",
        "category_label": "NAND 記憶體獨立廠 (從 WDC spin-off) — NAND cyclical 復甦受惠",
        "valuation_params": {"fwd_pe_base": 10, "fwd_pe_bull": 15, "ps_base": 2.5, "ev_ebitda_base": 8, "dcf_disc_rate": 0.11, "dcf_fcf_growth_5y": 0.10, "dcf_terminal_growth": 0.025},
        "bull_thesis": [
            "NAND cyclical 觸底反彈純打:NAND 價格 2026 H2 起連漲 4 個月,SNDK 是純度最高 NAND only 玩家",
            "WDC spin-off 後資產乾淨:HDD 業務剝離後 SNDK 純 NAND,估值方法簡化",
            "AI server NAND 需求結構性放大:GB200/GB300 機櫃配置高密度 SSD,enterprise NAND 訂單能見度提升",
            "fwd PE ~10x 為 memory cyclical 中段:若 2027 EPS 翻倍,股價自然 catch-up",
            "客戶分散:enterprise + mobile + consumer 三引擎,比 Micron 純度高但客戶集中度也低",
        ],
        "bear_thesis": [
            "NAND 過剩問題未根本解決:Samsung / SK Hynix / Kioxia / Micron 四強同時擴產,2027 可能再現 oversupply",
            "Burry W47 2025 邏輯適用:NAND 雖然便宜但客戶 (hyperscaler) 砍 capex 即斷崖式下滑",
            "毛利率 cyclical 波動 ±20% 區間:景氣高點到低點 EPS 可從 +$5 變 -$2",
            "技術領先性 vs Samsung/SK Hynix:200 層以上 3D NAND 量產良率挑戰,SNDK 技術領先性持平或落後",
            "WDC spin-off 後規模 disadvantage:單一玩家 R&D 投入受限",
        ],
        "briefing_mentions": [],
    },
    "NVTS": {
        "name": "Navitas Semiconductor",
        "category_label": "GaN 功率半導體 (PSU / 充電器) — AI server 800V HVDC 候選技術",
        "valuation_params": {"fwd_pe_base": 35, "fwd_pe_bull": 60, "ps_base": 12, "ev_ebitda_base": 25, "dcf_disc_rate": 0.13, "dcf_fcf_growth_5y": 0.40, "dcf_terminal_growth": 0.04},
        "bull_thesis": [
            "GaN 功率半導體純打:呼應股癌 EP671 功率半導體輪動,NVTS GaN 在 AI server PSU / 高功率充電器是純度最高的小型股",
            "AI server 800V HVDC 候選技術:GaN 在高頻 + 高效率上比 SiC 有優勢,Microsoft / Meta 都在評估 GaN PSU",
            "NVDA / Hyperscaler 試樣訂單可能催化:小型股 binary risk 但 upside 是 2-5x",
            "mcap < $1B 微型股:風險偏好上行時漲幅 vs 大型功率半導體 (ON/IFNNY/TXN) 大很多",
            "技術領先性 + Apple / 小米 / OPPO 大客戶背書:消費電子市場已驗證",
        ],
        "bear_thesis": [
            "尚未穩定獲利:微型股 binary,執行不到位 fwd PE 直接砍半",
            "客戶集中度極高:消費電子大客戶議價力強,毛利率長線壓縮",
            "SiC 與 GaN 在 AI server 戰場未定:若 hyperscaler 最終選 SiC (ON/IFNNY 主力),NVTS narrative 失血",
            "mcap 微型 + 流動性差:風險偏好下行時跌幅放大 2-3x",
            "Burry/Sacks risk-off 邏輯下,微型 AI/功率題材股是最早被砍倉位",
        ],
        "briefing_mentions": [
            {"week": "2026-W25", "category": "AI 硬體", "snippet": "股癌 EP671 + 富果 6/22:AI 伺服器破千瓦下被動 + 功率元件升級紅利。NVTS GaN 是小型純打"},
        ],
    },
    "ARM": {
        "name": "ARM Holdings",
        "category_label": "ARM 架構 IP 授權 — AI server CPU / 邊緣 AI / 車用 三引擎",
        "valuation_params": {"fwd_pe_base": 55, "fwd_pe_bull": 80, "ps_base": 30, "ev_ebitda_base": 50, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.25, "dcf_terminal_growth": 0.04},
        "bull_thesis": [
            "AI server CPU 結構性受惠:NVDA Grace (Vera) / Microsoft Cobalt / AWS Graviton 都是 ARM 架構,M觀點 W18『GPU:CPU 從 1:4 走向 1:1』直接拉動 ARM royalty",
            "NVDA RTX Spark / N1X 合作 (聯發科 W24 GTC Taipei):ARM 20 核 + Blackwell GPU 統一架構,ARM royalty 在 AI PC 也分一杯",
            "Apple Silicon / Snapdragon X / Snapdragon Auto 全押 ARM:邊緣 AI + 車用 + 手機 三引擎結構性穩固",
            "Royalty + License 雙引擎現金流穩定:毛利率 95%+ 為 software-like business,FCF $2B+",
            "Softbank 持股提供長線 narrative 支援 (孫正義 AI 主權基金背書)",
        ],
        "bear_thesis": [
            "PE / fwd PE 都極端 (fwd PE ~55x):IPO 後估值 fully priced AI server CPU 故事",
            "RISC-V 開源威脅:Linux 級別開源 ISA 競爭,中國 + 學術界推動下 2028 後可能侵蝕 ARM royalty pricing",
            "客戶議價力上升:Apple/NVDA/Microsoft 大客戶有自研空間,royalty 比例長線壓縮",
            "Softbank 持股 90%+ 流通股少:股價波動劇烈,大股東任何減持都會引發回檔",
            "Burry/Sacks risk-off 邏輯適用:fwd PE 50x+ 是被砍倉位首選",
        ],
        "briefing_mentions": [
            {"week": "2026-W18", "category": "Intel 復活", "snippet": "M觀點:Agentic AI 推升 CPU 需求,GPU:CPU 從 1:4 走向 1:1。ARM royalty 結構性放大"},
            {"week": "2026-W24", "category": "AI 算力", "snippet": "NVDA RTX Spark / N1X (聯發科) GTC Taipei:ARM 20 核 + Blackwell GPU 統一架構"},
        ],
    },
    "NOK": {
        "name": "Nokia",
        "category_label": "電信設備 + 5G/6G 基礎建設 — 衛星 + 工業專網兩條第二曲線",
        "valuation_params": {"fwd_pe_base": 15, "fwd_pe_bull": 22, "ps_base": 1.5, "ev_ebitda_base": 8, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.06, "dcf_terminal_growth": 0.02},
        "bull_thesis": [
            "5G/6G 基礎建設長期受惠美國 anti-Huawei 政策:Verizon/AT&T/T-Mobile 三大電信商 supply chain 必須有 Nokia/Ericsson 雙保",
            "工業專網 + 衛星合作 (GSAT 等):企業 LTE/5G 專網需求結構性放大,2026-2028 是 ramp 期",
            "估值便宜 (fwd PE ~15x):歐洲折價 + 電信設備 cyclical 同業低位",
            "AI Datacenter 光通訊 + 邊緣 AI 雙引擎:NVDA 5G/6G 合作 narrative 加分",
            "FCF €2B+ 穩定 + 股息殖利率 3%+:相對防禦倉位",
        ],
        "bear_thesis": [
            "成長性低:Revenue YoY 持平甚至下滑,sell-side 共識成長率僅 3-5%",
            "Ericsson 直接競爭壓力:歐洲雙雄毛利率長線壓縮",
            "中國市場流失 (Huawei 反向制裁) 雖小但長線結構性",
            "歐元/美元匯率風險 + ADR 流動性折溢價",
            "AI / 邊緣運算題材 narrative 不夠純:股價長期跑輸 SOX",
        ],
        "briefing_mentions": [],
    },
    "IRDM": {
        "name": "Iridium Communications",
        "category_label": "LEO 衛星電信 (語音 + IoT + 國防) — Starlink 之外的窄頻獨佔",
        "valuation_params": {"fwd_pe_base": 25, "fwd_pe_bull": 35, "ps_base": 5, "ev_ebitda_base": 13, "dcf_disc_rate": 0.11, "dcf_fcf_growth_5y": 0.10, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "LEO 窄頻獨佔 (語音 + IoT + Direct-to-Device):Starlink 在寬頻獨大,但 IRDM 在窄頻語音 / 國防 / IoT 上有不可替代地位",
            "Apple iPhone 衛星 SOS / Qualcomm Snapdragon Satellite 合作:Direct-to-Device 結構性受惠",
            "國防客戶結構性需求:美國國防部 / NATO / Five Eyes 都需要 Iridium 窄頻通訊",
            "毛利率 60%+ FCF $400M+ 在衛星股中相對穩定",
            "現金流穩定 + 股息回購:相對 ASTS/GSAT 兩家燒錢中,IRDM 是成熟穩定玩家",
        ],
        "bear_thesis": [
            "Starlink Direct-to-Cell 直接競爭:SpaceX 寬頻優勢若擴大到窄頻,IRDM 護城河被侵蝕",
            "fwd PE ~25x 不算便宜:成長率 5-10% 給高 PE 反映 Direct-to-Device 故事溢價",
            "衛星壽命周期 + 折舊壓力:下一代 NEXT 衛星 (2030+) 需要鉅額資本支出",
            "客戶集中度:國防 + Apple/QCOM 大客戶議價力強",
            "Sacks risk-off 邏輯下,衛星股是被砍倉位的範圍",
        ],
        "briefing_mentions": [],
    },
    "GSAT": {
        "name": "Globalstar",
        "category_label": "衛星電信 (Apple iPhone 衛星 SOS 獨家) — 微型純打",
        "valuation_params": {"fwd_pe_base": 30, "fwd_pe_bull": 60, "ps_base": 8, "ev_ebitda_base": 20, "dcf_disc_rate": 0.13, "dcf_fcf_growth_5y": 0.30, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "Apple iPhone 衛星 SOS 獨家供應 (Band 53):2022 起獨家綁定 Apple,服務遍及 18+ 國家",
            "Direct-to-Device 結構性受惠:Apple + Qualcomm 合作生態,iPhone 16/17 衛星功能擴充",
            "mcap < $3B 微型純打:Apple 任一升級即 binary upside",
            "FCC Band 53 頻譜資產:稀缺資源,潛在重估彈性",
            "Apple 持股 + 預付款結構:股權 + 業務雙重綁定降低執行風險",
        ],
        "bear_thesis": [
            "Apple 依賴度極高 (60%+):單一客戶風險集中",
            "未穩定獲利:FCF 為負或微正,微型股 binary",
            "Starlink Direct-to-Cell 競爭壓力:SpaceX 規模碾壓",
            "頻譜資產雖稀缺但 monetization 不確定",
            "mcap < $3B 流動性差,Burry/Sacks risk-off 邏輯下跌幅放大",
        ],
        "briefing_mentions": [],
    },
    "ASTS": {
        "name": "AST SpaceMobile",
        "category_label": "Direct-to-Cell 衛星 (與 AT&T/Verizon/Vodafone 合作) — Starlink 競爭者",
        "valuation_params": {"fwd_pe_base": 45, "fwd_pe_bull": 80, "ps_base": 25, "ev_ebitda_base": 35, "dcf_disc_rate": 0.14, "dcf_fcf_growth_5y": 0.50, "dcf_terminal_growth": 0.04},
        "bull_thesis": [
            "Direct-to-Cell 純打 (與標準 4G/5G 手機相容):AT&T/Verizon/Vodafone/Rakuten 大客戶背書",
            "BlueBird 衛星陣列 2026-2027 部署中:商業化 ramp 即將驗證",
            "美國政府 + 國防客戶機會:無人機 + 戰場通訊 + 北極通訊需求",
            "Sacks W47 2025 reading『主權 AI + 國家戰略物資』邏輯下,衛星通訊是受惠範圍",
            "mcap ~$15B 中型成長股,若拿到 Apple/Google 級別合作即重估 catalyst",
        ],
        "bear_thesis": [
            "尚未穩定獲利 + 高 cash burn:每年燒 $500M+ 直到 2027",
            "Starlink Direct-to-Cell 直接競爭:SpaceX 規模 + 衛星數量碾壓",
            "技術執行風險:BlueBird 大型衛星 (~700kg) 量產 + 軌道部署能力未完全驗證",
            "客戶 commitment 不確定:電信商可能轉投 Starlink",
            "fwd PE / PS 都極端 (PS > 25x):binary risk,執行不到位股價 -70%",
        ],
        "briefing_mentions": [],
    },
    "RKLB": {
        "name": "Rocket Lab",
        "category_label": "小型運載火箭 (Electron) + 中型 Neutron 開發中 — SpaceX 之外最大民營火箭",
        "valuation_params": {"fwd_pe_base": 50, "fwd_pe_bull": 80, "ps_base": 20, "ev_ebitda_base": 40, "dcf_disc_rate": 0.13, "dcf_fcf_growth_5y": 0.40, "dcf_terminal_growth": 0.04},
        "bull_thesis": [
            "SpaceX 之外最大民營火箭:Electron 累計發射數最多的小型運載火箭",
            "Neutron 中型可回收火箭 2026 試飛:成功即直接挑戰 Falcon 9,TAM 結構性放大",
            "Space Systems 業務 (衛星 + 元件) 第二曲線:不只賣火箭也賣衛星平台",
            "國防客戶結構性受惠:美國國防部 / 五角大廈 + Space Force 訂單",
            "馬斯克帝國觀察 + All-In 多次提及 RKLB 是 SpaceX 之外的『commercial space』題材純打",
        ],
        "bear_thesis": [
            "SpaceX Starlink + Starship 規模碾壓:RKLB 是『SpaceX 之外唯一』但 SpaceX 自己也在搶小型衛星發射市場",
            "Neutron 試飛 + 量產執行風險:大型火箭從 0 到 1 困難重重",
            "尚未穩定獲利:每年燒 $200M+,Neutron 量產前無 FCF",
            "fwd PE / PS 極端:已 priced in Neutron 成功",
            "Sacks risk-off 邏輯下,商業太空股是被砍倉位首選",
        ],
        "briefing_mentions": [],
    },
    "ZS": {
        "name": "Zscaler",
        "category_label": "零信任資安雲 (SASE / SSE) — 取代傳統 firewall 純打",
        "valuation_params": {"fwd_pe_base": 50, "fwd_pe_bull": 70, "ps_base": 15, "ev_ebitda_base": 40, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.22, "dcf_terminal_growth": 0.04},
        "bull_thesis": [
            "零信任資安雲純打:SASE/SSE 取代傳統 firewall + VPN 結構性故事,Gartner Magic Quadrant Leader",
            "客戶 NRR 120%+:既有客戶持續擴大採購",
            "AI agent 安全層題材 (W04 Kurtz / W24 Nikesh):agent 流量需要新一代資安檢測",
            "毛利率 78%+ FCF $700M+ best-in-class SaaS",
            "mcap $35B 中型成長股,sell-side 共識長線雙位數成長",
        ],
        "bear_thesis": [
            "Sacks W09 SaaS 大屠殺直接點名:『2/20 Claude Code Security CrowdStrike/Cloudflare/Okta 全倒』邏輯適用 ZS",
            "fwd PE >50x 高位:risk-off 期 de-rate 空間大",
            "CrowdStrike (CRWD) + Palo Alto (PANW) 競爭加劇:Platformization 戰場縮減 ZS 獨立性",
            "新興 AI-native 資安初創 (e.g. Cyera, Wiz) 挑戰底層",
            "Burry W47 2025 SaaS EPS 線性外推邏輯適用",
        ],
        "briefing_mentions": [
            {"week": "2026-W09", "category": "AI 軟體", "snippet": "Sacks SaaS 大屠殺:Claude Code Security 直接威脅 ZS/CRWD/NET/OKTA platformization"},
        ],
    },
    "NET": {
        "name": "Cloudflare",
        "category_label": "Edge Cloud + Workers AI + Zero Trust — 全棧 Edge 平台",
        "valuation_params": {"fwd_pe_base": 80, "fwd_pe_bull": 120, "ps_base": 25, "ev_ebitda_base": 60, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.28, "dcf_terminal_growth": 0.04},
        "bull_thesis": [
            "Workers AI 採用結構性放大:每月新增百萬級開發者,Cloudflare 邊緣 AI inference 純打",
            "Zero Trust + SASE 雙引擎:資安平台化故事同 ZS/PANW",
            "大客戶 (>$100K) 比重持續上升:Q3 26 共識 yoy_rev +30%",
            "Anthropic Claude / OpenAI 等 LLM 廠商部分採用 Cloudflare 作為 inference 邊緣",
            "DNS / CDN 基礎建設護城河仍在",
        ],
        "bear_thesis": [
            "Sacks W09『CrowdStrike/Cloudflare/Okta 全倒』直接點名 — Claude Code 開發者可一鍵建出對應功能",
            "fwd PE >80x 為 SaaS 中最貴之一:risk-off 期 de-rate 空間極大",
            "earnings hist_move ±18% 波動劇烈",
            "Workers AI 變現節奏 + 利潤率不確定",
            "AWS/Cloudflare/Fastly 邊緣 CDN 競爭壓力",
        ],
        "briefing_mentions": [
            {"week": "2026-W09", "category": "AI 軟體", "snippet": "Sacks SaaS 大屠殺直接點名 Cloudflare:Claude Code 一鍵建出資安功能"},
        ],
    },
    "FTNT": {
        "name": "Fortinet",
        "category_label": "資安老牌龍頭 (firewall + SD-WAN + SASE) — 估值低於 PANW/CRWD",
        "valuation_params": {"fwd_pe_base": 28, "fwd_pe_bull": 38, "ps_base": 9, "ev_ebitda_base": 22, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.13, "dcf_terminal_growth": 0.035},
        "bull_thesis": [
            "資安三巨頭中估值最便宜 (fwd PE ~30x vs CRWD 60x / PANW 40x):性價比相對防禦",
            "FortiASIC 客製化加速架構:硬體 + 軟體一體化在 firewall 領域有結構性優勢",
            "SD-WAN + SASE 平台化故事同 PANW:大企業客戶 sticky",
            "FCF $2B+ + 毛利率 80%+:cash-generative SaaS",
            "中小企業客戶基礎廣 (vs CRWD/PANW 偏大企業):景氣下行抗跌性較強",
        ],
        "bear_thesis": [
            "Sacks W09 SaaS 大屠殺擴及資安整體:FTNT 雖然便宜但 narrative 弱",
            "成長率低於同業 (10-15% vs CRWD 25%+):長線估值難以重估",
            "FortiASIC 自研 ASIC 路線若被 Cisco / Juniper 趕上,優勢消失",
            "客戶相對分散 (中小企業多) 是雙刃:景氣下行也最先砍預算",
            "AI-native 資安初創威脅 (Cyera/Wiz) 同樣適用",
        ],
        "briefing_mentions": [],
    },
    "OKTA": {
        "name": "Okta",
        "category_label": "身分驗證 (IAM / SSO) — Agentic AI 身分驗證候選層",
        "valuation_params": {"fwd_pe_base": 35, "fwd_pe_bull": 50, "ps_base": 7, "ev_ebitda_base": 25, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.15, "dcf_terminal_growth": 0.035},
        "bull_thesis": [
            "Agentic AI 身分驗證候選層 (W24 Nikesh『AI 三月內外流 wild』 + W04 Kurtz『每員工 90 agents』):agent 數量爆增直接放大 IAM TAM",
            "Workforce + Customer Identity 雙引擎:Auth0 併購後生態完整",
            "FCF $700M+ + 毛利率 75%+:cash-generative SaaS",
            "PANW 併購 IAM 公司傳聞 (W24 Nikesh『3 個月前 closed $25B identity 公司』):整體 IAM 板塊重估催化",
            "客戶分散度好 + NRR 110%+",
        ],
        "bear_thesis": [
            "Sacks W09 直接點名 OKTA:『Claude Code 一鍵建身分驗證』",
            "2022 安全事件 + 2023 客戶流失:歷史包袱 sentiment 仍在",
            "成長率放緩 (10-15% vs CRWD 25%+):長線估值難以重估",
            "AI-native IAM 初創 (Stytch / Beyond Identity) 挑戰底層",
            "Microsoft Entra ID 競爭壓力:M365 大客戶轉用 Microsoft 內建 IAM",
        ],
        "briefing_mentions": [
            {"week": "2026-W09", "category": "AI 軟體", "snippet": "Sacks 點名 OKTA 在 SaaS 大屠殺中:Claude Code 一鍵建身分驗證"},
            {"week": "2026-W24", "category": "資安", "snippet": "PANW Nikesh 揭露 $25B 收購 identity 公司 (CyberArk 級) — IAM 板塊整體重估催化"},
        ],
    },
    "S": {
        "name": "SentinelOne",
        "category_label": "AI-native EDR (Singularity Platform) — CRWD 替代選項",
        "valuation_params": {"fwd_pe_base": 60, "fwd_pe_bull": 100, "ps_base": 10, "ev_ebitda_base": 50, "dcf_disc_rate": 0.12, "dcf_fcf_growth_5y": 0.25, "dcf_terminal_growth": 0.04},
        "bull_thesis": [
            "2024/7 CRWD 大當機後客戶流失受惠:SentinelOne 是 EDR 主要替代選項,sell-side 估市佔短期 +2-3%",
            "AI-native EDR 故事 + Purple AI assistant:agent-driven SOC 自動化趨勢",
            "客戶 NRR 持續改善:近年從 110% 走到 120%+",
            "毛利率 75%+ + FCF 接近轉正",
            "mcap $7B 中小型成長股,binary upside 比 CRWD/PANW 大",
        ],
        "bear_thesis": [
            "尚未穩定獲利 + FCF 接近轉正但仍有變數",
            "CRWD 大當機紅利已 priced in,2026 H2 後再不簽單即 narrative 失血",
            "Sacks W09 SaaS 大屠殺 + Claude Code 威脅同樣適用",
            "mcap 中小型流動性風險:risk-off 期跌幅放大",
            "Microsoft Defender 競爭壓力:大企業 M365 整合 Defender,SentinelOne 中小企業客戶 sticky 但成長受限",
        ],
        "briefing_mentions": [],
    },
    "CYBR": {
        "name": "CyberArk",
        "category_label": "特權身分管理 (PAM) + 機密 / 機器身分 — 可能被 PANW 收購標的",
        "valuation_params": {"fwd_pe_base": 45, "fwd_pe_bull": 65, "ps_base": 12, "ev_ebitda_base": 35, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.20, "dcf_terminal_growth": 0.04},
        "bull_thesis": [
            "PANW Nikesh W24 揭露 $25B 收購 identity 公司 (CyberArk 級,3 個月前 closed) — CYBR 可能是收購標的或同業重估",
            "PAM (Privileged Access Management) 細分龍頭:大企業 + 政府客戶 sticky 度極高",
            "機器身分 / API 身分受 Agentic AI 拉動:agent 數量爆增直接放大機器身分 TAM",
            "Venafi 併購後機密 / 證書管理生態完整",
            "FCF $300M+ + 毛利率 80%+",
        ],
        "bear_thesis": [
            "被收購 narrative 雖好但若不被收購,fwd PE >45x 缺乏支撐",
            "Sacks W09 SaaS 大屠殺擴及身分驗證整體 (OKTA/CYBR 都點到)",
            "成長率中等 (15-20%):長線估值難以再重估",
            "Microsoft Entra Privileged Identity Management (PIM) 競爭壓力:M365 客戶可能轉用內建",
            "mcap $15B 中型流動性 OK 但 risk-off 期跌幅仍放大",
        ],
        "briefing_mentions": [
            {"week": "2026-W24", "category": "資安", "snippet": "PANW Nikesh 揭露 $25B 收購 identity 公司 (CyberArk 級) — CYBR 可能是收購標的或同業重估"},
        ],
    },
    "HPE": {
        "name": "Hewlett Packard Enterprise",
        "category_label": "企業伺服器 + AI 訓練 cluster + Juniper 併購後網路 — 全棧 AI infra",
        "valuation_params": {"fwd_pe_base": 14, "fwd_pe_bull": 20, "ps_base": 1.5, "ev_ebitda_base": 9, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.10, "dcf_terminal_growth": 0.025},
        "bull_thesis": [
            "AI 訓練 cluster 龍頭:Cray supercomputer + GreenLake 雲服務,Sandia / Oak Ridge / LANL 大型 AI/HPC 訂單",
            "Juniper 併購 (2025) 後網路 + 計算 + 儲存全棧:vs Cisco/Dell 三巨頭格局確立",
            "fwd PE ~14x 是 AI 受惠股中最便宜之一:性價比相對防禦",
            "FCF $2B+ + 股息殖利率 2.5%+",
            "中型政府 + 國防客戶 sticky 度高",
        ],
        "bear_thesis": [
            "成長率低 (5-10%):AI 雖然好但傳統企業伺服器 + 儲存業務拖累",
            "Juniper 併購整合風險:文化 + 銷售通路整合不順即影響短期業績",
            "Dell + Supermicro 直接競爭壓力:GB200/GB300 機櫃訂單三家分食",
            "客戶集中度:政府 + 大企業議價力強,毛利率長線壓縮",
            "Sacks risk-off 邏輯下,中型 AI 受惠股是被砍倉位範圍",
        ],
        "briefing_mentions": [],
    },
    "SMCI": {
        "name": "Super Micro Computer",
        "category_label": "AI 伺服器代工龍頭 — NVDA GB200/GB300 機櫃主要供應商",
        "valuation_params": {"fwd_pe_base": 18, "fwd_pe_bull": 30, "ps_base": 2, "ev_ebitda_base": 12, "dcf_disc_rate": 0.12, "dcf_fcf_growth_5y": 0.25, "dcf_terminal_growth": 0.035},
        "bull_thesis": [
            "NVDA GB200/GB300 機櫃主要組裝廠:hyperscaler 訂單能見度延伸到 2027",
            "液冷散熱技術領先 (Direct Liquid Cooling):AI 機櫃熱密度倍增,SMCI 是少數能量產的玩家",
            "FCF $1.5B+ + 毛利率回升 (15%+):從 2024 會計爭議低點修復",
            "AI 結構性 capex 紅利:Brad Gerstner / Coatue Laffont 的 $4T TAM 故事 SMCI 直接受惠",
            "fwd PE ~18x 是 AI 受惠股中最便宜之一",
        ],
        "bear_thesis": [
            "2024 會計爭議 + Hindenburg report sentiment 殘留:部分機構受託限制可能持續迴避",
            "客戶集中度極高:hyperscaler 三大 + xAI 佔營收 70%+",
            "毛利率低 (15-20%):代工模式天花板存在",
            "Dell / HPE 直接競爭壓力加大",
            "Burry/Sacks risk-off 邏輯下,AI 代工股是被砍倉位首選 (W47 2025 -20% 經驗)",
        ],
        "briefing_mentions": [],
    },
    "2382.TW": {
        "name": "廣達 Quanta",
        "category_label": "AI 伺服器 ODM 龍頭 — Meta / Google 主要客戶",
        "valuation_params": {"fwd_pe_base": 18, "fwd_pe_bull": 25, "ps_base": 1.5, "ev_ebitda_base": 12, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.18, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "AI 伺服器 ODM 龍頭 + Meta/Google 大客戶結構性受惠 hyperscaler capex",
            "GB200/GB300 機櫃 ODM 訂單能見度延伸到 2027",
            "BBU + 液冷 + 機櫃整合垂直整合度高",
            "毛利率回升 (10%+) + FCF 結構性穩定",
            "台股 50 權重 #4,外資持股穩定",
        ],
        "bear_thesis": [
            "代工模式毛利率天花板 (10-12%):利潤難擴張",
            "客戶集中度:Meta / Google / Microsoft 三家佔 AI 訂單 70%+",
            "緯創 (3231) / 鴻海 (2317) / 緯穎 (6669) 同業競爭",
            "AI capex digestion 風險:Burry/Sacks 邏輯適用",
            "新台幣升值對毛利率不利",
        ],
        "briefing_mentions": [],
    },
    "2891.TW": {
        "name": "中信金",
        "category_label": "金融類 No.1 — 台股 50 權重 #6,defensive",
        "valuation_params": {"fwd_pe_base": 12, "fwd_pe_bull": 16, "ps_base": 2, "ev_ebitda_base": 10, "dcf_disc_rate": 0.09, "dcf_fcf_growth_5y": 0.06, "dcf_terminal_growth": 0.02},
        "bull_thesis": [
            "金融類 No.1 + 多元收入 (銀行 + 壽險 + 證券)",
            "股息殖利率 4-5% defensive 倉位",
            "台灣升息 cycle 利差擴大",
            "ROE 10%+ + 配股穩定",
            "外資長期持股穩定",
        ],
        "bear_thesis": [
            "成長性低 (5-8%):AI 題材無關",
            "壽險業務利率敏感:降息 cycle 壓力",
            "外匯 / 投資部位波動",
            "金控法規限制 + 資本適足率要求",
            "Sacks risk-off 但金融股相對抗跌",
        ],
        "briefing_mentions": [],
    },
    "2412.TW": {
        "name": "中華電信",
        "category_label": "電信類 #1 — 定存替代,股價最穩",
        "valuation_params": {"fwd_pe_base": 22, "fwd_pe_bull": 26, "ps_base": 2.5, "ev_ebitda_base": 8, "dcf_disc_rate": 0.08, "dcf_fcf_growth_5y": 0.03, "dcf_terminal_growth": 0.02},
        "bull_thesis": [
            "定存替代:股息殖利率 4%+,股價波動極低",
            "電信基礎建設護城河 + 5G 滲透",
            "AI 資料中心 / 工業專網第二曲線",
            "ROE 9%+ 穩定配息",
            "Sacks risk-off 期間防禦倉位",
        ],
        "bear_thesis": [
            "成長性極低 (2-3%):長線估值難重估",
            "5G capex 高峰:折舊壓力",
            "電信競爭加劇 (台灣大 + 遠傳)",
            "AI 題材純度低",
            "fwd PE ~22x 對成長率 3% 偏貴",
        ],
        "briefing_mentions": [],
    },
    "2881.TW": {
        "name": "富邦金",
        "category_label": "金融類 #2 — 壽險為主 + 投資部位龐大",
        "valuation_params": {"fwd_pe_base": 11, "fwd_pe_bull": 15, "ps_base": 1.5, "ev_ebitda_base": 9, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.07, "dcf_terminal_growth": 0.02},
        "bull_thesis": [
            "壽險業務龍頭 + 投資部位龐大 (美股 + 台股)",
            "升息環境受惠利差擴大",
            "股息殖利率 4-5%",
            "Smart Beta + AI investment 部位優化",
            "外資長期持股穩定",
        ],
        "bear_thesis": [
            "壽險利率敏感:降息 cycle 壓力大於中信金",
            "投資部位匯損風險 (台幣升值)",
            "AI 題材無關",
            "金控法規 + 資本適足率",
            "成長性 5-8%",
        ],
        "briefing_mentions": [],
    },
    "3711.TW": {
        "name": "日月光投控 ASE",
        "category_label": "封測龍頭 — CoWoS 受惠 + 先進封裝結構性題材",
        "valuation_params": {"fwd_pe_base": 18, "fwd_pe_bull": 26, "ps_base": 1.8, "ev_ebitda_base": 12, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.15, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "封測龍頭 + CoWoS 受惠:TSMC CoWoS 擴產直接拉動 ASE OSAT 訂單",
            "先進封裝結構性故事:3D-IC / Chiplet / SiP 整合度提升",
            "NVDA / AMD / 蘋果都是大客戶",
            "毛利率 25%+ + FCF $2B+",
            "AI capex 紅利 + 客戶分散",
        ],
        "bear_thesis": [
            "代工模式毛利率天花板",
            "TSMC InFO / CoWoS 內部封裝侵蝕 ASE 高階訂單",
            "中國 OSAT (長電 / 通富) 追趕,中低階壓力",
            "AI capex digestion 風險",
            "新台幣升值不利毛利",
        ],
        "briefing_mentions": [],
    },
    "2303.TW": {
        "name": "聯電 UMC",
        "category_label": "成熟製程 (28nm/14nm) — 與 Intel 合作 + 美國 in-sourcing",
        "valuation_params": {"fwd_pe_base": 14, "fwd_pe_bull": 20, "ps_base": 2.5, "ev_ebitda_base": 9, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.08, "dcf_terminal_growth": 0.025},
        "bull_thesis": [
            "成熟製程 28nm/14nm 在 PMIC / DDIC / RF 持續有需求",
            "Intel 合作 + 美國 in-sourcing 紅利",
            "毛利率 30%+ 在純晶圓代工中相對穩定",
            "股息殖利率 5%+ defensive",
            "中國成熟製程擴產壓力但聯電技術領先",
        ],
        "bear_thesis": [
            "中國成熟製程價格戰壓力大",
            "成長性低 (5-8%):AI 純度低",
            "客戶集中度 + 訂單能見度差於 TSMC",
            "新台幣升值不利毛利",
            "8 吋產能 cyclical 風險",
        ],
        "briefing_mentions": [],
    },
    "3231.TW": {
        "name": "緯創 Wistron",
        "category_label": "AI 伺服器 ODM 主力 — GB200/Blackwell 純度高",
        "valuation_params": {"fwd_pe_base": 18, "fwd_pe_bull": 28, "ps_base": 1.8, "ev_ebitda_base": 13, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.20, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "AI server ODM 純度高:GB200/Blackwell ODM 主力之一",
            "緯穎 (6669) 為 Hyperscale 王 — 母公司價值化",
            "毛利率回升 (10%+) + FCF 結構性穩定",
            "AI capex 紅利 + 客戶分散",
            "估值便宜 (fwd PE ~18x) vs 美國 SMCI/HPE",
        ],
        "bear_thesis": [
            "代工模式毛利率天花板",
            "客戶集中度 + 緯穎稀釋母公司現金流",
            "廣達/鴻海/緯穎同業競爭",
            "AI capex digestion 風險",
            "新台幣升值不利毛利",
        ],
        "briefing_mentions": [],
    },
    "6669.TW": {
        "name": "緯穎 Wiwynn",
        "category_label": "Hyperscale ODM 龍頭 — Meta / Microsoft / AWS 主供",
        "valuation_params": {"fwd_pe_base": 20, "fwd_pe_bull": 32, "ps_base": 2.5, "ev_ebitda_base": 15, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.25, "dcf_terminal_growth": 0.04},
        "bull_thesis": [
            "Hyperscale ODM 龍頭:Meta / Microsoft / AWS 主供,AI server 純度最高台廠",
            "GB200/GB300 機櫃出貨能見度延伸到 2027",
            "毛利率 12%+ 高於同業",
            "AI capex 結構性紅利",
            "客戶 sticky 度高 + Tier-1 hyperscaler 直接合作",
        ],
        "bear_thesis": [
            "客戶集中度極高 (Meta + Microsoft 佔 60%+)",
            "fwd PE ~20x 對代工已偏貴",
            "Foxconn (鴻海 2317) 緊跟競爭",
            "Burry/Sacks risk-off 邏輯:AI 代工股是被砍倉位首選",
            "新台幣升值不利毛利",
        ],
        "briefing_mentions": [],
    },
    "2376.TW": {
        "name": "技嘉 Gigabyte",
        "category_label": "GPU 板卡 + AI 伺服器 — CSP + Tier-2 平衡",
        "valuation_params": {"fwd_pe_base": 16, "fwd_pe_bull": 24, "ps_base": 1.5, "ev_ebitda_base": 11, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.18, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "GPU 板卡 + AI 伺服器 (B100/H200) 雙引擎",
            "客戶分散 (CSP + Tier-2):AI 訂單能見度好",
            "毛利率回升 + FCF 結構性穩定",
            "AI capex 紅利",
            "估值便宜 (fwd PE ~16x)",
        ],
        "bear_thesis": [
            "GPU 板卡市場 ASUS/MSI 競爭激烈",
            "Hyperscale ODM 客戶開拓較緯穎慢",
            "毛利率天花板存在",
            "AI capex digestion 風險",
            "新台幣升值不利",
        ],
        "briefing_mentions": [],
    },
    "2356.TW": {
        "name": "英業達 Inventec",
        "category_label": "Server ODM 第三大 — NVDA HGX/MGX 出貨;NB ODM 為傳統業務",
        "valuation_params": {"fwd_pe_base": 14, "fwd_pe_bull": 22, "ps_base": 1.2, "ev_ebitda_base": 10, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.15, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "Server ODM 第三大:NVDA HGX/MGX 出貨",
            "NB ODM (HP/Lenovo) 傳統業務穩定基本盤",
            "AI 訂單能見度延伸到 2027",
            "估值便宜 (fwd PE ~14x)",
            "FCF 結構性回升",
        ],
        "bear_thesis": [
            "AI Server 訂單市佔不如廣達/緯穎",
            "NB ODM 業務 cyclical 拖累",
            "毛利率天花板 + 客戶議價力強",
            "AI capex digestion 風險",
            "新台幣升值不利",
        ],
        "briefing_mentions": [],
    },
    "4938.TW": {
        "name": "和碩 Pegatron",
        "category_label": "iPhone 二供 + AI 伺服器切入 + 汽車電子",
        "valuation_params": {"fwd_pe_base": 14, "fwd_pe_bull": 22, "ps_base": 1.0, "ev_ebitda_base": 10, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.15, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "iPhone 二供 (僅次鴻海):Apple sticky 客戶",
            "AI 伺服器切入中:多客戶分散",
            "汽車電子佈局:Tesla/特斯拉 合作",
            "估值便宜 (fwd PE ~14x)",
            "FCF 結構性回升",
        ],
        "bear_thesis": [
            "iPhone 銷量 cyclical 風險",
            "AI Server 訂單起步較廣達/緯穎慢",
            "汽車電子滲透速度慢",
            "毛利率天花板 + 客戶議價力強",
            "新台幣升值不利",
        ],
        "briefing_mentions": [],
    },
    "3017.TW": {
        "name": "奇鋐 Auras Technology",
        "category_label": "AI 液冷 + 散熱模組龍頭 — GB200/300 受惠最大",
        "valuation_params": {"fwd_pe_base": 22, "fwd_pe_bull": 35, "ps_base": 3, "ev_ebitda_base": 16, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.30, "dcf_terminal_growth": 0.04},
        "bull_thesis": [
            "AI 液冷 + 散熱模組龍頭:GB200/300 受惠最大",
            "AI 機櫃熱密度倍增直接拉動液冷 TAM",
            "非 ODM 但與廣達 / 緯穎深度綁定",
            "毛利率 25%+ 在散熱中相對高",
            "FCF + 股息成長",
        ],
        "bear_thesis": [
            "客戶集中度 (廣達 + 緯穎佔 60%+)",
            "競爭者 (3661 雙鴻 / 鋐譽) 緊追",
            "AI capex digestion 風險",
            "fwd PE ~22x 已 priced in 液冷故事",
            "新台幣升值不利",
        ],
        "briefing_mentions": [],
    },
    "2327.TW": {
        "name": "國巨 Yageo",
        "category_label": "全球被動元件第三大 (MLCC + 電阻) — AI server MLCC 滲透",
        "valuation_params": {"fwd_pe_base": 20, "fwd_pe_bull": 28, "ps_base": 3, "ev_ebitda_base": 14, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.15, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "股癌 EP671 + 富果 6/22:被動元件 → AI server MLCC 滲透紅利",
            "全球被動元件第三大 + 併購 Murata 部分產線後規模擴張",
            "AI server 用 MLCC 滲透中 + 高容值產品比重提升",
            "毛利率回升 + 客戶分散",
            "估值在歷史中段 (fwd PE ~20x)",
        ],
        "bear_thesis": [
            "被動元件 cyclical 風險:景氣下行 EPS 壓力大",
            "中國 MLCC 替代壓力 (風華高科 / 三環)",
            "Murata / Samsung Electro-Mechanics / TDK 領先地位仍穩",
            "AI capex digestion 風險",
            "新台幣升值不利",
        ],
        "briefing_mentions": [
            {"week": "2026-W25", "category": "AI 硬體", "snippet": "股癌 EP671:被動 → 功率半導體輪動。被動元件 (國巨/華新科) 仍是核心受惠者"},
            {"week": "2026-W25", "category": "AI 硬體", "snippet": "富果 6/22:AI 伺服器破千瓦下被動 + 功率元件升級紅利"},
        ],
    },
    "2492.TW": {
        "name": "華新科 Walsin",
        "category_label": "MLCC 第二大台廠 — AI server / EV 高容值產品",
        "valuation_params": {"fwd_pe_base": 18, "fwd_pe_bull": 25, "ps_base": 2.5, "ev_ebitda_base": 12, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.13, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "MLCC 第二大台廠 + AI server / EV 高容值產品比重提升",
            "股癌 EP671 + 富果 6/22 被動元件題材直接受惠",
            "毛利率回升 + FCF 結構性穩定",
            "客戶分散 (AI server + EV + 5G)",
            "估值便宜 (fwd PE ~18x)",
        ],
        "bear_thesis": [
            "規模小於國巨 (2327) + 議價力較弱",
            "被動元件 cyclical 風險",
            "中國 MLCC 替代壓力",
            "毛利率天花板存在",
            "新台幣升值不利",
        ],
        "briefing_mentions": [
            {"week": "2026-W25", "category": "AI 硬體", "snippet": "股癌 EP671:被動元件輪動。華新科 + 國巨 MLCC 雙受惠"},
        ],
    },
    "6981.T": {
        "name": "Murata 村田製作所",
        "category_label": "全球 MLCC 龍頭 (市占 ~40%) — 高階品 AI server / EV 不可替代",
        "valuation_params": {"fwd_pe_base": 22, "fwd_pe_bull": 30, "ps_base": 3, "ev_ebitda_base": 15, "dcf_disc_rate": 0.08, "dcf_fcf_growth_5y": 0.10, "dcf_terminal_growth": 0.025},
        "bull_thesis": [
            "全球 MLCC 龍頭 (市占 40%):高階 AI server / EV 不可替代",
            "iPhone 主供:Apple sticky 客戶",
            "毛利率 30%+ 在被動元件中最高",
            "FCF ¥300B+ + 股息穩定",
            "日圓貶值受惠出口",
        ],
        "bear_thesis": [
            "成長性中等 (8-12%):護城河穩但缺乏 explosive growth",
            "中國替代壓力 (風華高科 / 三環) 雖小但結構性",
            "客戶議價力強:Apple/Samsung",
            "日股流動性對美國投資人較弱 (.T 後綴)",
            "AI capex digestion 風險",
        ],
        "briefing_mentions": [
            {"week": "2026-W25", "category": "AI 硬體", "snippet": "股癌 EP671:被動元件輪動。Murata 是全球 MLCC 龍頭核心受惠"},
        ],
    },
    "6762.T": {
        "name": "TDK Corporation",
        "category_label": "MLCC + 高頻電感 + 二次電池 — iPhone 電池主供 (ATL 母公司)",
        "valuation_params": {"fwd_pe_base": 16, "fwd_pe_bull": 22, "ps_base": 1.5, "ev_ebitda_base": 10, "dcf_disc_rate": 0.09, "dcf_fcf_growth_5y": 0.10, "dcf_terminal_growth": 0.025},
        "bull_thesis": [
            "MLCC + 高頻電感 + 二次電池 三引擎",
            "ATL 子公司:iPhone 電池主供,Apple sticky",
            "AI server 用 MLCC + 電感受惠",
            "毛利率 + FCF 結構性穩定",
            "日圓貶值受惠出口",
        ],
        "bear_thesis": [
            "電池業務 cyclical (iPhone 銷量敏感)",
            "成長性中等 (8%)",
            "規模小於 Murata 整體",
            "AI capex digestion 風險",
            "日股流動性弱",
        ],
        "briefing_mentions": [],
    },
    "6976.T": {
        "name": "Taiyo Yuden 太陽誘電",
        "category_label": "MLCC 第三大廠 — 車用 + 高頻產品利基",
        "valuation_params": {"fwd_pe_base": 16, "fwd_pe_bull": 22, "ps_base": 1.5, "ev_ebitda_base": 10, "dcf_disc_rate": 0.09, "dcf_fcf_growth_5y": 0.08, "dcf_terminal_growth": 0.025},
        "bull_thesis": [
            "MLCC 第三大廠 + 車用 / 高頻利基",
            "AI server 用 MLCC 滲透",
            "毛利率穩定 + 股息",
            "客戶分散 (Apple / Samsung / 車用 / 5G)",
            "日圓貶值受惠出口",
        ],
        "bear_thesis": [
            "規模小於 Murata / SEMCO",
            "成長性中等 (5-8%)",
            "中國替代壓力",
            "AI capex digestion 風險",
            "日股流動性弱",
        ],
        "briefing_mentions": [],
    },
    "003670.KS": {
        "name": "Samsung Electro-Mechanics (SEMCO)",
        "category_label": "MLCC 全球第二 + ABF 載板第二大 — Samsung 集團 23.7% 持股",
        "valuation_params": {"fwd_pe_base": 14, "fwd_pe_bull": 20, "ps_base": 1.2, "ev_ebitda_base": 8, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.10, "dcf_terminal_growth": 0.025},
        "bull_thesis": [
            "MLCC 全球第二 (僅次 Murata) + ABF 載板第二大",
            "iPhone / Galaxy 雙供:客戶分散",
            "Samsung 集團 23.7% 持股:資源支援",
            "AI server 用 MLCC + ABF 載板雙受惠",
            "估值便宜 (fwd PE ~14x) 韓股折價",
        ],
        "bear_thesis": [
            "Samsung 集團持股雙刃:利潤可能被集團優先",
            "中國 MLCC + ABF 替代壓力",
            "AI capex digestion 風險",
            "韓圜匯率波動",
            "韓股流動性對美投資人弱",
        ],
        "briefing_mentions": [],
    },
    "6781.TW": {
        "name": "AEM-KY 富世達",
        "category_label": "AI server 連接器 / 銅纜 + 摺疊機軸承 — GB200/300 連接料受惠",
        "valuation_params": {"fwd_pe_base": 20, "fwd_pe_bull": 30, "ps_base": 3, "ev_ebitda_base": 14, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.25, "dcf_terminal_growth": 0.04},
        "bull_thesis": [
            "AI server 連接器 + 銅纜:GB200/300 連接料受惠",
            "摺疊機軸承 (Samsung Galaxy Fold) 第二曲線",
            "毛利率 30%+ 高利基產品",
            "FCF 結構性回升",
            "客戶分散 (NVDA + Samsung + Apple)",
        ],
        "bear_thesis": [
            "AI capex digestion 風險",
            "GB300 後連接料規格未定:技術轉換風險",
            "摺疊機市場成長放緩",
            "毛利率天花板存在",
            "新台幣升值不利",
        ],
        "briefing_mentions": [],
    },
    "3037.TW": {
        "name": "欣興 Unimicron",
        "category_label": "ABF 載板全球前三 — NVDA / AMD GPU 載板主供",
        "valuation_params": {"fwd_pe_base": 20, "fwd_pe_bull": 32, "ps_base": 2.5, "ev_ebitda_base": 14, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.20, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "ABF 載板全球前三 (Ibiden / SEMCO / 欣興):NVDA/AMD GPU 主供",
            "AI server capex 結構性受惠",
            "毛利率 25%+ + FCF 結構性回升",
            "客戶分散 (NVDA + AMD + Intel + 蘋果)",
            "fwd PE 在歷史中段",
        ],
        "bear_thesis": [
            "ABF 載板 cyclical 風險:Intel 2024 衝擊餘悸",
            "中國 ABF 替代壓力 (深南電路)",
            "Ibiden / SEMCO 仍領先",
            "AI capex digestion 風險",
            "新台幣升值不利",
        ],
        "briefing_mentions": [],
    },
    "8046.TW": {
        "name": "南電 Nan Ya PCB",
        "category_label": "ABF 載板高階產品 — Intel / NVDA",
        "valuation_params": {"fwd_pe_base": 22, "fwd_pe_bull": 34, "ps_base": 3, "ev_ebitda_base": 15, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.20, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "ABF 載板高階產品 (Intel/NVDA):2024 衝擊後 2025-26 訂單回溫",
            "Intel 復活紅利 (Intel 18A + EMIB) 直接拉動南電訂單",
            "M觀點 W18『Intel 復活』直接受惠",
            "毛利率 25%+ + FCF 回升",
            "AI server 訂單能見度延伸",
        ],
        "bear_thesis": [
            "Intel 依賴度過高:Intel 訂單若延後即直接影響",
            "中國 ABF 替代壓力",
            "ABF cyclical 風險",
            "AI capex digestion 風險",
            "新台幣升值不利",
        ],
        "briefing_mentions": [
            {"week": "2026-W18", "category": "Intel 復活", "snippet": "M觀點 W18:Intel +123% YTD,EMIB 後段封裝良率 90% 突破。南電作為 Intel ABF 載板供應商直接受惠"},
        ],
    },
    "3189.TW": {
        "name": "景碩 Kinsus",
        "category_label": "ABF 第三大台廠 — iPhone SiP + 高階 IC 載板",
        "valuation_params": {"fwd_pe_base": 18, "fwd_pe_bull": 28, "ps_base": 2.5, "ev_ebitda_base": 13, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.18, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "ABF 第三大台廠 + iPhone SiP",
            "高階 IC 載板:AI server + HPC 受惠",
            "毛利率回升 + FCF 結構性穩定",
            "客戶分散 (Apple + AI server)",
            "估值便宜 vs 欣興 (3037) / 南電 (8046)",
        ],
        "bear_thesis": [
            "規模小於欣興 / 南電",
            "iPhone 銷量 cyclical 風險",
            "AI capex digestion 風險",
            "中國 ABF 替代壓力",
            "新台幣升值不利",
        ],
        "briefing_mentions": [],
    },
    "5347.TWO": {
        "name": "世界先進 Vanguard Int'l",
        "category_label": "8 吋成熟製程 (PMIC / DDIC) — 與 NXP 合資新加坡 12 吋廠 (VSMC)",
        "valuation_params": {"fwd_pe_base": 16, "fwd_pe_bull": 24, "ps_base": 2.5, "ev_ebitda_base": 10, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.12, "dcf_terminal_growth": 0.025},
        "bull_thesis": [
            "8 吋成熟製程:PMIC / DDIC 持續有需求",
            "與 NXP 合資新加坡 12 吋廠 (VSMC):2027 量產後新增動能",
            "毛利率 35%+ 結構性穩定",
            "TSMC 子公司:資源支援",
            "估值便宜 (fwd PE ~16x)",
        ],
        "bear_thesis": [
            "成長性低 (5-8%)",
            "8 吋產能 cyclical 風險",
            "中國成熟製程價格戰",
            "AI 純度低",
            "新台幣升值不利",
        ],
        "briefing_mentions": [],
    },
    "3661.TW": {
        "name": "世芯-KY Alchip",
        "category_label": "AI ASIC 設計服務 — AWS Trainium 2/3 主要設計夥伴,純度極高",
        "valuation_params": {"fwd_pe_base": 30, "fwd_pe_bull": 50, "ps_base": 8, "ev_ebitda_base": 22, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.35, "dcf_terminal_growth": 0.04},
        "bull_thesis": [
            "AI ASIC 設計服務:AWS Trainium 2/3 主要設計夥伴,純度極高",
            "Chamath W21:ASIC 滲透 2026-2028 從 15% → 30% — 世芯直接受惠",
            "聯發科 (2454) + 世芯雙台廠 ASIC 設計服務龍頭",
            "毛利率 30%+ + FCF 結構性放大",
            "估值雖貴但成長率 35%+ catch-up",
        ],
        "bear_thesis": [
            "客戶集中度極高 (AWS 佔 60%+)",
            "Trainium 訂單能見度依 AWS",
            "fwd PE ~30x 已 priced in ASIC 故事",
            "AI capex digestion 風險",
            "Burry/Sacks risk-off 邏輯下,ASIC 設計股是被砍倉位首選",
        ],
        "briefing_mentions": [
            {"week": "2026-W21", "category": "AI 算力", "snippet": "Chamath W21:ASIC 滲透 2026-2028 從 15% → 30%。世芯 (3661) AWS Trainium 主要設計夥伴直接受惠"},
        ],
    },
    "6285.TW": {
        "name": "啟碁 Wistron NeWeb",
        "category_label": "Starlink 用戶終端 (UT) ODM 主供 — LEO 純度最高台廠",
        "valuation_params": {"fwd_pe_base": 18, "fwd_pe_bull": 28, "ps_base": 1.5, "ev_ebitda_base": 11, "dcf_disc_rate": 0.10, "dcf_fcf_growth_5y": 0.25, "dcf_terminal_growth": 0.03},
        "bull_thesis": [
            "Starlink 用戶終端 (UT) ODM 主供:LEO 純度最高台廠",
            "緯創 (3231) 子公司:母公司資源 + AI server 同步",
            "Starlink 用戶數從 4M → 10M 目標直接拉動 UT 訂單",
            "毛利率回升 + FCF 結構性穩定",
            "AI + 衛星雙引擎",
        ],
        "bear_thesis": [
            "客戶 SpaceX 單一依賴度高 (40%+)",
            "Starlink Direct-to-Cell 若降低 UT 依賴,啟碁訂單壓力",
            "新台幣升值不利",
            "AI capex + 衛星雙 cyclical 風險",
            "競爭者 (3491 昇達科) 切入",
        ],
        "briefing_mentions": [],
    },
    "3491.TW": {
        "name": "昇達科 SDT",
        "category_label": "毫米波被動元件 + 衛星地面站射頻 — SpaceX 供應鏈傳聞",
        "valuation_params": {"fwd_pe_base": 25, "fwd_pe_bull": 40, "ps_base": 5, "ev_ebitda_base": 18, "dcf_disc_rate": 0.11, "dcf_fcf_growth_5y": 0.30, "dcf_terminal_growth": 0.04},
        "bull_thesis": [
            "毫米波被動元件 + 衛星地面站射頻:SpaceX 供應鏈傳聞",
            "5G/6G + 衛星 + 國防三引擎",
            "毛利率高 (40%+) 在被動元件中相對高",
            "客戶分散 + 高階利基",
            "AI 邊緣運算 + 6G narrative 加分",
        ],
        "bear_thesis": [
            "mcap 小型流動性風險",
            "SpaceX 供應鏈傳聞未驗證",
            "成長率高但 binary risk",
            "新台幣升值不利",
            "Sacks risk-off 邏輯下,小型衛星題材股先被砍",
        ],
        "briefing_mentions": [],
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

    # 7. ROE 調整基準值 (PBR-ROE 法,參考 taiquant 釣魚分區邏輯 + 調整倍數以反映美股 mega-cap 高 P/B)
    #    taiquant 原始公式 ×10 適合台股穩健公司,但美股 mega-cap (NVDA P/B 26 / AAPL 41)
    #    需要更高倍數才能反映成長股估值現實:
    #    高 ROE 公司:NAV × ROE × 20
    #    中 ROE:     NAV × 2
    #    低 ROE:     NAV × (ROE + 0.02) × 15
    info = raw["info"]
    book_value_ps = safe_float(info.get("bookValue"))
    roe = safe_float(info.get("returnOnEquity"))
    # 跳過跨幣值 (TSM ADR) — bookValue 是 financial currency,股價是 stock currency
    # 跳過 ROE <= 0 (重組期 / 虧損)
    if book_value_ps and roe is not None and roe > 0 and not ccy_mismatch:
        if roe >= 0.10:
            roe_base = book_value_ps * roe * 20
            roe_note = f"高 ROE 法:NAV ${book_value_ps:.1f} × ROE {roe*100:.1f}% × 20"
        elif roe >= 0.08:
            roe_base = book_value_ps * 2
            roe_note = f"中 ROE 法:NAV ${book_value_ps:.1f} × 2"
        else:
            roe_base = book_value_ps * (roe + 0.02) * 15
            roe_note = f"低 ROE 法:NAV ${book_value_ps:.1f} × (ROE+2%) × 15"
        models.append({
            "model": "ROE 調整基準值 (PBR-ROE)",
            "implied_price": round(roe_base, 2),
            "rationale": roe_note + " — 高 ROE 才配高 P/B,低 ROE 給折價 (反映美股 mega-cap 估值)",
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

    # 魚體區計算 (參考 taiquant): 以 ROE 調整基準值 (PBR-ROE 模型) 為錨點
    # 沒 ROE 模型 fallback 用 analyst median target
    # 倍數從 ×10 調到 ×20 反映美股 mega-cap P/B (NVDA 26 / AAPL 41 等遠超 taiquant 台股設定)
    book_value_ps = safe_float(info.get("bookValue"))
    roe = safe_float(info.get("returnOnEquity"))
    stock_ccy = str(info.get("currency", "") or "")
    fin_ccy = str(info.get("financialCurrency", "") or "")
    ccy_mismatch = stock_ccy and fin_ccy and stock_ccy != fin_ccy

    roe_base = None
    # 跳過跨幣值 (e.g. TSM ADR) — bookValue 是 financial currency,跟 stock price 比不對等
    # 跳過 ROE <= 0 (重組期 / 虧損) — 公式會給負值
    if book_value_ps and roe is not None and roe > 0 and not ccy_mismatch:
        if roe >= 0.10:
            roe_base = book_value_ps * roe * 20
        elif roe >= 0.08:
            roe_base = book_value_ps * 2
        else:
            roe_base = book_value_ps * (roe + 0.02) * 15

    benchmark_base = roe_base if roe_base else base
    # 計算 5 段魚體區邊界
    band_thresholds = {
        "head_low":   benchmark_base * 0.85,   # 魚頭區下緣
        "body_low":   benchmark_base * 1.00,   # 魚身區下緣
        "tail_low":   benchmark_base * 1.15,   # 魚尾區下緣
        "bone_low":   benchmark_base * 1.30,   # 魚骨區下緣
        "crazy_low":  benchmark_base * 2.00,   # 瘋狂區下緣
    }
    # 當前價落哪個區
    if current_price < band_thresholds["head_low"]:
        price_band = "below_head"
        price_band_label = "魚頭區以下 (深度低估)"
    elif current_price < band_thresholds["body_low"]:
        price_band = "head"
        price_band_label = "魚頭區 (低估)"
    elif current_price < band_thresholds["tail_low"]:
        price_band = "body"
        price_band_label = "魚身區 (合理)"
    elif current_price < band_thresholds["bone_low"]:
        price_band = "tail"
        price_band_label = "魚尾區 (略貴)"
    elif current_price < band_thresholds["crazy_low"]:
        price_band = "bone"
        price_band_label = "魚骨區 (過熱)"
    else:
        price_band = "crazy"
        price_band_label = "瘋狂區 (泡沫)"

    # discount %:當前價 vs 基準值
    discount_pct = round((current_price - benchmark_base) / benchmark_base * 100, 1) if benchmark_base else 0

    return {
        "ticker": symbol,
        "name": cfg["name"],
        "category_label": cfg["category_label"],
        "updated_at": date.today().isoformat(),
        "current_price": current_price,
        "currency": str(info.get("currency", "USD")),
        "financial_currency": str(info.get("financialCurrency", "USD")),
        "benchmark_base": round(benchmark_base, 2),
        "benchmark_source": "PBR-ROE" if roe_base else "Analyst Median",
        "price_band": price_band,
        "price_band_label": price_band_label,
        "discount_pct": discount_pct,
        "band_thresholds": {k: round(v, 2) for k, v in band_thresholds.items()},
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
