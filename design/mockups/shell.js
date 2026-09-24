/*
 * Svoya OS — shared runtime for the screen mockups.
 *
 * Load it in <head> (it sets data-theme from ?theme= before first paint), then call
 * Svoya.init({...}) at the end of <body>. It draws what every screen shares with the approved
 * desktop mockup: the top bar, the wallpaper signal, the Morse mark, Jackson's scope in all its
 * states, and the line-icon set (Lucide geometry, ISC — redrawn on the 24px grid, round caps).
 * Rendering is deterministic: no randomness, no clock, so PNGs are reproducible.
 */
(function () {
  const q = new URLSearchParams(location.search);
  document.documentElement.dataset.theme = q.get('theme') || 'graphite';
})();

window.Svoya = (() => {
  const NS = 'http://www.w3.org/2000/svg';
  const MORSE = ['...', '---', '...']; // С О С — identical in Russian and international Morse
  const q = new URLSearchParams(location.search);
  let uid = 0;

  /* ─────────────── icons (24px grid, stroke drawn by CSS) ─────────────── */
  const FILE = '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>';
  const SHIELD = '<path d="M12 3 5 6v5.2c0 4.3 2.9 7.9 7 9.8 4.1-1.9 7-5.5 7-9.8V6z"/>';
  const ICONS = {
    search: '<circle cx="11" cy="11" r="6.5"/><path d="m20 20-4.4-4.4"/>',
    // the three bar glyphs are the approved ones, unchanged
    wifi: '<path d="M2.5 9a15 15 0 0 1 19 0"/><path d="M5.5 12.5a10.5 10.5 0 0 1 13 0"/><path d="M8.7 16a6 6 0 0 1 6.6 0"/><circle cx="12" cy="19.3" r="0.6"/>',
    volume: '<path d="M4 9.5h3.5L12 5.5v13l-4.5-4H4z"/><path d="M15.5 9a4.5 4.5 0 0 1 0 6"/><path d="M18 6.5a8 8 0 0 1 0 11"/>',
    battery: '<rect x="2.5" y="7.5" width="17" height="9" rx="2"/><path d="M21.5 10.5v3"/><rect x="4.5" y="9.5" width="10" height="5" rx="0.8" fill="currentColor" stroke="none"/>',
    bluetooth: '<path d="m7 7 10 10-5 5V2l5 5L7 17"/>',
    sun: '<circle cx="12" cy="12" r="3.6"/><path d="M12 2.8v1.9M12 19.3v1.9M5.5 5.5l1.35 1.35M17.15 17.15l1.35 1.35M2.8 12h1.9M19.3 12h1.9M5.5 18.5l1.35-1.35M17.15 6.85 18.5 5.5"/>',
    moon: '<path d="M19.5 14.2A7.8 7.8 0 1 1 9.8 4.5a6.2 6.2 0 0 0 9.7 9.7z"/>',
    lock: '<rect x="4.5" y="10.5" width="15" height="10" rx="2.2"/><path d="M8 10.5V7.8a4 4 0 0 1 8 0v2.7"/>',
    power: '<path d="M12 3v8.5"/><path d="M17.7 6.6a8.2 8.2 0 1 1-11.4 0"/>',
    restart: '<path d="M20 12a8 8 0 1 1-2.35-5.65L20 8.7"/><path d="M20 3.8v4.9h-4.9"/>',
    folder: '<path d="M3 7.2A2.2 2.2 0 0 1 5.2 5h3.6l2.2 2.2h7.8A2.2 2.2 0 0 1 21 9.4v7.4a2.2 2.2 0 0 1-2.2 2.2H5.2A2.2 2.2 0 0 1 3 16.8z"/>',
    file: FILE,
    fileCode: FILE + '<path d="m10 12.5-2.2 2.2 2.2 2.2M14 12.5l2.2 2.2-2.2 2.2"/>',
    fileText: FILE + '<path d="M8.5 13h7M8.5 16.5h4.5"/>',
    fileAudio: FILE + '<path d="M9 13.5v3M12 12v6M15 14v2"/>',
    terminal: '<rect x="3" y="4" width="18" height="16" rx="2.4"/><path d="m7.2 9.2 2.8 2.8-2.8 2.8M12.5 15h4.3"/>',
    workflow: '<rect x="3" y="3" width="8" height="8" rx="2"/><path d="M7 11v3.8A2.2 2.2 0 0 0 9.2 17H13"/><rect x="13" y="13" width="8" height="8" rx="2"/>',
    package: '<path d="M20.5 7.8 12 3 3.5 7.8v8.4L12 21l8.5-4.8z"/><path d="m3.5 7.8 8.5 4.8 8.5-4.8M12 12.6V21"/>',
    download: '<path d="M12 3.5v11M7.3 10.2 12 14.9l4.7-4.7M4.5 19.5h15"/>',
    upload: '<path d="M12 15V4M7.3 8.3 12 3.6l4.7 4.7M4.5 19.5h15"/>',
    globe: '<circle cx="12" cy="12" r="8.8"/><path d="M3.2 12h17.6M12 3.2c2.5 2.4 3.8 5.3 3.8 8.8s-1.3 6.4-3.8 8.8c-2.5-2.4-3.8-5.3-3.8-8.8S9.5 5.6 12 3.2z"/>',
    shield: SHIELD,
    shieldCheck: SHIELD + '<path d="m9 12.2 2.1 2.1 4-4.1"/>',
    check: '<path d="M19.5 6.5 9.2 16.8 4.5 12.1"/>',
    x: '<path d="M17.5 6.5l-11 11M6.5 6.5l11 11"/>',
    chevronRight: '<path d="m9.5 6 6 6-6 6"/>',
    chevronDown: '<path d="m6 9.5 6 6 6-6"/>',
    chevronUp: '<path d="m6 14.5 6-6 6 6"/>',
    arrowRight: '<path d="M4.5 12h15M13.5 6l6 6-6 6"/>',
    arrowUpRight: '<path d="M7 17 17 7M8.5 7H17v8.5"/>',
    mic: '<rect x="9" y="3" width="6" height="11.5" rx="3"/><path d="M5.5 11.2a6.5 6.5 0 0 0 13 0M12 17.7V21"/>',
    bell: '<path d="M6.2 16.5v-5.3a5.8 5.8 0 0 1 11.6 0v5.3l1.6 1.9H4.6z"/><path d="M10 21a2.1 2.1 0 0 0 4 0"/>',
    user: '<circle cx="12" cy="8.2" r="3.9"/><path d="M4.8 20.2a7.2 7.2 0 0 1 14.4 0"/>',
    users: '<circle cx="9.5" cy="8.4" r="3.6"/><path d="M3 20a6.5 6.5 0 0 1 13 0"/><path d="M15.4 4.9a3.6 3.6 0 0 1 0 7M18 14.4a6.5 6.5 0 0 1 3 5.6"/>',
    key: '<circle cx="8" cy="15.5" r="4.4"/><path d="m11.2 12.4 8.3-8.3M16.4 7.2l2.6 2.6M14 9.6l2 2"/>',
    cloud: '<path d="M7.2 18.5a4.4 4.4 0 0 1-.5-8.8 5.8 5.8 0 0 1 11.2 1.6 3.6 3.6 0 0 1-.4 7.2z"/>',
    cloudOff: '<path d="M9.4 18.5H7.2a4.4 4.4 0 0 1-.5-8.8c.2-.9.6-1.8 1.2-2.5M11 5.4a5.8 5.8 0 0 1 6.9 5.9 3.6 3.6 0 0 1 2.2 5.9"/><path d="m3.5 3.5 17 17"/>',
    eye: '<path d="M2.8 12S6.2 5.5 12 5.5 21.2 12 21.2 12 17.8 18.5 12 18.5 2.8 12 2.8 12z"/><circle cx="12" cy="12" r="2.8"/>',
    briefcase: '<rect x="3" y="7" width="18" height="13" rx="2.2"/><path d="M8.8 7V5.6A1.6 1.6 0 0 1 10.4 4h3.2a1.6 1.6 0 0 1 1.6 1.6V7M3 12.6h18"/>',
    activity: '<path d="M3 12.5h3.8l2.7-7 5 13 2.7-6h3.8"/>',
    presentation: '<path d="M3 4h18M4.6 4v9.4A1.6 1.6 0 0 0 6.2 15h11.6a1.6 1.6 0 0 0 1.6-1.6V4M12 15v3.2M8.4 21l3.6-2.8 3.6 2.8"/>',
    monitor: '<rect x="2.8" y="4" width="18.4" height="12.6" rx="2"/><path d="M8.4 20.5h7.2M12 16.6v3.9"/>',
    cpu: '<rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9.2" y="9.2" width="5.6" height="5.6" rx="0.8"/><path d="M9.5 2.5V5M14.5 2.5V5M9.5 19v2.5M14.5 19v2.5M2.5 9.5H5M2.5 14.5H5M19 9.5h2.5M19 14.5h2.5"/>',
    gpu: '<rect x="2.5" y="6" width="19" height="11" rx="1.8"/><circle cx="9" cy="11.5" r="2.8"/><path d="M14.5 9.5h4M14.5 13.5h4M5 17v2.2M8 17v2.2"/>',
    drive: '<rect x="3" y="4.5" width="18" height="15" rx="2.2"/><path d="M3 13.5h18M7 16.6h.01M10.2 16.6h.01"/>',
    keyboard: '<rect x="2.5" y="6" width="19" height="12" rx="2.2"/><path d="M6.5 10h.01M9.5 10h.01M12.5 10h.01M15.5 10h.01M18 10h.01M6.5 13.8h.01M18 13.8h.01M9.5 14h5"/>',
    undo: '<path d="M9 14.5 4.5 10 9 5.5"/><path d="M4.5 10h10a5 5 0 0 1 0 10H11"/>',
    history: '<path d="M3.8 12a8.2 8.2 0 1 0 2.4-5.8L3.8 8.6"/><path d="M3.8 4v4.6h4.6M12 7.8V12l3 1.8"/>',
    play: '<path d="M7.5 4.8v14.4L19 12z"/>',
    pause: '<path d="M8.5 5v14M15.5 5v14"/>',
    image: '<rect x="3.2" y="3.2" width="17.6" height="17.6" rx="2.4"/><circle cx="9" cy="9" r="1.9"/><path d="m20.8 15-3.3-3.3a2 2 0 0 0-2.8 0L6 20.8"/>',
    video: '<rect x="2.8" y="6" width="12.8" height="12" rx="2.2"/><path d="m15.6 10.4 5.6-3.2v9.6l-5.6-3.2"/>',
    wave: '<path d="M3.5 10.5v3M7.3 7.5v9M11.1 4.5v15M14.9 8.5v7M18.7 10v4"/>',
    text: '<path d="M20.5 14.6a2 2 0 0 1-2 2H8.2L3.5 20.5V5.5a2 2 0 0 1 2-2h13a2 2 0 0 1 2 2z"/><path d="M8 8.4h8M8 11.8h5"/>',
    layers: '<path d="m12 3.5 8.8 4.6L12 12.7 3.2 8.1z"/><path d="m3.2 12.3 8.8 4.6 8.8-4.6M3.2 16.4l8.8 4.6 8.8-4.6"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    minus: '<path d="M5 12h14"/>',
    more: '<path d="M5.5 12h.01M12 12h.01M18.5 12h.01"/>',
    sliders: '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M12 2.8v2.6M12 18.6v2.6M4.1 7.4l2.2 1.3M17.7 15.3l2.2 1.3M4.1 16.6l2.2-1.3M17.7 8.7l2.2-1.3"/><circle cx="12" cy="12" r="7.2"/>',
    accessibility: '<circle cx="12" cy="4.6" r="1.6"/><path d="M4.8 8.6 12 10l7.2-1.4M12 10v5.2M8.6 21l3.4-5.8 3.4 5.8"/>',
    zap: '<path d="M13 2.8 4.8 13.6H11l-1 7.6 8.2-10.8H12z"/>',
    code: '<path d="m15.5 17.5 5.5-5.5-5.5-5.5M8.5 6.5 3 12l5.5 5.5"/>',
    flask: '<path d="M9 3h6M10 3v6.2L4.8 18.3A1.8 1.8 0 0 0 6.4 21h11.2a1.8 1.8 0 0 0 1.6-2.7L14 9.2V3"/><path d="M7.4 15h9.2"/>',
    nodes: '<circle cx="6" cy="12" r="2.6"/><circle cx="18" cy="5.8" r="2.6"/><circle cx="18" cy="18.2" r="2.6"/><path d="m8.3 10.8 7.4-3.8M8.3 13.2l7.4 3.8"/>',
    compass: '<circle cx="12" cy="12" r="8.8"/><path d="m15.6 8.4-2.2 5-5 2.2 2.2-5z"/>',
    aperture: '<circle cx="12" cy="12" r="8.8"/><path d="m14.2 7.9 5 8.6M9.8 7.9h9.9M7.6 12l5-8.6M9.8 16.1l-5-8.6M14.2 16.1H4.3M16.4 12l-5 8.6"/>',
    clock: '<circle cx="12" cy="12" r="8.8"/><path d="M12 7.2V12l3.2 2"/>',
    camera: '<path d="M4.8 7.5h2.6L9 5h6l1.6 2.5h2.6a1.8 1.8 0 0 1 1.8 1.8v8.9a1.8 1.8 0 0 1-1.8 1.8H4.8A1.8 1.8 0 0 1 3 18.2V9.3a1.8 1.8 0 0 1 1.8-1.8z"/><circle cx="12" cy="13.2" r="3.4"/>',
    home: '<path d="M4 10.4 12 4l8 6.4v8.4a1.8 1.8 0 0 1-1.8 1.8H5.8A1.8 1.8 0 0 1 4 18.8z"/><path d="M9.8 20.6v-6h4.4v6"/>',
    box: '<rect x="3.5" y="4" width="17" height="5" rx="1.4"/><path d="M5 9v9.2A1.8 1.8 0 0 0 6.8 20h10.4a1.8 1.8 0 0 0 1.8-1.8V9M10 13h4"/>',
    database: '<ellipse cx="12" cy="5.8" rx="7.5" ry="2.8"/><path d="M4.5 5.8v12.4c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8V5.8M4.5 12c0 1.5 3.4 2.8 7.5 2.8s7.5-1.3 7.5-2.8"/>',
    star: '<path d="m12 3.6 2.6 5.3 5.8.8-4.2 4.1 1 5.8L12 16.9l-5.2 2.7 1-5.8-4.2-4.1 5.8-.8z"/>',
    heart: '<path d="M12 20s-7.8-4.6-7.8-10.2A4.3 4.3 0 0 1 12 7.3a4.3 4.3 0 0 1 7.8 2.5C19.8 15.4 12 20 12 20z"/>',
    link: '<path d="M10 14a4 4 0 0 0 5.7 0l3.1-3.1a4 4 0 0 0-5.7-5.7l-1 1"/><path d="M14 10a4 4 0 0 0-5.7 0l-3.1 3.1a4 4 0 0 0 5.7 5.7l1-1"/>',
    refresh: '<path d="M19.8 11a7.9 7.9 0 0 0-14.6-2.8M4.2 13a7.9 7.9 0 0 0 14.6 2.8"/><path d="M19.8 4.4V9h-4.6M4.2 19.6V15h4.6"/>',
    alert: '<path d="M12 3.8 21 19.5H3z"/><path d="M12 10v4.2M12 17h.01"/>',
    info: '<circle cx="12" cy="12" r="8.8"/><path d="M12 11v5.2M12 7.8h.01"/>',
    dot: '<circle cx="12" cy="12" r="3" fill="currentColor" stroke="none"/>',
    grid: '<rect x="3.5" y="3.5" width="7" height="7" rx="1.6"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.6"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.6"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.6"/>',
    tiles: '<rect x="3" y="3.5" width="9.5" height="17" rx="1.8"/><rect x="15" y="3.5" width="6" height="7.3" rx="1.6"/><rect x="15" y="13.2" width="6" height="7.3" rx="1.6"/>',
    windows: '<rect x="3" y="6.5" width="13" height="10" rx="1.8"/><path d="M7.5 6.5V5.2A1.7 1.7 0 0 1 9.2 3.5h10.1A1.7 1.7 0 0 1 21 5.2v8.1a1.7 1.7 0 0 1-1.7 1.7H16"/><path d="M3 20.5h18"/>',
    taskbar: '<rect x="3" y="3.5" width="18" height="17" rx="2.2"/><path d="M3 16.5h18M6.5 18.6h2M10.5 18.6h2"/>',
    tag: '<path d="M3.5 12.2V4.8a1.3 1.3 0 0 1 1.3-1.3h7.4l8.3 8.3a1.3 1.3 0 0 1 0 1.8l-7.4 7.4a1.3 1.3 0 0 1-1.8 0z"/><circle cx="8.2" cy="8.2" r="1.4"/>',
    scale: '<path d="M12 3.5v17M6.5 20.5h11M4 7h16M7 7l-3 7a3.2 3.2 0 0 0 6 0zM17 7l-3 7a3.2 3.2 0 0 0 6 0z"/>',
    copy: '<rect x="8.5" y="8.5" width="12" height="12" rx="2"/><path d="M15.5 8.5V5.3a1.8 1.8 0 0 0-1.8-1.8H5.3a1.8 1.8 0 0 0-1.8 1.8v8.4a1.8 1.8 0 0 0 1.8 1.8h3.2"/>',
    hash: '<path d="M9.5 3.5 7.5 20.5M16.5 3.5l-2 17M4 8.8h16.5M3.5 15.2H20"/>',
    snapshot: '<path d="M4 8.5V6a2 2 0 0 1 2-2h2.5M15.5 4H18a2 2 0 0 1 2 2v2.5M20 15.5V18a2 2 0 0 1-2 2h-2.5M8.5 20H6a2 2 0 0 1-2-2v-2.5"/><circle cx="12" cy="12" r="3.2"/>',
    filter: '<path d="M4 5h16l-6.2 7.4V19l-3.6 1.6v-8.2z"/>',
    sort: '<path d="M7 4.5v15M3.8 16.3 7 19.5l3.2-3.2M17 19.5v-15M13.8 7.7 17 4.5l3.2 3.2"/>',
    external: '<path d="M14 4h6v6M20 4l-8.5 8.5"/><path d="M18 14v4.2a1.8 1.8 0 0 1-1.8 1.8H5.8A1.8 1.8 0 0 1 4 18.2V7.8A1.8 1.8 0 0 1 5.8 6H10"/>',
    stop: '<rect x="6" y="6" width="12" height="12" rx="2"/>',
    wand: '<path d="m4 20 11-11M14 4v2.5M19.5 9.5H17M17.9 6.1l-1.8 1.8"/>',
  };

  function icons(root = document) {
    root.querySelectorAll('svg[data-i]').forEach((s) => {
      const k = s.dataset.i;
      if (!ICONS[k]) { console.warn('missing icon', k); return; }
      s.setAttribute('viewBox', '0 0 24 24');
      s.innerHTML = ICONS[k];
      s.classList.add('i');
    });
  }

  /* ─────────────── Morse mark ··· ——— ··· ───────────────
     s = scale (1 = the bar mark: 3.2px high). The ——— is always the accent.
     lit = how many of the nine symbols are lit (boot progress); unlit symbols use `var(--unlit)`. */
  function mark(svg, s = 1, lit = 9) {
    const u = 3.2 * s, dash = 8 * s, gap = 2.4 * s, letterGap = 3.2 * s;
    const h = Math.ceil(u + 6.8 * s);
    const cy = h / 2;
    let x = 0, n = 0;
    svg.innerHTML = '';
    MORSE.forEach((letter, li) => {
      [...letter].forEach((sym) => {
        const w = sym === '.' ? u : dash;
        const r = document.createElementNS(NS, 'rect');
        r.setAttribute('x', x.toFixed(2)); r.setAttribute('y', (cy - u / 2).toFixed(2));
        r.setAttribute('width', w.toFixed(2)); r.setAttribute('height', u.toFixed(2)); r.setAttribute('rx', (u / 2).toFixed(2));
        r.setAttribute('fill', n >= lit ? 'var(--unlit, var(--line-strong))' : li === 1 ? 'var(--accent)' : 'currentColor');
        svg.append(r);
        x += w + gap; n += 1;
      });
      x += letterGap;
    });
    const width = x - gap - letterGap;
    svg.setAttribute('width', Math.ceil(width + (s === 1 ? gap + letterGap : 0)));
    svg.setAttribute('height', h);
    svg.setAttribute('viewBox', `0 0 ${Math.ceil(width + (s === 1 ? gap + letterGap : 0))} ${h}`);
  }

  /* ─────────────── wallpaper signal: a horizon line carrying one Morse burst ─────────────── */
  function signal(svg, o = {}) {
    const y = o.y ?? 700, u = o.u ?? 6.5, h = o.h ?? 14, x0 = o.x0 ?? 1030, W = o.w ?? 1440;
    const id = 's' + (++uid);
    let x = x0, d = `M ${x0 - 70} ${y} L ${x0} ${y}`;
    MORSE.forEach((letter, li) => {
      [...letter].forEach((sym, si) => {
        const w = (sym === '.' ? 1 : 3) * u;
        d += ` L ${x} ${y - h} L ${x + w} ${y - h} L ${x + w} ${y}`;
        x += w;
        if (si < letter.length - 1) { d += ` L ${x + u} ${y}`; x += u; }
      });
      if (li < MORSE.length - 1) { d += ` L ${x + 3 * u} ${y}`; x += 3 * u; }
    });
    d += ` L ${x + 70} ${y}`;
    svg.setAttribute('viewBox', `0 0 ${W} ${o.hgt ?? 900}`);
    svg.innerHTML = `
      <defs>
        <linearGradient id="${id}f" x1="0" x2="${W}" gradientUnits="userSpaceOnUse">
          <stop offset="0" stop-color="var(--accent)" stop-opacity="0"/>
          <stop offset=".22" stop-color="var(--accent)" stop-opacity=".9"/>
          <stop offset=".86" stop-color="var(--accent)" stop-opacity=".9"/>
          <stop offset="1" stop-color="var(--accent)" stop-opacity="0"/>
        </linearGradient>
        <linearGradient id="${id}b" x1="${x0 - 70}" x2="${x + 70}" gradientUnits="userSpaceOnUse">
          <stop offset="0" stop-color="var(--accent)" stop-opacity="0"/>
          <stop offset=".18" stop-color="var(--accent)" stop-opacity="1"/>
          <stop offset=".82" stop-color="var(--accent)" stop-opacity="1"/>
          <stop offset="1" stop-color="var(--accent)" stop-opacity="0"/>
        </linearGradient>
      </defs>
      <path class="base" d="M 0 ${y} L ${W} ${y}" stroke="url(#${id}f)"/>
      <path class="pulse" d="${d}" stroke="url(#${id}b)"/>
      ${o.tick === false ? '' : `<text class="tick" x="${x0}" y="${y + 26}">··· ——— ···</text>`}`;
  }

  /* ─────────────── Jackson's scope ───────────────
     kinds: answer (approved) · voice (live mic, with phosphor persistence) · thinking (slow sine) ·
            working (∞ Lissajous) · waiting (low sine, frozen) · idle (flat line) · error (dot) */
  function scope(svg) {
    const w = +svg.getAttribute('width'), h = +svg.getAttribute('height');
    const kind = svg.dataset.kind || 'answer';
    const sw = svg.dataset.sw || (h >= 40 ? 1.6 : 1.5);
    const cy = h / 2;
    const id = 'g' + (++uid);
    svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
    svg.innerHTML = '';
    const add = (tag, attrs) => {
      const e = document.createElementNS(NS, tag);
      for (const k in attrs) e.setAttribute(k, attrs[k]);
      svg.append(e); return e;
    };
    const base = () => add('path', { d: `M 0 ${cy} L ${w} ${cy}`, stroke: 'var(--accent)', 'stroke-opacity': kind === 'idle' ? 0.3 : 0.22, 'stroke-width': 1, fill: 'none' });
    const line = (d, extra = {}) => add('path', { d, fill: 'none', stroke: 'var(--accent)', 'stroke-width': sw, 'stroke-linejoin': 'round', 'stroke-linecap': 'round', ...extra });

    if (kind === 'idle') {
      add('path', { d: `M 0 ${cy} L ${w} ${cy}`, stroke: 'var(--accent)', 'stroke-opacity': 0.55, 'stroke-width': sw, 'stroke-linecap': 'round', fill: 'none' });
      return;
    }
    if (kind === 'error') {
      base(); add('circle', { cx: w / 2, cy, r: 2, fill: 'var(--bad)' }); return;
    }
    base();
    let d = '';
    if (kind === 'answer') {
      const amp = +(svg.dataset.amp || h * 0.43), freq = +(svg.dataset.freq || 3.2), seed = +(svg.dataset.seed || 0.7);
      for (let i = 0; i <= w; i += 1) {
        const t = i / w, env = Math.sin(Math.PI * t) ** 1.6;
        const v = Math.sin(t * freq * 2 * Math.PI + seed) * 0.62 + Math.sin(t * freq * 5.3 * Math.PI + seed * 2) * 0.28 + Math.sin(t * freq * 11.7 * Math.PI) * 0.1;
        d += (i ? ' L ' : 'M ') + i + ' ' + (cy - v * env * amp).toFixed(2);
      }
      line(d);
    } else if (kind === 'thinking' || kind === 'waiting') {
      const amp = +(svg.dataset.amp || h * (kind === 'waiting' ? 0.2 : 0.32)), cycles = +(svg.dataset.freq || 1.6), seed = +(svg.dataset.seed || 0.4);
      for (let i = 0; i <= w; i += 0.5) {
        const t = i / w, env = Math.sin(Math.PI * t) ** 0.7;
        d += (i ? ' L ' : 'M ') + i + ' ' + (cy - Math.sin(t * cycles * 2 * Math.PI + seed) * env * amp).toFixed(2);
      }
      line(d);
    } else if (kind === 'working') {
      const ax = w / 2 - sw - 1, ay = h / 2 - sw - 0.5;
      for (let k = 0; k <= 360; k += 1) {
        const t = (k / 360) * 2 * Math.PI;
        d += (k ? ' L ' : 'M ') + (w / 2 + ax * Math.sin(t)).toFixed(2) + ' ' + (cy + ay * Math.sin(2 * t)).toFixed(2);
      }
      line(d + ' Z');
    } else if (kind === 'voice') {
      // speech: syllable envelopes over a carrier; older signal (left) fades like CRT phosphor persistence
      const period = +(svg.dataset.period || 7.5);
      const amp = +(svg.dataset.amp || h * 0.46);
      const syl = svg.dataset.syl ? JSON.parse(svg.dataset.syl) : [[.04, .018, .25], [.1, .025, .55], [.16, .02, .8], [.215, .022, .5], [.3, .03, .9], [.365, .02, .62], [.43, .026, .35], [.52, .022, .72], [.58, .028, 1], [.645, .02, .58], [.72, .024, .82], [.79, .02, .45], [.86, .026, .95], [.925, .022, .7], [.985, .02, .85]];
      const env = (t) => syl.reduce((a, [c, s, k]) => a + k * Math.exp(-((t - c) ** 2) / (2 * s * s)), 0);
      for (let i = 0; i <= w; i += 0.5) {
        const t = i / w;
        const v = Math.sin((i / period) * 2 * Math.PI) * 0.7 + Math.sin((i / period) * 2 * Math.PI * 2.3 + 1.1) * 0.3;
        const e = Math.min(1, env(t)) * (0.12 + 0.88 * Math.min(1, t * 7));
        d += (i ? ' L ' : 'M ') + i + ' ' + (cy - v * e * amp).toFixed(2);
      }
      const defs = add('defs', {});
      defs.innerHTML = `<linearGradient id="${id}" x1="0" x2="${w}" gradientUnits="userSpaceOnUse">
          <stop offset="0" stop-color="var(--accent)" stop-opacity=".08"/>
          <stop offset=".55" stop-color="var(--accent)" stop-opacity=".55"/>
          <stop offset="1" stop-color="var(--accent)" stop-opacity="1"/></linearGradient>`;
      line(d, { stroke: `url(#${id})` });
      const endV = Math.sin((w / period) * 2 * Math.PI) * 0.7 + Math.sin((w / period) * 2 * Math.PI * 2.3 + 1.1) * 0.3;
      add('circle', { cx: w - 0.5, cy: (cy - endV * Math.min(1, env(1)) * amp).toFixed(2), r: 2.2, fill: 'var(--accent)' });
    }
  }

  /* ─────────────── top bar (defaults = the approved desktop) ─────────────── */
  const BAR_ICONS = ['wifi', 'volume', 'battery'];
  function bar(o = {}) {
    const el = o.el || document.querySelector('header.bar');
    if (!el) return;
    const ws = o.ws || [[1, 'on'], [2, ''], [3, ''], [4, 'empty']];
    const title = o.title === undefined ? ['Терминал', 'tts-finetune'] : o.title;
    const job = o.job === undefined ? { label: 'обучение', pct: 62 } : o.job;
    const gpu = o.gpu === undefined ? ['64°', '11,2/24 ГБ'] : o.gpu;
    const jack = o.jackson || 'active'; // active | idle | listening
    const jackMini = jack === 'listening'
      ? `<div class="jack-mini live"><svg data-i="mic"></svg><svg class="scope" data-kind="voice" data-period="3" data-amp="4.4" width="22" height="10"></svg></div>`
      : `<div class="jack-mini ${jack === 'idle' ? 'idle' : ''}"><svg class="scope" data-kind="${jack === 'idle' ? 'idle' : 'answer'}" data-amp="4" data-freq="1.6" data-seed="0.2" width="22" height="10"></svg></div>`;
    el.innerHTML = `
      <div class="bar-left">
        <div class="mark"><svg class="morse"></svg></div>
        <div class="ws">${ws.map(([n, c]) => `<span class="${c}">${n}</span>`).join('')}</div>
        ${title ? `<div class="win-title">${title[0]}${title[1] ? `<i>/</i><span>${title[1]}</span>` : ''}</div>` : ''}
      </div>
      <div class="bar-right">
        ${o.extraRight || ''}
        ${job ? `<div class="seg"><span class="dot${job.done ? ' ok' : ''}"></span><span>${job.label}</span>${job.pct != null ? `<span class="meter acc"><i style="width:${job.pct}%"></i></span><span>${job.pct}%</span>` : ''}</div>` : ''}
        ${gpu ? `<div class="seg"><span class="k">GPU</span><span>${gpu[0]}</span><span class="k">·</span><span>${gpu[1]}</span></div>` : ''}
        <div class="ico${o.pressed ? ' pressed' : ''}">${BAR_ICONS.map((k) => `<svg viewBox="0 0 24 24">${ICONS[k]}</svg>`).join('')}</div>
        <div class="seg">${o.layout || 'RU'}</div>
        ${jackMini}
        <time>${o.date || 'Чт 24 сен'}<b>${o.time || '18:42'}</b></time>
      </div>`;
  }

  /* ─────────────── shared window bodies ─────────────── */
  function training(state = 'running') {
    const head = `<span class="a">›</span> svoya run train.py
<span class="m">  среда    </span>torch 2.13 · CUDA 13.0 · RTX 4090 <span class="d">24 ГБ</span>
<span class="m">  модель   </span>qwen3-tts-0.6b <span class="d">+</span> LoRA r16
<span class="m">  данные   </span>ru-voice <span class="d">·</span> 48 213 примеров
<span class="m">  трекинг  </span><span class="c">localhost:7860</span> <span class="d">(trackio)</span>
`;
    if (state === 'done') {
      return head + `
<span class="m">эпоха 3/3</span>  <span class="a">█████████████████████████</span>  100%
<span class="d">           loss</span> 0.298 <span class="g">↓</span>   <span class="d">2 900 шагов за</span> 54 мин
<span class="g">•</span> готово <span class="m">runs/0924-1832/final</span> <span class="d">· 312 МБ</span>
<span class="cur"></span>`;
    }
    return head + `
<span class="m">эпоха 2/3</span>  <span class="a">████████████████░░░░░░░░░</span>  62%
<span class="d">           loss</span> 0.412 <span class="g">↓</span>   <span class="d">3,1 шаг/с · ещё</span> 18 мин
<span class="g">•</span> чекпойнт <span class="m">runs/0924-1832/step-1800</span>
<span class="cur"></span>`;
  }

  function winControls() {
    return `<div class="ctl">
        <span><svg viewBox="0 0 8 8"><path d="M1.5 4h5"/></svg></span>
        <span><svg viewBox="0 0 8 8"><path d="M1.5 1.5h5v5h-5z"/></svg></span>
        <span><svg viewBox="0 0 8 8"><path d="M1.8 1.8l4.4 4.4M6.2 1.8L1.8 6.2"/></svg></span>
      </div>`;
  }

  /* ─────────────── ComfyUI node graph (themed; used inside app windows) ───────────────
     g = { nodes: [{ id, x, y, w, title, ins: [[name, type]], outs: [[name, type]], widgets: [[label, value]],
                     state: 'missing' | 'running' | 'done', img: 'photo' | 'video', note }],
           links: [[fromId, outIndex, toId, inIndex]] }  — types: model · text · image · latent · video · lora */
  const HEAD = 25, SLOT = 18, PAD = 5, WID = 22;
  function comfy(el, g) {
    const byId = {};
    const nodes = g.nodes.map((n) => {
      const rows = Math.max((n.ins || []).length, (n.outs || []).length);
      const img = n.img ? (n.imgH || 86) + 8 : 0;
      const h = HEAD + PAD + rows * SLOT + (n.widgets || []).length * WID + img + (n.note ? 26 : 0) + (n.body ? n.bodyH || 60 : 0) + 7;
      const o = { ...n, rows, h };
      byId[n.id] = o; return o;
    });
    const port = (n, side, i) => ({ x: side === 'in' ? n.x : n.x + n.w, y: n.y + HEAD + PAD + i * SLOT + SLOT / 2 });
    const typeOf = (n, side, i) => ((side === 'in' ? n.ins : n.outs)[i] || [])[1];
    let links = '';
    (g.links || []).forEach(([a, ai, b, bi]) => {
      const A = port(byId[a], 'out', ai), B = port(byId[b], 'in', bi);
      const dx = Math.max(40, Math.abs(B.x - A.x) * 0.5);
      const t = typeOf(byId[a], 'out', ai);
      const broken = byId[a].state === 'missing' || byId[b].state === 'missing';
      links += `<path class="lk t-${t}${broken ? ' broken' : ''}" d="M ${A.x} ${A.y} C ${A.x + dx} ${A.y}, ${B.x - dx} ${B.y}, ${B.x} ${B.y}"/>`;
    });
    const html = nodes.map((n) => {
      const slots = [];
      for (let i = 0; i < n.rows; i++) {
        const a = (n.ins || [])[i], b = (n.outs || [])[i];
        slots.push(`<div class="slot">${a ? `<span class="in t-${a[1]}"><i></i>${a[0]}</span>` : '<span></span>'}${b ? `<span class="out t-${b[1]}">${b[0]}<i></i></span>` : ''}</div>`);
      }
      const w = (n.widgets || []).map(([l, v]) => `<div class="w"><span>${l}</span><b>${v}</b></div>`).join('');
      const img = n.img ? `<div class="pv ${n.img}" style="height:${n.imgH || 86}px"></div>` : '';
      const note = n.note ? `<div class="nnote">${n.note}</div>` : '';
      const body = n.body ? `<div class="nbody">${n.body}</div>` : '';
      return `<div class="cnode ${n.state || ''}" style="left:${n.x}px; top:${n.y}px; width:${n.w}px; height:${n.h}px">
          <div class="h"><i></i><span>${n.title}</span>${n.badge ? `<em>${n.badge}</em>` : ''}</div>
          <div class="slots">${slots.join('')}</div>${w}${img}${note}${body}</div>`;
    }).join('');
    el.innerHTML = `<svg class="links">${links}</svg>${html}`;
  }

  /* ─────────────── training loss chart (Trackio window) ───────────────
     o = { total: steps planned, now: current step, final: loss at `now`, val: final val loss } */
  function lossChart(svg, o = {}) {
    const W = +svg.getAttribute('width'), H = +svg.getAttribute('height');
    const total = o.total || 2900, now = o.now || 1800;
    const m = { l: 34, r: 8, t: 10, b: 24 };
    const X = (s) => m.l + (s / total) * (W - m.l - m.r);
    const lo = 0.2, hi = 1.4;
    const Y = (v) => m.t + (1 - (v - lo) / (hi - lo)) * (H - m.t - m.b);
    const start = 1.32, floor = o.floor ?? 0.245;
    const k = -now / Math.log((o.final - floor) / (start - floor));          // decay that lands on o.final at `now`
    const noise = (s) => (Math.sin(s * 12.9898) * 43758.5453) % 1;           // deterministic, −1…1
    const loss = (s) => floor + (start - floor) * Math.exp(-s / k);
    let raw = '', ema = '', e = loss(0);
    for (let s = 0; s <= now; s += 10) {
      const v = loss(s) + noise(s + 1) * 0.05 * (0.35 + Math.exp(-s / 900));
      e = s ? e * 0.8 + v * 0.2 : v;
      raw += (s ? ' L ' : 'M ') + X(s).toFixed(1) + ' ' + Y(v).toFixed(1);
      ema += (s ? ' L ' : 'M ') + X(s).toFixed(1) + ' ' + Y(s === now ? o.final : s < 40 ? loss(s) : e).toFixed(1);
    }
    let val = '', dots = '';
    for (let s = 300; s <= now; s += 300) {
      const v = s === now ? o.val : loss(s) + (o.val - o.final) * (0.55 + 0.45 * (s / now));
      val += (val ? ' L ' : 'M ') + X(s).toFixed(1) + ' ' + Y(v).toFixed(1);
      dots += `<circle cx="${X(s).toFixed(1)}" cy="${Y(v).toFixed(1)}" r="2.6" class="vd"/>`;
    }
    const grid = [0.4, 0.8, 1.2].map((v) => `<path class="gl" d="M ${m.l} ${Y(v)} H ${W - m.r}"/><text class="ax" x="${m.l - 8}" y="${Y(v) + 3.5}" text-anchor="end">${v.toFixed(1)}</text>`).join('');
    const xt = [0, 1000, 2000, total].map((s) => `<text class="ax" x="${X(s)}" y="${H - 6}" text-anchor="${s === 0 ? 'start' : s === total ? 'end' : 'middle'}">${s.toLocaleString('ru-RU')}</text>`).join('');
    const ep = [total / 3, (2 * total) / 3].map((s) => `<path class="ep" d="M ${X(s)} ${m.t} V ${H - m.b}"/>`).join('');
    const nowX = X(now);
    const ck = (o.ckpt || [600, 1200, 1800, 2400]).filter((s) => s <= now)
      .map((s) => `<path class="ck" d="M ${X(s) - 3.5} ${H - m.b} L ${X(s)} ${H - m.b - 5} L ${X(s) + 3.5} ${H - m.b} Z"/>`).join('');
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    svg.innerHTML = `${grid}<path class="bl" d="M ${m.l} ${H - m.b} H ${W - m.r}"/>${ck}${ep}${xt}
      <path class="raw" d="${raw}"/><path class="val" d="${val}"/>${dots}<path class="ema" d="${ema}"/>
      ${now < total ? `<path class="now" d="M ${nowX} ${m.t} V ${H - m.b}"/>` : ''}
      <circle class="end" cx="${nowX}" cy="${Y(o.final)}" r="3.2"/>`;
  }

  /* Trackio window content. state: running | done; w: chart width */
  function trackio(state = 'running', w = 650, h = 210) {
    const done = state === 'done';
    const o = done ? { total: 2900, now: 2900, final: 0.298, val: 0.331 } : { total: 2900, now: 1800, final: 0.412, val: 0.455 };
    return `<div class="trk">
        <div class="trk-head">
          <span class="run">tts-finetune<span>/</span>0924-1832</span>
          ${done ? '<span class="tag ok"><span class="dot ok"></span>готово · 54 мин</span>' : '<span class="tag acc"><span class="dot"></span>идёт · эпоха 2/3</span>'}
          <span class="spacer"></span>
          <span class="meta">${done ? 'завершено в 19:26' : 'обновлено 5 с назад'}</span>
        </div>
        <div class="trk-cards">
          <div><div class="k">loss</div><div class="v">${done ? '0.298<small>↓ 0.114</small>' : '0.412<small>↓ 0.021</small>'}</div></div>
          <div><div class="k">val_loss</div><div class="v">${done ? '0.331<small>↓ 0.124</small>' : '0.455<small>↓ 0.017</small>'}</div></div>
          <div><div class="k">lr</div><div class="v">${done ? '0<small class="dim">cosine</small>' : '1.8e-4<small class="dim">cosine</small>'}</div></div>
          <div><div class="k">шаг</div><div class="v">${done ? '2 900<small class="dim">/ 2 900</small>' : '1 800<small class="dim">/ 2 900</small>'}</div></div>
        </div>
        <div class="trk-chart">
          <div class="lg"><span><i></i>train/loss</span><span><i class="v"></i>val/loss</span><em>▲ чекпойнт каждые 600 шагов</em></div>
          <svg class="loss" width="${w}" height="${h}" data-o='${JSON.stringify(o)}'></svg>
        </div>
      </div>`;
  }

  /* ─────────────── init ─────────────── */
  function init(o = {}) {
    if (o.bar !== false) bar(o.bar || {});
    document.querySelectorAll('[data-training]').forEach((e) => { e.innerHTML = training(e.dataset.training); });
    document.querySelectorAll('[data-trackio]').forEach((e) => { e.innerHTML = trackio(e.dataset.trackio, +(e.dataset.w || 650), +(e.dataset.h || 210)); });
    document.querySelectorAll('[data-ctl]').forEach((e) => { e.outerHTML = winControls(); });
    document.querySelectorAll('svg.signal').forEach((s) => signal(s, JSON.parse(s.dataset.o || '{}')));
    document.querySelectorAll('svg.morse').forEach((s) => mark(s, +(s.dataset.s || 1), +(s.dataset.lit ?? 9)));
    document.querySelectorAll('svg.scope').forEach(scope);
    document.querySelectorAll('svg.loss').forEach((s) => lossChart(s, JSON.parse(s.dataset.o || '{}')));
    icons();
    document.fonts.ready.then(() => { document.body.dataset.ready = '1'; });
  }

  return { q, NS, MORSE, ICONS, icons, mark, signal, scope, bar, training, trackio, comfy, lossChart, init };
})();
