"""Compose the recorded walkthrough into a 1080p portfolio mockup video.

Usage: uv run --with playwright python portfolio/make_video.py REC_DIR
  REC_DIR comes from record_demo.py (raw.mp4 + marks.json).
Outputs portfolio/<name>-demo.mp4 and portfolio/<name>-poster.png (name from GG_APP_NAME).
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.config import get_settings

NAME = get_settings().app_name
SLUG = NAME.lower().replace(" ", "-")

OUT = Path(__file__).parent
CW, CH = 1920, 1080  # canvas
WX, WY, WW, BAR, AH = 256, 40, 1408, 36, 880  # window position, width, title bar, app height
RADIUS = 14
FPS = 30
INTRO, OUTRO, XF = 3.6, 3.8, 0.6

CAPTIONS = {
    "hero": "Semantic photo search that runs on your machine",
    "search": "Describe a moment — results update as you type",
    "photo": "Every match carries a similarity score",
    "multilingual": "Works in any language — here, Hindi",
    "freetext": "No tags, no albums — just meaning",
    "how": "EmbeddingGemma 2 · runs entirely on-device",
}

HEAD = """<!doctype html><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  * { box-sizing: border-box; margin: 0; }
  html, body { background: transparent; font-family: "Plus Jakarta Sans", system-ui, sans-serif; color: #f5f4f7; }
  .canvas { position: relative; width: 1920px; height: 1080px; overflow: hidden; background: #0b0b0d; }
  .glow { position: absolute; border-radius: 50%; filter: blur(110px); }
  .stars { position: absolute; inset: 0; opacity: .5;
    background-image: radial-gradient(1px 1px at 20px 30px, #fff, transparent), radial-gradient(1px 1px at 120px 80px, rgba(255,255,255,.7), transparent),
      radial-gradient(1.5px 1.5px at 200px 160px, rgba(255,255,255,.8), transparent), radial-gradient(1px 1px at 60px 210px, rgba(255,255,255,.5), transparent);
    background-size: 300px 260px; }
  .silver { background: linear-gradient(180deg, #fff 0%, #d9d6e0 45%, #8e8a99 100%); -webkit-background-clip: text; background-clip: text; color: transparent; }
  .brand-grad { background: linear-gradient(135deg, #f97316, #d946ef 50%, #7c3aed); }
</style>"""

GLOWS = """
<div class="glow" style="left:-300px;bottom:-380px;width:1100px;height:800px;background:radial-gradient(closest-side,rgba(124,58,237,.8),transparent)"></div>
<div class="glow" style="right:-300px;bottom:-380px;width:1100px;height:800px;background:radial-gradient(closest-side,rgba(249,115,22,.65),rgba(236,72,153,.25) 60%,transparent)"></div>
<div class="glow" style="left:50%;top:-420px;width:1400px;height:700px;translate:-50% 0;background:radial-gradient(closest-side,rgba(217,70,239,.45),rgba(124,58,237,.25) 60%,transparent)"></div>
<div class="stars"></div>"""

LOGO = """<svg width="{w}" height="{h}" viewBox="0 0 28 24" fill="none" stroke-width="2.2" stroke-linecap="round">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f97316"/><stop offset=".5" stop-color="#d946ef"/><stop offset="1" stop-color="#7c3aed"/></linearGradient></defs>
<g stroke="url(#g)"><path d="M2 6c4-3 8 3 12 0s8-3 12 0"/><path d="M2 12c4-3 8 3 12 0s8-3 12 0"/><path d="M2 18c4-3 8 3 12 0s8-3 12 0"/></g></svg>"""

BACKGROUND = f"""{HEAD}<div class="canvas">{GLOWS}
<div style="position:absolute;left:{WX}px;top:{WY}px;width:{WW}px;height:{BAR + AH}px;border-radius:{RADIUS}px;
  box-shadow:0 0 0 1px rgba(255,255,255,.14),0 50px 140px rgba(0,0,0,.75),0 0 160px rgba(217,70,239,.25)"></div>
</div>"""

FRAME = f"""{HEAD}<div style="width:{WW}px;height:{BAR + AH}px;border-radius:{RADIUS}px;overflow:hidden;background:#0b0b0d">
<div style="height:{BAR}px;display:flex;align-items:center;padding:0 16px;background:linear-gradient(#232329,#1a1a1f);border-bottom:1px solid rgba(255,255,255,.08);position:relative">
  <span style="display:flex;gap:8px">
    <i style="width:12px;height:12px;border-radius:50%;background:#ff5f57"></i>
    <i style="width:12px;height:12px;border-radius:50%;background:#febc2e"></i>
    <i style="width:12px;height:12px;border-radius:50%;background:#28c840"></i></span>
  <span style="position:absolute;left:50%;translate:-50% 0;display:flex;align-items:center;gap:8px;padding:4px 80px;border-radius:8px;
    background:rgba(255,255,255,.06);font-size:13px;color:#c8c6cf">
    <svg width="11" height="11" viewBox="0 0 24 24" fill="#8a8794"><path d="M12 2a5 5 0 0 0-5 5v3H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8a2 2 0 0 0-2-2h-1V7a5 5 0 0 0-5-5Zm-3 8V7a3 3 0 1 1 6 0v3H9Z"/></svg>
    localhost:8000</span>
</div></div>"""

MASK = f"""{HEAD}<body style="background:#000"><div style="width:{WW}px;height:{BAR + AH}px;border-radius:{RADIUS}px;background:#fff"></div>"""

CAPTION = f"""{HEAD}<div style="width:{CW}px;height:80px;display:flex;justify-content:center;align-items:center">
<div style="display:flex;align-items:center;gap:12px;padding:12px 24px;border-radius:999px;border:1px solid rgba(255,255,255,.16);
  background:rgba(20,20,26,.78);box-shadow:0 10px 40px rgba(0,0,0,.5);font-size:21px;font-weight:500">
  <i class="brand-grad" style="width:10px;height:10px;border-radius:50%;box-shadow:0 0 12px #d946ef"></i>{{text}}</div></div>"""

INTRO_HTML = f"""{HEAD}<div class="canvas" style="display:grid;place-items:center;text-align:center">{GLOWS}
<div style="position:relative">
  <div style="display:inline-flex;align-items:center;gap:10px;padding:8px 18px;border:1px solid rgba(255,255,255,.16);border-radius:999px;
    background:rgba(255,255,255,.04);font-size:20px;color:#c8c6cf"><span style="color:#facc15">★</span> Case study · Visual AI</div>
  <div style="display:flex;align-items:center;justify-content:center;gap:24px;margin-top:34px">
    {LOGO.format(w=110, h=94)}
    <h1 class="silver" style="font-size:132px;font-weight:600;letter-spacing:-.05em;line-height:1">{NAME}</h1></div>
  <p style="margin-top:26px;font-size:32px;color:#a9a6b3">Search your photos by describing them — in any language, fully on-device.</p>
</div></div>"""

OUTRO_HTML = f"""{HEAD}<div class="canvas" style="display:grid;place-items:center;text-align:center">{GLOWS}
<div style="position:relative">
  <div style="display:flex;align-items:center;justify-content:center;gap:18px">{LOGO.format(w=64, h=55)}
    <h2 class="silver" style="font-size:72px;font-weight:600;letter-spacing:-.045em">{NAME}</h2></div>
  <p style="margin-top:18px;font-size:28px;color:#a9a6b3">Semantic photo search powered by EmbeddingGemma 2</p>
  <div style="display:flex;gap:12px;justify-content:center;margin-top:40px">
    {"".join(f'<span style="padding:10px 22px;border:1px solid rgba(255,255,255,.16);border-radius:999px;background:rgba(255,255,255,.04);font-size:20px;color:#e5e3ea">{t}</span>' for t in ["FastAPI", "HTMX", "EmbeddingGemma 2", "PyTorch · MPS", "SQLite + NumPy"])}
  </div>
</div></div>"""


async def render_assets(tmp: Path) -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome")
        page = await browser.new_page(viewport={"width": CW, "height": CH})

        async def shot(html: str, name: str, w: int, h: int, transparent: bool) -> None:
            await page.set_viewport_size({"width": w, "height": h})
            await page.set_content(html, wait_until="networkidle")
            await page.evaluate("document.fonts.ready")
            await page.screenshot(path=str(tmp / name), omit_background=transparent)

        await shot(BACKGROUND, "bg.png", CW, CH, False)
        await shot(FRAME, "frame.png", WW, BAR + AH, True)
        await shot(MASK, "mask.png", WW, BAR + AH, False)
        await shot(INTRO_HTML, "intro.png", CW, CH, False)
        await shot(OUTRO_HTML, "outro.png", CW, CH, False)
        for key, text in CAPTIONS.items():
            await shot(CAPTION.replace("{text}", text), f"cap_{key}.png", CW, 80, True)
        await browser.close()


def duration(path: Path) -> float:
    out = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]
    )
    return float(out)


def compose(rec: Path, tmp: Path) -> Path:
    raw = rec / "raw.mp4"
    d = duration(raw)
    marks = json.loads((rec / "marks.json").read_text())
    order = [k for k in CAPTIONS if k in marks]
    spans = []
    for i, k in enumerate(order):
        start = max(marks[k], 0.2)
        end = (marks[order[i + 1]] - 0.15) if i + 1 < len(order) else d - 0.4
        spans.append((k, start, end))

    inputs = ["-loop", "1", "-t", f"{d}", "-i", str(tmp / "bg.png"),
              "-loop", "1", "-t", f"{d}", "-i", str(tmp / "frame.png"),
              "-loop", "1", "-t", f"{d}", "-i", str(tmp / "mask.png"),
              "-i", str(raw)]
    for k, _, _ in spans:
        inputs += ["-loop", "1", "-t", f"{d}", "-i", str(tmp / f"cap_{k}.png")]
    n = 4 + len(spans)
    inputs += ["-loop", "1", "-t", f"{INTRO}", "-i", str(tmp / "intro.png"),
               "-loop", "1", "-t", f"{OUTRO}", "-i", str(tmp / "outro.png")]

    norm = f"fps={FPS},format=yuv420p,setsar=1,settb=AVTB"
    g = [
        f"[3:v]scale={WW}:{AH}:flags=lanczos,setsar=1,fps={FPS}[app]",
        f"[1:v]format=rgba,fps={FPS}[fr]",
        f"[fr][app]overlay=0:{BAR}:shortest=1[win]",
        f"[2:v]format=gray,fps={FPS}[m]",
        "[win][m]alphamerge[winr]",
        f"[0:v]fps={FPS}[bg]",
        f"[bg][winr]overlay={WX}:{WY}:shortest=1[s0]",
    ]
    cap_y = WY + BAR + AH + (CH - (WY + BAR + AH) - 80) // 2
    for i, (_, s, e) in enumerate(spans):
        g.append(
            f"[{4 + i}:v]format=rgba,fps={FPS},fade=in:st={s:.2f}:d=0.35:alpha=1,"
            f"fade=out:st={e - 0.35:.2f}:d=0.35:alpha=1[c{i}]"
        )
        g.append(f"[s{i}][c{i}]overlay=0:{cap_y}:enable='between(t,{s:.2f},{e:.2f})'[s{i + 1}]")
    g += [
        f"[s{len(spans)}]{norm}[main]",
        f"[{n}:v]{norm}[intro]",
        f"[{n + 1}:v]{norm}[outro]",
        f"[intro][main]xfade=transition=fade:duration={XF}:offset={INTRO - XF}[a]",
        f"[a][outro]xfade=transition=fade:duration={XF}:offset={INTRO - XF + d - XF}[v]",
    ]
    out = OUT / f"{SLUG}-demo.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", ";".join(g),
         "-map", "[v]", "-c:v", "libx264", "-preset", "slow", "-crf", "17", "-profile:v", "high",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)],
        check=True,
    )
    poster_t = INTRO - XF + marks.get("search", 8) + 6.5
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{poster_t:.2f}", "-i", str(out),
         "-frames:v", "1", str(OUT / f"{SLUG}-poster.png")],
        check=True,
    )
    return out


def main(rec: Path) -> None:
    tmp = rec / "assets"
    tmp.mkdir(exist_ok=True)
    asyncio.run(render_assets(tmp))
    out = compose(rec, tmp)
    print(f"{out} — {duration(out):.1f}s, {out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
