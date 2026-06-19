"""
transcribe.py — 抓 podcast / YouTube 影片字幕或轉錄為純文字

使用情境:
  1. All-In Podcast (英文 YouTube)        → 抓自動字幕,幾秒搞定
  2. 股癌 (中文,SoundOn/Apple/Spotify)    → 抓音檔 + Whisper 轉錄

需要的套件:
  pip install --user yt-dlp
  pip install --user openai-whisper   # 只在用 --whisper 時需要
  ffmpeg                              # whisper 必須(系統層裝)

範例:
  # 1. YouTube + 自動字幕 (最快)
  python transcribe.py "https://youtu.be/XXXX" --lang en

  # 2. YouTube + Whisper (字幕不夠好時)
  python transcribe.py "https://youtu.be/XXXX" --whisper --lang zh

  # 3. 純音檔 podcast (股癌 SoundOn 等)
  python transcribe.py "https://feeds.soundon.fm/.../episode.mp3" --whisper --lang zh

  # 4. 給提示字 (提升中文專有名詞辨識)
  python transcribe.py URL --whisper --lang zh \\
      --initial-prompt "台積電,輝達,聯發科,鴻海,日月光,SoIC,CoWoS"

旗標:
  --lang LANG          語言代碼 (en / zh / zh-TW / zh-CN);影響字幕優先順序與 Whisper
  --whisper            強制用 Whisper 轉錄(否則優先抓 YouTube 字幕)
  --model MODEL        Whisper 模型: tiny / base / small / medium / large-v3 (預設 large-v3)
  --initial-prompt P   給 Whisper 的引導字 (專有名詞清單,提升辨識率)
  --out DIR            輸出目錄 (預設 ./transcripts)
  --keep-audio         保留下載的 .mp3 (預設轉錄完刪除)
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent
DEFAULT_OUT = ROOT / "transcripts"

# yt-dlp 不一定在 PATH 上(pip install --user 後 Windows 常見問題),所以先找
def _find_yt_dlp() -> str:
    for cand in ("yt-dlp", "yt-dlp.exe"):
        p = shutil.which(cand)
        if p:
            return p
    # Windows pip install --user 預設位置
    win_path = Path.home() / "AppData/Roaming/Python/Python312/Scripts/yt-dlp.exe"
    if win_path.exists():
        return str(win_path)
    print("❌ 找不到 yt-dlp。請執行: pip install --user yt-dlp", file=sys.stderr)
    sys.exit(1)


YT_DLP = _find_yt_dlp()


def _find_ffmpeg() -> Optional[str]:
    """優先用系統 ffmpeg;沒有則 fallback 到 imageio-ffmpeg 自帶的 binary"""
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg  # type: ignore
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        return None


FFMPEG = _find_ffmpeg()
if FFMPEG:
    # 把 ffmpeg 所在目錄塞到 PATH 最前面,讓 Whisper 也找得到
    import os as _os
    _os.environ["PATH"] = str(Path(FFMPEG).parent) + _os.pathsep + _os.environ.get("PATH", "")


def slugify(text: str, max_len: int = 80) -> str:
    """把標題變成檔名安全的 slug"""
    t = re.sub(r"[^\w一-鿿\-_.]+", "-", text, flags=re.UNICODE)
    t = re.sub(r"-+", "-", t).strip("-")
    return t[:max_len] or "untitled"


def fetch_metadata(url: str) -> dict:
    """用 yt-dlp 拉 metadata (標題、上傳者、時長)"""
    print(f"📡 抓 metadata: {url}")
    result = subprocess.run(
        [YT_DLP, "--dump-json", "--no-playlist", "--skip-download", url],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode != 0:
        print(f"⚠️  metadata 抓取失敗: {result.stderr[:200]}", file=sys.stderr)
        return {"title": "untitled", "uploader": "?", "duration": 0}
    try:
        data = json.loads(result.stdout.splitlines()[0])
        return {
            "title": data.get("title", "untitled"),
            "uploader": data.get("uploader", "?"),
            "duration": data.get("duration", 0),
            "upload_date": data.get("upload_date", ""),
            "id": data.get("id", ""),
        }
    except Exception as e:
        print(f"⚠️  metadata 解析失敗: {e}", file=sys.stderr)
        return {"title": "untitled", "uploader": "?", "duration": 0}


def try_youtube_subs(url: str, lang: str, out_dir: Path, slug: str) -> Optional[Path]:
    """
    優先策略:
      1. 抓人工字幕 --write-sub  (品質最高)
      2. 退而求其次抓自動字幕 --write-auto-sub
    成功回傳 .vtt 路徑;失敗回 None。
    """
    out_template = str(out_dir / f"{slug}.%(ext)s")
    # 候選語言 (依優先順序);Whisper 用 zh,YouTube 用 zh-TW/zh-CN/zh-Hant
    if lang == "zh":
        sub_langs = "zh-TW,zh-Hant,zh-CN,zh-Hans,zh"
    elif lang == "en":
        sub_langs = "en,en-US,en-GB"
    else:
        sub_langs = lang

    # 試人工字幕
    print(f"🔍 試抓人工字幕 ({sub_langs})...")
    cmd = [YT_DLP, "--write-sub", "--sub-lang", sub_langs, "--sub-format", "vtt",
           "--skip-download", "--no-playlist", "-o", out_template, url]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    vtt = next(out_dir.glob(f"{slug}*.vtt"), None)
    if vtt:
        print(f"   ✓ 拿到人工字幕: {vtt.name}")
        return vtt

    # 退到自動字幕
    print(f"🔍 試抓自動字幕 ({sub_langs})...")
    cmd = [YT_DLP, "--write-auto-sub", "--sub-lang", sub_langs, "--sub-format", "vtt",
           "--skip-download", "--no-playlist", "-o", out_template, url]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    vtt = next(out_dir.glob(f"{slug}*.vtt"), None)
    if vtt:
        print(f"   ✓ 拿到自動字幕: {vtt.name}")
        return vtt

    print("   ✗ 沒有可用字幕")
    return None


def vtt_to_text(vtt_path: Path) -> str:
    """剝掉 vtt 的時間戳/編號/標籤,只留純文字。同行去重(自動字幕常 rolling 重複)"""
    text_lines: list[str] = []
    last_line = ""
    skip_header = True
    for raw in vtt_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if skip_header:
            if line == "" or line.startswith("WEBVTT") or line.startswith("Kind:") \
                    or line.startswith("Language:") or line.startswith("NOTE"):
                continue
            skip_header = False
        if not line:
            continue
        if "-->" in line:
            continue
        if line.isdigit():  # cue number
            continue
        # 移除 inline 標籤 <c>, <00:00:00.000>, &nbsp; 等
        clean = re.sub(r"<[^>]+>", "", line)
        clean = re.sub(r"&\w+;", " ", clean).strip()
        if not clean:
            continue
        if clean == last_line:  # 自動字幕 rolling 去重
            continue
        text_lines.append(clean)
        last_line = clean
    return "\n".join(text_lines)


def download_audio(url: str, out_dir: Path, slug: str) -> Path:
    """抓最佳音質、轉成 mp3 (Whisper 喜歡 16kHz mono,但 mp3 也可以)"""
    out_template = str(out_dir / f"{slug}.%(ext)s")
    print(f"⬇️  下載音檔...")
    cmd = [YT_DLP, "-x", "--audio-format", "mp3", "--audio-quality", "0",
           "--no-playlist", "-o", out_template, url]
    if FFMPEG:
        cmd += ["--ffmpeg-location", FFMPEG]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        print(f"❌ 音檔下載失敗:\n{r.stderr[:500]}", file=sys.stderr)
        sys.exit(1)
    mp3 = next(out_dir.glob(f"{slug}*.mp3"), None)
    if not mp3:
        print("❌ 找不到下載的 mp3", file=sys.stderr)
        sys.exit(1)
    print(f"   ✓ {mp3.name} ({mp3.stat().st_size / 1e6:.1f} MB)")
    return mp3


def whisper_transcribe(
    audio_path: Path, lang: str, model: str, initial_prompt: Optional[str], out_dir: Path
) -> Path:
    """跑 Whisper 轉錄,輸出 .txt"""
    try:
        import whisper  # type: ignore
    except ImportError:
        print("❌ Whisper 未安裝。請執行: pip install --user openai-whisper", file=sys.stderr)
        print("   並確認 ffmpeg 已安裝在 PATH 上", file=sys.stderr)
        sys.exit(1)

    print(f"🎧 載入 Whisper 模型: {model} (首次會下載 ~3GB for large-v3)")
    m = whisper.load_model(model)

    print(f"🎙️  轉錄中... ({audio_path.name},語言={lang})")
    if initial_prompt:
        print(f"   提示詞: {initial_prompt[:80]}{'...' if len(initial_prompt) > 80 else ''}")

    result = m.transcribe(
        str(audio_path),
        language=lang if lang in ("zh", "en", "ja", "ko") else None,
        initial_prompt=initial_prompt,
        verbose=False,
        fp16=False,  # CPU 跑時必須 False
    )

    txt_path = out_dir / (audio_path.stem + ".txt")
    txt_path.write_text(result["text"].strip(), encoding="utf-8")
    print(f"   ✓ 寫入 {txt_path.name} ({len(result['text']):,} chars)")
    return txt_path


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", help="YouTube / Podcast URL")
    ap.add_argument("--lang", default="en", help="語言代碼 (預設 en)")
    ap.add_argument("--whisper", action="store_true", help="強制用 Whisper(跳過 YouTube 字幕)")
    ap.add_argument("--model", default="large-v3", help="Whisper 模型 (預設 large-v3)")
    ap.add_argument("--initial-prompt", help="Whisper 引導詞 (專有名詞清單)")
    ap.add_argument("--out", default=str(DEFAULT_OUT), help="輸出目錄")
    ap.add_argument("--keep-audio", action="store_true", help="保留 .mp3 (預設轉錄完刪)")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    meta = fetch_metadata(args.url)
    slug = slugify(meta["title"])
    print(f"📺 {meta['title']}")
    print(f"   uploader={meta['uploader']}  duration={meta['duration']}s  id={meta.get('id', '?')}")

    # 寫 metadata
    (out_dir / f"{slug}.meta.json").write_text(
        json.dumps({**meta, "url": args.url, "lang": args.lang}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    txt_path: Optional[Path] = None

    if not args.whisper:
        vtt = try_youtube_subs(args.url, args.lang, out_dir, slug)
        if vtt:
            text = vtt_to_text(vtt)
            txt_path = out_dir / f"{slug}.txt"
            txt_path.write_text(text, encoding="utf-8")
            print(f"📝 寫入 {txt_path.name} ({len(text):,} chars)")
            # vtt 留著當原始檔
        else:
            print("⚡ 改走 Whisper fallback")

    if txt_path is None:
        # Whisper 路徑
        audio = download_audio(args.url, out_dir, slug)
        try:
            txt_path = whisper_transcribe(
                audio, args.lang, args.model, args.initial_prompt, out_dir
            )
        finally:
            if not args.keep_audio:
                audio.unlink(missing_ok=True)
                print(f"🗑️  已刪 {audio.name}")

    print(f"\n✅ 完成: {txt_path}")
    # 輸出前 500 字當預覽
    preview = txt_path.read_text(encoding="utf-8")[:500]
    print(f"\n--- 預覽 (前 500 字) ---\n{preview}\n...")


if __name__ == "__main__":
    main()
