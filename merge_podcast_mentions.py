"""
merge_podcast_mentions.py — 把 All-In 2026 podcast extract (5 batches) 合併進 data.json

Schema (寫進 data.json["podcast_mentions"]):
  {
    "by_week": {
      "2026-W22": [
        {"podcast": "All-In", "category": "AI 軟體", "title": "...",
         "tickers": ["ANTH","GS",...], "summary": "...",
         "stance": "...", "implication": "...",
         "themes": ["AI 軟體/平台",...]}
      ],
      ...
    },
    "by_ticker": {
      "NVDA": [{"week":"2026-W22","podcast":"All-In","title":"...","snippet":"..."}],
      ...
    }
  }
"""
from __future__ import annotations

import json
from pathlib import Path

BATCH_DIR = Path.home() / "AppData" / "Local" / "Temp" / "allin_batches"
DATA_FILE = Path(__file__).parent / "data.json"


def load_batches() -> dict[str, dict]:
    """Returns {W02: {...}, W03: {...}, ...}"""
    out = {}
    for f in sorted(BATCH_DIR.glob("batch*.json")):
        out.update(json.loads(f.read_text(encoding="utf-8")))
    return out


def build_podcast_mentions(weeks: dict[str, dict]) -> dict:
    by_week: dict[str, list] = {}
    by_ticker: dict[str, list] = {}

    for wkey, w in weeks.items():
        # W02 → 2026-W02
        week_id = f"2026-{wkey}"
        entry = {
            "podcast": "All-In",
            "category": w.get("category", ""),
            "title": w.get("title", ""),
            "tickers": w.get("tickers", []),
            "summary": w.get("summary", ""),
            "stance": w.get("stance", ""),
            "implication": w.get("implication", ""),
            "themes": w.get("themes_touched", []),
        }
        by_week.setdefault(week_id, []).append(entry)

        snippet = w.get("title", "")[:120]
        for t in w.get("tickers", []):
            by_ticker.setdefault(t, []).append({
                "week": week_id,
                "podcast": "All-In",
                "category": w.get("category", ""),
                "title": w.get("title", ""),
                "snippet": snippet,
            })

    return {"by_week": by_week, "by_ticker": by_ticker}


def main() -> None:
    weeks = load_batches()
    print(f"Loaded {len(weeks)} weeks from {BATCH_DIR}")

    mentions = build_podcast_mentions(weeks)
    print(f"by_week: {len(mentions['by_week'])} weeks")
    print(f"by_ticker: {len(mentions['by_ticker'])} unique tickers")
    top = sorted(mentions['by_ticker'].items(), key=lambda kv: -len(kv[1]))[:10]
    print(f"top tickers: {[(k, len(v)) for k, v in top]}")

    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    data["podcast_mentions"] = mentions
    DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Written to {DATA_FILE}")


if __name__ == "__main__":
    main()
