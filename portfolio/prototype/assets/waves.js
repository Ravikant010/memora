// Animated wireframe "mountain" lines (purple → magenta → orange) for every canvas.waves.
// data-lines sets the line count; data-calm lowers the peaks for small bands.
(() => {
  const still = matchMedia("(prefers-reduced-motion: reduce)").matches;

  function ridge(x, w, i, t) {
    const n =
      Math.sin(x * 0.0045 + t * 0.00035 + i * 0.16) * 0.5 +
      Math.sin(x * 0.011 - t * 0.0005 + i * 0.31) * 0.3 +
      Math.sin(x * 0.023 + t * 0.0002 + i * 0.47) * 0.2;
    const peak = Math.pow((n + 1) / 2, 2.2);
    // Lower in the middle so content can sit in a valley, taller toward the edges.
    const edge = Math.abs(x / w - 0.5) * 2;
    return peak * (0.35 + 0.65 * edge);
  }

  function setup(canvas) {
    const ctx = canvas.getContext("2d");
    const lines = Number(canvas.dataset.lines || 34);
    const calm = "calm" in canvas.dataset ? 0.8 : 1;
    let w = 0, h = 0, visible = true;

    function resize() {
      const dpr = Math.min(devicePixelRatio || 1, 2);
      w = canvas.clientWidth;
      h = canvas.clientHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function draw(t) {
      ctx.clearRect(0, 0, w, h);
      const grad = ctx.createLinearGradient(0, 0, w, 0);
      grad.addColorStop(0, "#7c3aed");
      grad.addColorStop(0.5, "#d946ef");
      grad.addColorStop(1, "#f97316");
      ctx.strokeStyle = grad;
      ctx.lineWidth = 1;
      for (let i = 0; i < lines; i++) {
        const depth = i / (lines - 1); // 0 = back, 1 = front
        const base = h * (0.55 + depth * 0.5);
        const amp = h * (0.75 - depth * 0.35) * calm;
        ctx.globalAlpha = 0.12 + depth * 0.4;
        ctx.beginPath();
        for (let x = -10; x <= w + 10; x += 8) {
          const y = base - amp * ridge(x, w, i, t);
          x < 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        }
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }

    resize();
    addEventListener("resize", resize);
    new IntersectionObserver(([e]) => (visible = e.isIntersecting)).observe(canvas);
    return (t) => visible && draw(t);
  }

  const painters = [...document.querySelectorAll("canvas.waves")].map(setup);
  if (!painters.length) return;
  if (still) return painters.forEach((p) => p(0));
  (function loop(t) {
    painters.forEach((p) => p(t));
    requestAnimationFrame(loop);
  })(0);
})();
