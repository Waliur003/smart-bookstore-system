/* Everything here enhances pages that already work as plain links and forms. */
(function () {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const calm = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const money = cents => '$' + (cents / 100).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const parse = html => new DOMParser().parseFromString(html, 'text/html');
  const csrf = () => ($('input[name=_csrf]') || {}).value || '';
  const reveal = root => $$('[data-js]', root).forEach(el => { el.hidden = false; });
  reveal(document);

  /* Messages */
  const toasts = $('[data-toasts]');
  function drop(t) { t.classList.add('is-out'); setTimeout(() => t.remove(), 260); }
  function arm(t) { if (!t.classList.contains('toast--error')) setTimeout(() => drop(t), 6000); }
  function toast(text, kind) {
    const t = document.createElement('div');
    t.className = 'toast toast--' + kind;
    t.setAttribute('role', kind === 'error' ? 'alert' : 'status');
    const s = document.createElement('span'); s.textContent = text;
    const b = document.createElement('button'); b.type = 'button'; b.dataset.dismiss = ''; b.setAttribute('aria-label', 'Dismiss'); b.textContent = '×';
    t.append(s, b); toasts.append(t); arm(t);
  }
  $$('[data-toast]').forEach(arm);
  document.addEventListener('click', e => { const b = e.target.closest('[data-dismiss]'); if (b) drop(b.closest('.toast')); });

  /* Requests: the server answers with a whole page, and we take the parts we need. */
  async function send(url, data) {
    const r = await fetch(url, { method: 'POST', body: new URLSearchParams(data), credentials: 'same-origin' });
    if (r.status === 400) throw new Error('Your session expired. Refresh the page and try again.');
    if (r.status === 404) throw new Error('That book is no longer available to order.');
    if (!r.ok) throw new Error('That did not work. Refresh the page and try again.');
    return parse(await r.text());
  }
  const flashes = doc => $$('[data-toast]', doc).map(t => ({ bad: t.classList.contains('toast--error'), text: t.textContent.trim() }));

  /* Cart */
  const drawer = $('#cart-drawer'), drawerBody = $('[data-drawer-body]');
  async function cartDoc(doc) {
    if (doc && $('#cart-root', doc)) return doc;
    return parse(await (await fetch('/cart', { credentials: 'same-origin' })).text());
  }
  function paintCart(doc) {
    const from = $('[data-cart-count]', doc), to = $('[data-cart-count]');
    if (from && to) {
      if (from.textContent !== to.textContent) { to.classList.remove('is-bump'); void to.offsetWidth; to.classList.add('is-bump'); }
      to.textContent = from.textContent; to.hidden = from.hidden;
    }
    const lines = $('[data-cart-lines]', doc);
    if (lines && drawerBody) { drawerBody.replaceChildren(document.importNode(lines, true)); reveal(drawerBody); }
    const page = $('#cart-root'), fresh = $('#cart-root', doc);
    if (page && fresh) { page.replaceWith(document.importNode(fresh, true)); reveal($('#cart-root')); }
  }
  async function openCart() {
    paintCart(await cartDoc());
    if (drawer && !drawer.open) drawer.showModal();
  }
  const opener = $('[data-cart-open]');
  if (opener && !$('#cart-root')) opener.addEventListener('click', e => {
    if (e.metaKey || e.ctrlKey || e.shiftKey) return;
    e.preventDefault(); openCart().catch(() => { location.href = opener.href; });
  });
  document.addEventListener('submit', async e => {
    const f = e.target.closest('form[data-add], form[data-remove]'); if (!f) return;
    e.preventDefault();
    const btn = $('button:not([type=button])', f), adding = f.hasAttribute('data-add');
    if (btn) btn.disabled = true;
    try {
      const doc = await send(f.action, Object.fromEntries(new FormData(f)));
      const bad = flashes(doc).find(x => x.bad);
      if (bad) toast(bad.text, 'error');
      paintCart(await cartDoc(doc));
      if (adding && !bad) {
        const was = btn.textContent; btn.textContent = 'Added'; btn.classList.add('is-done');
        setTimeout(() => { btn.textContent = was; btn.classList.remove('is-done'); }, 1600);
        if (drawer && !$('#cart-root') && !drawer.open) drawer.showModal();
      }
    } catch (err) { toast(err.message, 'error'); }
    if (btn) btn.disabled = false;
  });
  document.addEventListener('click', async e => {
    const b = e.target.closest('[data-cart-by]'); if (!b) return;
    const box = b.closest('[data-cart-step]'), qty = +box.dataset.qty, by = +b.dataset.cartBy, area = b.closest('[data-cart-lines]');
    area.classList.add('is-busy');
    try {
      let doc;
      if (by > 0) doc = await send(box.dataset.addUrl, { _csrf: csrf(), quantity: 1 });
      else { await send(box.dataset.removeUrl, { _csrf: csrf() }); doc = await send(box.dataset.addUrl, { _csrf: csrf(), quantity: qty - 1 }); }
      const bad = flashes(doc).find(x => x.bad); if (bad) toast(bad.text, 'error');
      paintCart(await cartDoc(doc));
    } catch (err) { toast(err.message, 'error'); paintCart(await cartDoc()); }
  });

  /* Dialogs */
  document.addEventListener('click', e => {
    const open = e.target.closest('[data-open]'); if (open) document.getElementById(open.dataset.open).showModal();
    if (e.target.closest('[data-close]')) e.target.closest('dialog').close();
    if (e.target.tagName === 'DIALOG') {
      const r = e.target.getBoundingClientRect();
      if (e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom) e.target.close();
    }
    const menu = $('.menu[open]'); if (menu && !menu.contains(e.target)) menu.open = false;
  });
  document.addEventListener('keydown', e => { const m = $('.menu[open]'); if (e.key === 'Escape' && m) { m.open = false; $('summary', m).focus(); } });

  /* Quantity */
  document.addEventListener('click', e => {
    const b = e.target.closest('[data-step-by]'); if (!b) return;
    const i = $('input', b.parentElement), n = (parseInt(i.value, 10) || 1) + +b.dataset.stepBy;
    i.value = Math.min(+i.max, Math.max(1, n));
  });

  /* Search suggestions */
  const find = $('[data-find]'), list = $('[data-suggest]'), input = find && $('.find__input', find);
  const covers = JSON.parse($('#cover-map').textContent || '{}');
  if (find) {
    let timer, at = -1, seq = 0;
    input.setAttribute('role', 'combobox'); input.setAttribute('aria-controls', 'suggest'); input.setAttribute('aria-expanded', 'false'); input.setAttribute('aria-autocomplete', 'list');
    const close = () => { list.hidden = true; at = -1; input.setAttribute('aria-expanded', 'false'); input.removeAttribute('aria-activedescendant'); };
    const marked = (text, q) => {
      const out = document.createDocumentFragment(), i = text.toLowerCase().indexOf(q.toLowerCase());
      if (i < 0) { out.append(text); return out; }
      const m = document.createElement('mark'); m.textContent = text.slice(i, i + q.length);
      out.append(text.slice(0, i), m, text.slice(i + q.length)); return out;
    };
    async function suggest() {
      const q = input.value.trim(), mine = ++seq;
      if (q.length < 2) return close();
      let books;
      try { books = await (await fetch('/api/books?q=' + encodeURIComponent(q))).json(); } catch (_) { return close(); }
      if (mine !== seq) return;
      list.replaceChildren(); at = -1;
      books.slice(0, 5).forEach((b, i) => {
        const a = document.createElement('a'); a.href = '/book/' + encodeURIComponent(b.id); a.id = 'sg-' + i; a.setAttribute('role', 'option'); a.setAttribute('aria-selected', 'false'); a.tabIndex = -1;
        const art = document.createElement('span'); art.className = 'suggest__art'; const c = covers[b.id] || {};
        art.style.cssText = c.style || ''; if (c.art) art.style.backgroundImage = 'url(' + JSON.stringify(c.art) + ')';
        const t = document.createElement('span'), n = document.createElement('b'), by = document.createElement('small');
        n.append(marked(b.title, q)); by.append(marked(b.author, q)); t.append(n, by);
        const p = document.createElement('span'); p.textContent = money(b.price_cents);
        a.append(art, t, p); list.append(a);
      });
      if (!books.length) { const p = document.createElement('p'); p.className = 'muted'; p.textContent = 'No books match “' + q + '”.'; list.append(p); }
      list.hidden = false; input.setAttribute('aria-expanded', 'true');
    }
    input.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(suggest, 160); });
    input.addEventListener('focus', () => { if (input.value.trim().length > 1) suggest(); });
    input.addEventListener('keydown', e => {
      const opts = $$('a', list);
      if (e.key === 'Escape') return close();
      if (list.hidden || !opts.length) return;
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault(); at = (at + (e.key === 'ArrowDown' ? 1 : -1) + opts.length + (at < 0 && e.key === 'ArrowUp' ? 1 : 0)) % opts.length;
        opts.forEach((o, i) => o.setAttribute('aria-selected', String(i === at)));
        input.setAttribute('aria-activedescendant', opts[at].id); opts[at].scrollIntoView({ block: 'nearest' });
      } else if (e.key === 'Enter' && at >= 0) { e.preventDefault(); location.href = opts[at].href; }
    });
    document.addEventListener('click', e => { if (!find.contains(e.target)) close(); });
    find.addEventListener('focusout', e => { if (e.relatedTarget && !find.contains(e.relatedTarget)) close(); });
  }

  /* Front table */
  const table = $('[data-table]');
  if (table) {
    const tabs = $$('[data-tab]', table), panels = $$('[data-panel]', table);
    const pick = (i, focus) => {
      tabs.forEach((t, n) => { t.setAttribute('aria-selected', String(n === i)); t.tabIndex = n === i ? 0 : -1; });
      panels.forEach((p, n) => { p.hidden = n !== i; p.classList.toggle('is-in', n === i); });
      table.style.cssText = panels[i].dataset.tone;
      if (focus) tabs[i].focus();
    };
    tabs.forEach((t, i) => t.addEventListener('click', () => pick(i)));
    $('[role=tablist]', table).addEventListener('keydown', e => {
      const i = tabs.indexOf(document.activeElement), to = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: tabs.length - 1 }[e.key];
      if (i < 0 || to === undefined) return;
      e.preventDefault(); pick((to + tabs.length) % tabs.length, true);
    });
  }

  /* Tilt a book under the pointer */
  if (!calm && matchMedia('(hover: hover)').matches) $$('[data-tilt]').forEach(el => {
    const zone = el.closest('.table__panel, .detail__stage') || el;
    zone.addEventListener('pointermove', e => {
      const r = el.getBoundingClientRect(), x = Math.max(-1, Math.min(1, (e.clientX - r.left) / r.width - .5)), y = Math.max(-1, Math.min(1, (e.clientY - r.top) / r.height - .5));
      el.classList.add('is-live'); el.style.setProperty('--rx', x * 22 + 'deg'); el.style.setProperty('--ry', y * -12 + 'deg');
    });
    zone.addEventListener('pointerleave', () => { el.classList.remove('is-live'); el.style.removeProperty('--rx'); el.style.removeProperty('--ry'); });
  });

  /* Carry the chosen cover across to the book page */
  document.addEventListener('click', e => {
    const a = e.target.closest('a[data-morph]'); if (!a) return;
    const scope = a.closest('.card, .pick, .table__panel') || a, c = $('.cover', scope);
    $$('.is-morph').forEach(x => x.classList.remove('is-morph')); if (c) c.classList.add('is-morph');
  });
  addEventListener('pageshow', e => { if (e.persisted && !$('.detail')) $$('.is-morph').forEach(x => x.classList.remove('is-morph')); });

  /* Sort and filter */
  const grid = $('[data-grid]');
  if (grid && $('[data-sort]')) {
    const cards = $$('[data-card]', grid), sort = $('[data-sort]'), price = $('[data-filter-price]'), stock = $('[data-filter-stock]'), count = $('[data-count]'), empty = $('[data-empty]');
    const apply = () => {
      const [key, dir] = sort.value.split('-');
      const sorted = cards.slice().sort((a, b) => {
        const d = key === 'title' ? a.dataset.title.localeCompare(b.dataset.title) : a.dataset[key] - b.dataset[key];
        return (dir ? -d : d) || a.dataset.title.localeCompare(b.dataset.title);
      });
      let n = 0;
      sorted.forEach(c => { const ok = (price.value === price.max || +c.dataset.price <= +price.value) && (!stock.checked || c.dataset.available); c.hidden = !ok; if (ok) n++; grid.append(c); });
      count.textContent = n + (n === 1 ? ' book' : ' books'); empty.hidden = n > 0;
    };
    const run = () => {
      if (calm || !document.startViewTransition) return apply();
      cards.forEach(c => { c.style.viewTransitionName = 'card-' + c.dataset.id; });
      const t = document.startViewTransition(apply);
      t.ready.catch(() => {}); t.finished.finally(() => cards.forEach(c => { c.style.viewTransitionName = ''; }));
    };
    const out = $('[data-price-out]');
    price.addEventListener('input', () => { out.textContent = money(+price.value); });
    price.addEventListener('change', run); sort.addEventListener('change', run); stock.addEventListener('change', run);
    if (sort.value !== 'title' || price.value !== price.max || stock.checked) { out.textContent = money(+price.value); apply(); }
  }

  /* Tabs on the staff dashboard, remembered after saving */
  const bar = $('[data-tabs]');
  if (bar) {
    const tabs = $$('[role=tab]', bar);
    const show = (t, focus) => {
      tabs.forEach(x => { const on = x === t; x.setAttribute('aria-selected', String(on)); x.tabIndex = on ? 0 : -1; document.getElementById(x.getAttribute('aria-controls')).hidden = !on; });
      try { sessionStorage.setItem('staff-tab', t.id); } catch (_) { /* storage is optional */ }
      if (focus) t.focus();
    };
    let saved = null; try { saved = sessionStorage.getItem('staff-tab'); } catch (_) { /* storage is optional */ }
    show(tabs.find(t => t.id === saved) || tabs[0]);
    tabs.forEach(t => t.addEventListener('click', () => show(t)));
    bar.addEventListener('keydown', e => { const i = tabs.indexOf(document.activeElement), to = { ArrowRight: i + 1, ArrowLeft: i - 1 }[e.key]; if (to !== undefined) { e.preventDefault(); show(tabs[(to + tabs.length) % tabs.length], true); } });
  }
  $$('form[data-dirty]').forEach(f => {
    const btn = $('button', f); btn.disabled = true;
    f.ownerDocument.querySelectorAll('input[form="' + f.id + '"]').forEach(i => i.addEventListener('input', () => { btn.disabled = false; }));
  });

  /* Sign-in sample */
  const zone = $('[data-drop]');
  if (zone) {
    const file = $('input', zone), title = $('[data-drop-title]', zone), hint = $('[data-drop-hint]', zone), img = $('[data-drop-preview]', zone);
    const setup = () => {
      const voice = $('[data-method]:checked').value === 'voice';
      file.accept = voice ? 'audio/*' : 'image/*'; file.value = ''; img.hidden = true;
      title.textContent = voice ? 'Choose a voice clip' : 'Choose a photo of your face';
      hint.textContent = voice ? 'Use a short clip recorded just now.' : 'Use a photo taken just now, with one face in it.';
    };
    $$('[data-method]').forEach(r => r.addEventListener('change', setup)); setup();
    file.addEventListener('change', () => {
      const f = file.files[0]; if (!f) return setup();
      title.textContent = f.name; hint.textContent = 'Choose again to replace it.';
      img.hidden = !f.type.startsWith('image/'); if (!img.hidden) { img.src = URL.createObjectURL(f); img.onload = () => URL.revokeObjectURL(img.src); }
    });
    ['dragenter', 'dragover'].forEach(n => zone.addEventListener(n, () => zone.classList.add('is-over')));
    ['dragleave', 'drop'].forEach(n => zone.addEventListener(n, () => zone.classList.remove('is-over')));
  }

  /* Assistant */
  const ask = $('[data-ask]');
  if (ask) {
    const chat = $('[data-chat]'), box = $('textarea', ask), go = $('.composer__go', ask);
    const bubble = (cls, text) => { const d = document.createElement('div'); d.className = 'msg ' + cls; if (text) { const p = document.createElement('p'); p.className = 'preserve'; p.textContent = text; d.append(p); } chat.append(d); d.scrollIntoView({ block: 'nearest' }); return d; };
    ask.addEventListener('submit', async e => {
      e.preventDefault();
      const q = box.value.trim(); if (!q || go.disabled) return;
      bubble('msg--you', q); box.value = ''; go.disabled = true;
      const wait = bubble('msg--it'); wait.classList.add('typing'); wait.setAttribute('aria-label', 'Thinking'); wait.append(...[1, 2, 3].map(() => document.createElement('i')));
      try {
        const a = $('[data-answer]', await send('/assistant', { _csrf: csrf(), question: q }));
        if (!a) throw new Error('No answer came back. Try asking again.');
        wait.replaceWith(document.importNode(a, true));
      } catch (err) { wait.remove(); bubble('msg--it msg--err', err.message); }
      go.disabled = false; box.focus(); chat.lastElementChild.scrollIntoView({ block: 'nearest' });
    });
    box.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); ask.requestSubmit(); } });
    $$('[data-chip]').forEach(c => c.addEventListener('click', () => { box.value = c.textContent; ask.requestSubmit(); }));
  }

  /* Voice */
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const status = $('#voice-status');
  function listen(btn) {
    const say = t => { if (status) status.textContent = t; else if (t !== 'Listening...') toast(t, 'success'); };
    if (!Recognition) return say('Speech recognition is not available in this browser. Use the search box instead.');
    const r = new Recognition(); r.lang = 'en-US'; r.interimResults = false; r.maxAlternatives = 1;
    r.onresult = e => { const q = e.results[0][0].transcript; say('Searching for: ' + q); location.href = '/?q=' + encodeURIComponent(q); };
    r.onerror = () => say('We could not hear you. Use the search box instead.');
    r.onend = () => btn.classList.remove('is-on');
    r.start(); btn.classList.add('is-on'); say('Listening...');
  }
  const big = $('#voice-start'), small = $('[data-voice]');
  if (big) big.addEventListener('click', () => listen(big));
  if (small && Recognition) { small.hidden = false; small.addEventListener('click', () => listen(small)); }
})();
