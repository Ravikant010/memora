"""Record a scripted walkthrough of the running app as high-res frames (Chrome screencast).

Usage: uv run --with playwright python portfolio/record_demo.py http://127.0.0.1:8799 OUT_DIR
Writes OUT_DIR/frames/*.jpg plus OUT_DIR/frames.txt (ffmpeg concat list with durations).
"""

import asyncio
import base64
import json
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

W, H, SCALE = 1440, 900, 2

# A visible cursor + click ripple (headless screencasts don't draw the system cursor).
CURSOR_JS = """
(() => {
  const pos = JSON.parse(sessionStorage.getItem('__cur') || '[720,450]');
  const make = () => {
    const c = document.createElement('div');
    c.id = '__cursor';
    c.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24"><path d="M4 2l15 9.5-6.6 1.4L16 20l-3 1.5-3.6-7.2L4 19z" fill="#fff" stroke="#111" stroke-width="1.3" stroke-linejoin="round"/></svg>';
    Object.assign(c.style, {position: 'fixed', left: 0, top: 0, zIndex: 2147483647, pointerEvents: 'none',
      transform: `translate(${pos[0]}px, ${pos[1]}px)`, filter: 'drop-shadow(0 2px 4px rgba(0,0,0,.5))'});
    document.documentElement.append(c);
    addEventListener('mousemove', (e) => {
      c.style.transform = `translate(${e.clientX}px, ${e.clientY}px)`;
      sessionStorage.setItem('__cur', JSON.stringify([e.clientX, e.clientY]));
    }, true);
    addEventListener('mousedown', (e) => {
      const r = document.createElement('div');
      Object.assign(r.style, {position: 'fixed', left: e.clientX - 18 + 'px', top: e.clientY - 18 + 'px', width: '36px',
        height: '36px', borderRadius: '50%', border: '2px solid rgba(217,70,239,.9)', zIndex: 2147483646,
        pointerEvents: 'none', transition: 'transform .45s ease-out, opacity .45s ease-out'});
      document.documentElement.append(r);
      requestAnimationFrame(() => { r.style.transform = 'scale(1.8)'; r.style.opacity = '0'; });
      setTimeout(() => r.remove(), 500);
    }, true);
  };
  document.readyState === 'loading' ? addEventListener('DOMContentLoaded', make) : make();
})();
"""

SMOOTH_SCROLL_JS = """
([to, ms]) => new Promise((done) => {
  const from = scrollY, t0 = performance.now();
  const ease = (t) => t < .5 ? 4*t*t*t : 1 - Math.pow(-2*t + 2, 3) / 2;
  (function step(now) {
    const t = Math.min(1, (now - t0) / ms);
    scrollTo(0, from + (to - from) * ease(t));
    t < 1 ? requestAnimationFrame(step) : done();
  })(t0);
})
"""


async def main(base: str, out: Path) -> None:
    frames_dir = out / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    frames: list[tuple[float, Path]] = []
    marks: list[tuple[str, float]] = []  # (step, wall-clock time) for captions

    async with async_playwright() as p:
        browser = await p.chromium.launch(channel="chrome")
        ctx = await browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=SCALE)
        await ctx.add_init_script(CURSOR_JS)
        page = await ctx.new_page()
        cdp = await ctx.new_cdp_session(page)

        async def on_frame(ev):
            path = frames_dir / f"{len(frames):05d}.jpg"
            path.write_bytes(base64.b64decode(ev["data"]))
            frames.append((ev["metadata"]["timestamp"], path))
            await cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})

        cdp.on("Page.screencastFrame", lambda ev: asyncio.ensure_future(on_frame(ev)))

        async def move_to(selector: str, steps: int = 30):
            box = await page.locator(selector).first.bounding_box()
            await page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2, steps=steps)

        async def click(selector: str):
            await move_to(selector)
            await page.wait_for_timeout(150)
            await page.locator(selector).first.click()

        async def scroll_to(y: int, ms: int):
            await page.evaluate(SMOOTH_SCROLL_JS, [y, ms])

        async def results_ready(text: str):
            await page.wait_for_selector(f"#results .results-head:has-text('{text}')")
            await page.wait_for_function(
                "[...document.querySelectorAll('#results img')].slice(0, 8).every(i => i.complete)"
            )

        await page.goto(f"{base}/")
        await page.wait_for_load_state("networkidle")
        await cdp.send(
            "Page.startScreencast",
            {"format": "jpeg", "quality": 92, "maxWidth": W * SCALE, "maxHeight": H * SCALE},
        )
        # 1. Land on the hero
        marks.append(("hero", time.time()))
        await page.wait_for_timeout(3200)

        # 2. Search by typing
        marks.append(("search", time.time()))
        await click("input[name=q]")
        await page.keyboard.type("dog playing frisbee", delay=85)
        await results_ready("dog playing frisbee")
        await page.wait_for_timeout(1200)
        await scroll_to(560, 1800)
        await move_to(".masonry .card:nth-child(2)")
        await page.wait_for_timeout(900)
        await move_to(".masonry .card:nth-child(3)")
        await page.wait_for_timeout(700)

        # 3. Open a photo
        marks.append(("photo", time.time()))
        await click(".masonry .card:nth-child(1)")
        await page.wait_for_selector("#lightbox[open]")
        await page.wait_for_timeout(2400)
        await page.keyboard.press("Escape")
        await page.wait_for_timeout(500)

        # 4. Multilingual query via a suggestion chip
        marks.append(("multilingual", time.time()))
        await scroll_to(0, 1100)
        await click(".chip[data-q^='बच्चे']")
        await results_ready("बच्चे")
        await page.wait_for_timeout(1400)
        await scroll_to(420, 1500)
        await page.wait_for_timeout(1300)
        await scroll_to(0, 1000)

        # 5. Another free-text query
        marks.append(("freetext", time.time()))
        await page.locator("input[name=q]").first.click(click_count=3)
        await page.keyboard.type("red double decker bus", delay=80)
        await results_ready("red double decker bus")
        await page.wait_for_timeout(1200)
        await scroll_to(480, 1500)
        await page.wait_for_timeout(1500)

        # 6. How it works + privacy
        marks.append(("how", time.time()))
        await scroll_to(0, 900)
        await click("a.brand")
        await page.wait_for_url(f"{base}/")
        await page.wait_for_timeout(1200)
        how = await page.evaluate("document.getElementById('how').getBoundingClientRect().top + scrollY")
        await scroll_to(how + 40, 2600)
        await page.wait_for_timeout(3600)
        privacy = await page.evaluate("document.getElementById('privacy').getBoundingClientRect().top + scrollY")
        await scroll_to(privacy - 260, 1800)
        await page.wait_for_timeout(2800)

        await cdp.send("Page.stopScreencast")
        await page.wait_for_timeout(300)
        await browser.close()

    # ffmpeg concat list: each frame lasts until the next one arrives.
    frames.sort()
    lines = []
    for (t, path), (t_next, _) in zip(frames, frames[1:] + [(frames[-1][0] + 0.5, None)]):
        lines += [f"file '{path.resolve()}'", f"duration {max(t_next - t, 0.001):.4f}"]
    lines.append(f"file '{frames[-1][1].resolve()}'")
    (out / "frames.txt").write_text("\n".join(lines) + "\n")
    t0 = frames[0][0]
    (out / "marks.json").write_text(json.dumps({name: round(t - t0, 2) for name, t in marks}))
    print(f"{len(frames)} frames, {frames[-1][0] - frames[0][0]:.1f}s")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1].rstrip("/"), Path(sys.argv[2])))
