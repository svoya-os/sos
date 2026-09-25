// Renders the first-run wizard's preview pictures from the design mockups.
//   node shell/tools/gen_previews.js          (needs `playwright` + a Chromium)
// Output: shell/assets/setup/theme-<id>.png   (Look step: the mini desktops of setup-look.html)
//         shell/assets/setup/layout-<id>-<theme>.png (Layout step: Clean / Classic / Hacker)
// Every picture is the 1440×900 mockup desktop scaled into a 232×145 card at 3× density.
// SPDX-License-Identifier: Apache-2.0
const path = require('path');
const fs = require('fs');
const { chromium } = require('playwright');

const ROOT = path.resolve(__dirname, '..', '..');
const MOCK = path.join(ROOT, 'design', 'mockups');
const OUT = path.join(ROOT, 'shell', 'assets', 'setup');
const CHROME = process.env.CHROME || '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';

// window bodies used by the layout previews
const TERM = `<pre class="term-body" data-training="running"></pre>`;
const NOTES = `<div style="padding:18px 22px;font:400 14px/1.7 'Plex Sans';color:var(--text-dim)">
  <div style="font:500 22px/1.3 'Plex Sans';color:var(--text);margin-bottom:12px">Заметки</div>
  <div>• датасет: ru-voice, 48 213 примеров</div><div>• LoRA r16, эпоха 3</div>
  <div>• проверить громкость на 7-й минуте</div><div style="margin-top:14px;color:var(--text-faint)">сохранено · 18:40</div></div>`;
const FILES = `<div style="padding:14px 18px;font:400 13px/2.1 'Plex Mono';color:var(--text-dim)">
  <div>▸ datasets</div><div>▸ runs</div><div style="color:var(--text)">▾ tts-finetune</div>
  <div>&nbsp;&nbsp;train.py</div><div>&nbsp;&nbsp;config.toml</div><div>&nbsp;&nbsp;README.md</div></div>`;

function win(x, y, w, h, title, body, opts = {}) {
  const tb = opts.bare ? '' : `<div class="titlebar"><div class="t"><span class="glyph"></span><b>${title}</b></div><i data-ctl></i></div>`;
  const border = opts.active ? 'border-color: var(--accent);' : '';
  const radius = opts.bare ? 'border-radius: 11px;' : '';
  return `<section class="window" style="left:${x}px; top:${y}px; width:${w}px; height:${h}px; ${border}${radius}">${tb}${body}</section>`;
}

const LAYOUTS = {
  clean: (t) => `
    <header class="bar"></header>
    ${win(96, 170, 720, 420, 'Файлы', FILES)}
    ${win(560, 300, 760, 440, 'Терминал', TERM, { active: false })}`,
  classic: (t) => `
    <header class="bar" style="top:auto;bottom:0;border-bottom:0;border-top:1px solid var(--line)"></header>
    ${win(96, 90, 720, 420, 'Файлы', FILES)}
    ${win(560, 250, 760, 440, 'Терминал', TERM)}`,
  hacker: (t) => `
    <header class="bar"></header>
    ${win(12, 42, 700, 846, '', TERM, { bare: true, active: true })}
    ${win(724, 42, 704, 417, '', NOTES, { bare: true })}
    ${win(724, 471, 704, 417, '', FILES, { bare: true })}`,
};

// The mockups predate the `sos` command name: show it as users will type it.
const FIX = `function fixCommand() {
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) n.nodeValue = n.nodeValue.replace(/\\bsvoya (run|theme|modules)/g, 'sos $1');
}`;

function page(theme, body) {
  return `<!doctype html><html data-theme="${theme}"><head><meta charset="utf-8">
  <link rel="stylesheet" href="file://${MOCK}/fonts.css"><link rel="stylesheet" href="file://${MOCK}/tokens.css">
  <link rel="stylesheet" href="file://${MOCK}/desktop.css"><link rel="stylesheet" href="file://${MOCK}/components.css">
  <script src="file://${MOCK}/shell.js"></script>
  <style>body{margin:0;background:#000} .window .ctl{display:none}</style><script>${FIX}</script></head>
  <body><div class="screen"><div class="wallpaper"><svg class="signal"></svg><div class="grain"></div></div>${body}</div>
  <script>
    document.querySelectorAll('header.bar').forEach((el) => Svoya.bar({ el }));
    document.querySelectorAll('[data-ctl]').forEach((el) => { el.outerHTML = ''; });
    Svoya.init({ bar: false });
    fixCommand();
  </script></body></html>`;
}

(async () => {
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: CHROME });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 3 * 232 / 1440 });

  // Look step: the four cards of setup-look.html, captured without their rounded frame
  const look = await ctx.newPage();
  await look.setViewportSize({ width: 1440, height: 900 });
  const lctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 3 });
  const lp = await lctx.newPage();
  await lp.goto('file://' + path.join(MOCK, 'setup-look.html') + '?theme=graphite');
  await lp.addStyleTag({ content: '.pv{border-radius:0 !important;box-shadow:none !important}.pv::after{display:none !important}' });
  await lp.addScriptTag({ content: FIX + '\nfixCommand();' });
  await lp.waitForTimeout(400);
  const ids = ['graphite', 'paper', 'auto', 'phosphor'];
  const cards = await lp.$$('.themes .card .pv');
  for (let i = 0; i < ids.length; i++) {
    await cards[i].screenshot({ path: path.join(OUT, `theme-${ids[i]}.png`) });
  }
  await look.close();

  // Layout step: a mini desktop per preset, dark and light
  for (const [id, body] of Object.entries(LAYOUTS)) {
    for (const theme of ['graphite', 'paper']) {
      const p = await ctx.newPage();
      const file = path.join(OUT, `.tmp-${id}-${theme}.html`);
      fs.writeFileSync(file, page(theme, body(theme)));
      await p.goto('file://' + file + '?theme=' + theme);
      await p.waitForTimeout(300);
      await p.screenshot({ path: path.join(OUT, `layout-${id}-${theme}.png`) });
      fs.unlinkSync(file);
      await p.close();
    }
  }
  await browser.close();
  console.log('previews ->', path.relative(ROOT, OUT));
})();
