"""
fetch_allin.py — 批次抓 All-In Podcast YouTube 字幕

跟 transcribe.py 不同:這個專做 All-In 頻道,批次處理多集。

使用:
  pip install --user yt-dlp
  python fetch_allin.py                     # 抓今年至今所有集
  python fetch_allin.py --year 2026         # 只抓 2026
  python fetch_allin.py --limit 10          # 只抓最近 N 集
  python fetch_allin.py --refresh           # 強制重抓 (即使 .txt 已存在)

輸出:
  transcripts/allin/EP{id}_{slug}.txt          純文字逐字稿
  transcripts/allin/EP{id}_{slug}.meta.json    {title, upload_date, duration, url}
  transcripts/allin/index.json                 全部已抓集數 metadata
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, date
from pathlib import Path

ROOT = Path(__file__).parent
OUT_DIR = ROOT / "transcripts" / "allin"
CHANNEL_URL = "https://www.youtube.com/@allin/videos"


def _find_yt_dlp() -> str:
    p = shutil.which("yt-dlp") or shutil.which("yt-dlp.exe")
    if p:
        return p
    win_path = Path.home() / "AppData/Roaming/Python/Python312/Scripts/yt-dlp.exe"
    if win_path.exists():
        return str(win_path)
    print("❌ 找不到 yt-dlp。請: pip install --user yt-dlp", file=sys.stderr)
    sys.exit(1)


YT_DLP = _find_yt_dlp()


def slugify(text: str, max_len: int = 60) -> str:
    t = re.sub(r"[^\w一-鿿\-_.]+", "-", text or "untitled", flags=re.UNICODE)
    t = re.sub(r"-+", "-", t).strip("-")
    return t[:max_len] or "untitled"


def list_channel_videos(limit: int = 100) -> list[dict]:
    """列頻道最近 N 集 (含 upload_date) — 用 --print 而非 --flat-playlist"""
    print(f"📡 列頻道 {limit} 集 (這需要 1-2 分鐘抓 metadata)...")
    cmd = [YT_DLP, "--print", "%(id)s|%(title)s|%(upload_date)s|%(duration)s",
           "--playlist-end", str(limit), "--no-download", CHANNEL_URL]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600, encoding="utf-8")
    videos = []
    for line in (r.stdout or "").splitlines():
        if line.startswith("WARNING") or "|" not in line:
            continue
        parts = line.strip().split("|")
        if len(parts) < 4:
            continue
        vid, title, upload, dur = parts[0], parts[1], parts[2], parts[3]
        try:
            upload_dt = datetime.strptime(upload, "%Y%m%d").date() if upload != "NA" else None
        except Exception:
            upload_dt = None
        videos.append({
            "id": vid,
            "title": title,
            "upload_date": upload_dt.isoformat() if upload_dt else "",
            "duration": int(float(dur)) if dur and dur != "NA" else 0,
        })
    print(f"   ✓ 拿到 {len(videos)} 集")
    return videos


def fetch_subs(vid: str, slug: str, out_dir: Path) -> Path | None:
    """抓自動字幕 → vtt → txt。回傳 .txt 路徑或 None"""
    out_template = str(out_dir / f"EP{vid}_{slug}.%(ext)s")
    cmd = [YT_DLP, "--write-auto-sub", "--sub-lang", "en,en-US,en-GB",
           "--sub-format", "vtt", "--skip-download", "--no-playlist",
           "-o", out_template, f"https://www.youtube.com/watch?v={vid}"]
    subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    vtt = next(out_dir.glob(f"EP{vid}_{slug}*.vtt"), None)
    if not vtt:
        return None
    # vtt → txt
    text_lines, last = [], ""
    skip_header = True
    for raw in vtt.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if skip_header:
            if line == "" or line.startswith(("WEBVTT", "Kind:", "Language:", "NOTE")):
                continue
            skip_header = False
        if not line or "-->" in line or line.isdigit():
            continue
        clean = re.sub(r"<[^>]+>", "", line)
        clean = re.sub(r"&\w+;", " ", clean).strip()
        if not clean or clean == last:
            continue
        text_lines.append(clean)
        last = clean
    txt = out_dir / f"EP{vid}_{slug}.txt"
    txt.write_text("\n".join(text_lines), encoding="utf-8")
    vtt.unlink(missing_ok=True)  # 不留 vtt
    return txt


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--year", type=int, help="只抓指定年份")
    ap.add_argument("--limit", type=int, default=150, help="從頻道列幾集當候選 (預設 150)")
    ap.add_argument("--refresh", action="store_true", help="強制重抓即使 .txt 已存在")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    videos = list_channel_videos(args.limit)
    if args.year:
        videos = [v for v in videos if v["upload_date"].startswith(str(args.year))]
        print(f"🎯 過濾 {args.year}: {len(videos)} 集")
    else:
        today = date.today()
        videos = [v for v in videos if v["upload_date"].startswith(str(today.year))]
        print(f"🎯 過濾今年 ({today.year}): {len(videos)} 集")

    written, skipped = 0, 0
    for i, v in enumerate(videos, 1):
        slug = slugify(v["title"])
        target = OUT_DIR / f"EP{v['id']}_{slug}.txt"
        if target.exists() and not args.refresh:
            skipped += 1
            continue
        print(f"[{i}/{len(videos)}] {v['upload_date']} {v['title'][:60]}")
        try:
            txt = fetch_subs(v["id"], slug, OUT_DIR)
            if txt:
                # 寫 meta
                meta_path = OUT_DIR / f"EP{v['id']}_{slug}.meta.json"
                meta_path.write_text(json.dumps({
                    **v, "url": f"https://www.youtube.com/watch?v={v['id']}",
                }, ensure_ascii=False, indent=2), encoding="utf-8")
                written += 1
                print(f"   ✓ {txt.stat().st_size // 1024} KB")
            else:
                print(f"   ✗ 沒字幕")
        except Exception as e:
            print(f"   ✗ {e}", file=sys.stderr)

    # 寫 index
    index = []
    for meta_file in sorted(OUT_DIR.glob("*.meta.json")):
        try:
            m = json.loads(meta_file.read_text(encoding="utf-8"))
            txt_path = meta_file.with_suffix("").with_suffix(".txt")
            if txt_path.exists():
                m["tx_len"] = txt_path.stat().st_size
                m["txt_file"] = txt_path.name
                index.append(m)
        except Exception:
            pass
    index.sort(key=lambda x: x.get("upload_date", ""), reverse=True)
    (OUT_DIR / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"\n✅ 寫入 {written} 集 + skip {skipped} 集已存在")
    print(f"📇 index.json: {len(index)} 集")


if __name__ == "__main__":
    main()
