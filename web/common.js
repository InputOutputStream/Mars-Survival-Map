// common.js - language support shared by both viewers. English is the default; the choice is remembered.
// Language files live in lang/<code>.js (see lang/help.html). Missing strings fall back along meta.fallback, then English.
const LANG = (() => {
  let s = null;
  try { s = localStorage.getItem('lang'); } catch (e) {}
  return (s && LANGUAGES.some(l => l.code === s)) ? s : 'en';
})();
const LANGINFO = LANGUAGES.find(l => l.code === LANG) || LANGUAGES[0];
const IS_RTL = LANGINFO.dir === 'rtl';
function loadLanguage() {              // call once, synchronously, from a classic script before the page script
  document.write('<script src="lang/en.js"><\/script>');
  if (LANG !== 'en') document.write('<script src="lang/' + LANG + '.js"><\/script>');
}
function makeT(page) {
  const chain = () => [LANG, ...((((window.LANGS || {})[LANG] || {}).meta || {}).fallback || []), 'en'];
  return (k, ...a) => {
    for (const c of chain()) {
      const d = ((window.LANGS || {})[c] || {})[page];
      if (d && d[k] !== undefined) { const v = d[k]; return typeof v === 'function' ? v(...a) : v; }
    }
    return k;
  };
}
const TC = makeT('common');
function langToggle() {                // a language menu (name kept for the pages that call it)
  const s = document.createElement('select'); s.className = 'lang'; s.setAttribute('aria-label', TC('langlabel'));
  for (const l of LANGUAGES) s.add(new Option(l.name, l.code, false, l.code === LANG));
  s.onchange = () => { try { localStorage.setItem('lang', s.value); } catch (e) {} location.reload(); };
  return s;
}
(function applyDirection() {
  document.documentElement.lang = LANG;
  if (IS_RTL) {                        // text flows right to left; the map and the sidebars keep their places
    document.documentElement.classList.add('rtl');
    const st = document.createElement('style');
    st.textContent = 'html.rtl aside, html.rtl .float, html.rtl #hover, html.rtl #banner { direction: rtl; text-align: right; } html.rtl .leaflet-container, html.rtl #map { direction: ltr; }';
    document.head.appendChild(st);
  }
  addEventListener('DOMContentLoaded', () => {
    const meta = (window.LANGS || {})[LANG] && window.LANGS[LANG].meta;
    if (LANG === 'en' || !meta || meta.status === 'reviewed') return;
    const n = document.createElement('a'); n.className = 'draftnote'; n.href = 'lang/help.html'; n.textContent = TC('draftnote') + ' · ' + TC('draftlink');
    document.body.appendChild(n);
  });
})();
const MARS_R = 3396190;
