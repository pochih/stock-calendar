"""
fetch_gooaye.py — 從 whatmkreallysaid.com 抓股癌全集逐字稿

來源:
  https://whatmkreallysaid.com/transcripts.json.br
  (10MB brotli, 671 集, 含 Whisper.cpp + Claude 後處理)

格式 (每集):
  n    集數 (int)
  t    標題
  d    日期 YYYY-MM-DD
  dt   顯示日期 (e.g. "Jun 17, 2026")
  desc 摘要 (200-500 字)
  tx   完整 markdown 逐字稿 (含 ## 章節分段)

輸出:
  transcripts/gooaye/EP{n}.md       完整逐字稿 (含 YAML frontmatter)
  transcripts/gooaye/index.json     集數索引 (n/t/d/desc, 不含 tx)

使用:
  pip install --user brotli
  python fetch_gooaye.py                # 抓全部 671 集
  python fetch_gooaye.py --classics     # 只抓 11 集經典 (省 disk)
  python fetch_gooaye.py --since 600    # 只抓 EP600 之後
  python fetch_gooaye.py --refresh      # 強制重抓 pack (預設 cache)
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
OUT_DIR = ROOT / "transcripts" / "gooaye"
PACK_URL = "https://whatmkreallysaid.com/transcripts.json.br"
MANIFEST_URL = "https://whatmkreallysaid.com/pack_manifest.json"
CACHE_PACK = OUT_DIR / "_cache.transcripts.json"
CACHE_MANIFEST = OUT_DIR / "_cache.manifest.json"

# 11 集經典 (從首頁 details.classics 抓出)
CLASSICS = [20, 57, 102, 117, 169, 180, 260, 275, 327, 339, 550]


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 stock-calendar/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def load_or_fetch_pack(refresh: bool) -> list[dict]:
    """抓 brotli pack,解壓,cache 一份未壓縮版到本地"""
    try:
        import brotli  # type: ignore
    except ImportError:
        print("❌ 需要 brotli 套件: pip install --user brotli", file=sys.stderr)
        sys.exit(1)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    if CACHE_PACK.exists() and not refresh:
        print(f"📦 從 cache 載入: {CACHE_PACK.name}")
        return json.loads(CACHE_PACK.read_text(encoding="utf-8"))

    print(f"📡 下載 manifest...")
    manifest = json.loads(http_get(MANIFEST_URL).decode("utf-8"))
    CACHE_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"   version: {manifest['version']}  集數: {manifest['episode_count']}  "
          f"pack: {manifest['transcripts']['brotli_bytes'] / 1e6:.1f}MB (br)")

    print(f"⬇️  下載 brotli pack ({manifest['transcripts']['brotli_bytes'] / 1e6:.1f}MB)...")
    br_bytes = http_get(PACK_URL)
    print(f"🗜️  解壓 brotli...")
    raw = brotli.decompress(br_bytes)
    print(f"   解出 {len(raw) / 1e6:.1f}MB")

    eps = json.loads(raw)
    # cache 一份未壓縮 (37MB) 方便下次快速 reload + diff
    CACHE_PACK.write_text(json.dumps(eps, ensure_ascii=False), encoding="utf-8")
    print(f"💾 cache 已存 {CACHE_PACK.name}")
    return eps


def write_episode_md(ep: dict, out_dir: Path) -> Path:
    """把單集寫成 markdown,加 YAML frontmatter"""
    n = ep["n"]
    fname = f"EP{n:03d}.md"  # 補零讓檔案排序整齊
    path = out_dir / fname

    frontmatter = [
        "---",
        f"episode: {n}",
        f"title: {json.dumps(ep['t'], ensure_ascii=False)}",
        f"date: {ep['d']}",
        f"display_date: {json.dumps(ep['dt'], ensure_ascii=False)}",
        f"description: {json.dumps(ep['desc'], ensure_ascii=False)}",
        f"source: https://whatmkreallysaid.com/episode?file=EP{n}_xxx.md",
        "---",
        "",
    ]
    body = ep["tx"]
    path.write_text("\n".join(frontmatter) + body + "\n", encoding="utf-8")
    return path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--classics", action="store_true", help="只抓 11 集經典")
    ap.add_argument("--since", type=int, help="只抓 EP>=N (e.g. 600)")
    ap.add_argument("--episodes", help="只抓指定集數,逗號分隔 (e.g. 671,670,550)")
    ap.add_argument("--refresh", action="store_true", help="強制重抓 pack")
    ap.add_argument("--out", default=str(OUT_DIR), help="輸出目錄")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    eps = load_or_fetch_pack(args.refresh)
    print(f"\n📚 pack 共 {len(eps)} 集")

    # 篩選
    if args.classics:
        wanted = set(CLASSICS)
        eps = [e for e in eps if e["n"] in wanted]
        print(f"🎯 篩 11 集經典 → {len(eps)} 集")
    elif args.episodes:
        wanted = {int(x.strip()) for x in args.episodes.split(",")}
        eps = [e for e in eps if e["n"] in wanted]
        print(f"🎯 篩指定集數 → {len(eps)} 集")
    elif args.since:
        eps = [e for e in eps if e["n"] >= args.since]
        print(f"🎯 篩 EP{args.since}+ → {len(eps)} 集")

    if not eps:
        print("❌ 沒有符合條件的集數")
        sys.exit(1)

    print(f"\n✍️  寫入 markdown...")
    written = 0
    for ep in eps:
        p = write_episode_md(ep, out_dir)
        written += 1
        if written <= 5 or written % 50 == 0:
            print(f"   ✓ {p.name}  EP{ep['n']:>4d}  {ep['t'][:40]}")
    if written > 5:
        print(f"   ... 共 {written} 集")

    # 寫 index.json (不含 tx,給 dashboard 用)
    # 注意:寫的是「pack 全集」index,不只 filter 後的子集
    all_eps = json.loads(CACHE_PACK.read_text(encoding="utf-8"))
    index = [
        {"n": e["n"], "t": e["t"], "d": e["d"], "desc": e["desc"], "tx_len": len(e.get("tx", ""))}
        for e in all_eps
    ]
    idx_path = out_dir / "index.json"
    idx_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n📇 寫入 index: {idx_path.name} ({len(index)} 集)")
    print(f"\n✅ 完成 {written} 集 → {out_dir}")


if __name__ == "__main__":
    main()
