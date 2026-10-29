// Static prototype: replaces the FastAPI/HTMX backend with precomputed results (window.PRESETS).
(() => {
  const form = document.querySelector("form.palette");
  const results = document.getElementById("results");
  if (!form || !results) return;
  const presets = window.PRESETS || {};
  const names = Object.keys(presets);

  const words = (s) => s.toLowerCase().match(/[\p{L}\p{N}]+/gu) || [];
  function closest(q) {
    if (presets[q]) return q;
    const qw = new Set(words(q));
    let best = null, bestScore = 0;
    for (const name of names) {
      const nw = words(name);
      const hit = nw.filter((w) => [...qw].some((x) => x.length > 2 && (w.startsWith(x) || x.startsWith(w)))).length;
      const score = hit / nw.length;
      if (score > bestScore) { best = name; bestScore = score; }
    }
    return bestScore >= 0.34 ? best : null;
  }

  const escape = (s) => s.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
  function noMatch(q) {
    const chips = names.map((n) => `<button type="button" class="chip" data-q="${escape(n)}">${escape(n)}</button>`).join("");
    return `<p class="empty">This prototype has precomputed results — no match for “${escape(q)}”. Try one of these:</p>
            <div class="chips">${chips}</div><div class="masonry"></div>`;
  }

  let timer;
  function run(q, delay = 350) {
    q = q.trim();
    clearTimeout(timer);
    const url = new URL(location.href);
    q ? url.searchParams.set("q", q) : url.searchParams.delete("q");
    history.replaceState(null, "", url);
    if (!q) { results.innerHTML = ""; return; }
    form.classList.add("htmx-request"); // reuse the loading beam
    timer = setTimeout(() => {
      const match = closest(q);
      results.innerHTML = match ? presets[match] : noMatch(q);
      form.classList.remove("htmx-request");
    }, delay);
  }

  form.addEventListener("submit", (e) => { e.preventDefault(); run(form.q.value, 200); });
  form.q.addEventListener("input", () => run(form.q.value, 450));
  results.addEventListener("click", (e) => {
    const chip = e.target.closest(".chip");
    if (!chip) return;
    form.q.value = chip.dataset.q;
    run(chip.dataset.q, 200);
  });

  const initial = new URLSearchParams(location.search).get("q");
  if (initial) { form.q.value = initial; run(initial, 0); }
})();
