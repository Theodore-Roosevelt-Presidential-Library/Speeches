// Theodore Roosevelt's Speeches — shared helpers
const SP = (() => {
  const API = new URL("api/v1/", document.baseURI).href;
  const cache = new Map();
  const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];
  const MON = ["Jan.","Feb.","Mar.","Apr.","May","June","July","Aug.","Sept.","Oct.","Nov.","Dec."];
  const KIND = { speech: "Speech", lecture: "Lecture", message: "Message to Congress", letter: "Public letter", statement: "Statement", memorandum: "Memorandum" };

  function get(path) {
    if (!cache.has(path)) cache.set(path, fetch(API + path).then(r => { if (!r.ok) throw new Error(r.status + " " + path); return r.json(); }));
    return cache.get(path);
  }
  function esc(s) { return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
  function param(n) { return new URLSearchParams(location.search).get(n); }
  function fmtDate(iso, short) {
    if (!iso) return "Date unknown";
    const [y, m, d] = iso.split("-").map(Number);
    if (!m) return String(y);
    if (!d) return `${MONTHS[m - 1]} ${y}`;
    return short ? `${MON[m - 1]} ${d}, ${y}` : `${MONTHS[m - 1]} ${d}, ${y}`;
  }
  function weekday(iso) {
    if (!iso || iso.length !== 10) return "";
    return new Date(iso + "T12:00:00Z").toLocaleDateString("en-US", { weekday: "long", timeZone: "UTC" });
  }
  function placeName(p) { return p ? `${p.name}${p.region && p.region !== p.name ? ", " + p.region : ""}` : ""; }
  function num(n) { return Number(n || 0).toLocaleString("en-US"); }
  function speechLink(id, html) { return `<a href="speech.html?id=${encodeURIComponent(id)}">${html}</a>`; }
  function escRe(s) { return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }

  // a row in a list of speeches
  function row(s, placeMap) {
    const p = s.place && placeMap ? placeMap[s.place] : null;
    const cls = s.kind === "message" ? "m" : (s.text ? "t" : "");
    const badges = (s.text ? `<span class="badge text">Full text</span>` : "") + (s.trc ? `<span class="badge scan">Original at the TRC</span>` : "") + (s.kind !== "speech" && s.kind !== "lecture" ? `<span class="badge msg">${esc(KIND[s.kind] || s.kind)}</span>` : "");
    const meta = [fmtDate(s.date, true), p ? placeName(p) : null, s.words ? `${num(s.words)} words` : null].filter(Boolean).join(" &nbsp;|&nbsp; ");
    return `<li class="${cls}"><a class="ttl" href="speech.html?id=${encodeURIComponent(s.id)}">${esc(s.title)}</a>${badges}<div class="meta">${meta}</div></li>`;
  }

  // simple SVG bar/line chart: values = [[label, value], ...]
  function barChart(values, opts = {}) {
    const W = opts.width || 760, H = opts.height || 180, pad = 26, n = values.length || 1;
    const max = Math.max(1, ...values.map(v => v[1]));
    const bw = (W - pad) / n;
    let s = `<svg class="chart" viewBox="0 0 ${W} ${H + 22}" role="img" aria-label="${esc(opts.label || "chart")}">`;
    values.forEach(([lab, v], i) => {
      const h = Math.round((v / max) * (H - 10));
      const x = pad + i * bw;
      s += `<rect x="${x + 1}" y="${H - h}" width="${Math.max(1, bw - 2)}" height="${h}" fill="${opts.color || "#FC924E"}"><title>${esc(lab)}: ${opts.fmt ? opts.fmt(v) : v}</title></rect>`;
      if (opts.every ? i % opts.every === 0 : n <= 30) s += `<text x="${x + bw / 2}" y="${H + 14}" text-anchor="middle">${esc(lab)}</text>`;
    });
    s += `<line x1="${pad}" y1="${H}" x2="${W}" y2="${H}" stroke="#D1CCBD"/>`;
    s += `<text x="0" y="10">${opts.fmt ? opts.fmt(max) : num(max)}</text></svg>`;
    return s;
  }

  return { API, get, esc, param, fmtDate, weekday, placeName, num, speechLink, row, barChart, escRe, KIND, MONTHS };
})();
