# Portfolio assets

| File | What |
|---|---|
| `memora-demo.mp4` | 1080p mockup video (~55 s): intro → hero → search → photo viewer → Hindi query → how it works → outro |
| `memora-poster.png` | 1920×1080 poster / thumbnail frame |
| `prototype/` | Static, backend-free clickable prototype. Upload the folder and link to `prototype/index.html`. |

The prototype uses precomputed results from the real model for 12 example queries; typed text is matched to the
closest example.

## Rebuild

```bash
uv run python -m portfolio.build_prototype                      # prototype/ (loads the model)

uv run uvicorn app.main:app --port 8799 &                       # video: run the app,
uv run --with playwright python portfolio/record_demo.py http://127.0.0.1:8799 /tmp/rec
(cd /tmp/rec && ffmpeg -f concat -safe 0 -i frames.txt -vf "fps=30,format=yuv420p" -c:v libx264 -crf 14 raw.mp4)
uv run --with playwright python portfolio/make_video.py /tmp/rec
```

Recording and compositing use your installed Google Chrome via Playwright, plus ffmpeg.
