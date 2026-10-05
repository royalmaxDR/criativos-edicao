// Garimpagem na Biblioteca de Anuncios da Meta (facebook.com/ads/library).
// Cole no CONSOLE da aba da biblioteca (ou execute via a ferramenta de JavaScript do seu agente/navegador).
// Funciona com a interface em portugues, ingles e espanhol.
//
//   1) Cole este arquivo inteiro.            -> define window.CRP
//   2) CRP.start({ target: 60 })             -> comeca a rolar a pagina e coletar em segundo plano
//   3) CRP.status()                          -> { count, running, stalled }  (repita ate running=false)
//   4) copy(CRP.result())  /  console.log(CRP.result())   -> JSON para salvar como ads.json
//
// Cada item: { rank, library_id, start_date (YYYY-MM-DD), src (video), poster (miniatura), page_text }
//   rank = ordem de aparicao na pagina (se a busca esta ordenada por impressoes, rank 0 = mais impressoes)
// Obs.: o Facebook carrega poucos anuncios por vez e as vezes trava (ver references/TROUBLESHOOTING.md).
(function () {
  const MONTHS = { jan: 1, fev: 2, feb: 2, mar: 3, abr: 4, apr: 4, mai: 5, may: 5, jun: 6, jul: 7, ago: 8, aug: 8,
    set: 9, sep: 9, out: 10, oct: 10, nov: 11, dez: 12, dec: 12, ene: 1, dic: 12 };
  const ID_RE = /(?:Identifica[cç][aã]o da biblioteca|Library ID|ID de la biblioteca)\s*:?\s*(\d{6,})/i;
  const pad = (n) => String(n).padStart(2, '0');
  const iso = (y, m, d) => `${y}-${pad(m)}-${pad(d)}`;

  function parseDate(t) {
    let m = t.match(/(\d{1,2})\s+de\s+([a-zç]{3,})\.?\s+de\s+(\d{4})/i) || t.match(/(\d{1,2})\s+([a-zç]{3,})\.?,?\s+(\d{4})/i);
    if (m && MONTHS[m[2].slice(0, 3).toLowerCase()]) return iso(m[3], MONTHS[m[2].slice(0, 3).toLowerCase()], m[1]);
    m = t.match(/([A-Za-z]{3,})\.?\s+(\d{1,2}),?\s+(\d{4})/);
    if (m && MONTHS[m[1].slice(0, 3).toLowerCase()]) return iso(m[3], MONTHS[m[1].slice(0, 3).toLowerCase()], m[2]);
    return null;
  }

  function cardOf(el) {
    let e = el;
    for (let i = 0; i < 16 && e; i++) {
      e = e.parentElement;
      if (!e) break;
      const t = e.innerText || '';
      if (ID_RE.test(t) && t.length < 2500) return { e, t };
    }
    return null;
  }

  const S = (window.__crp = window.__crp || { ads: {}, order: [], running: false, iv: null, stalled: 0, last: 0 });

  function collect() {
    document.querySelectorAll('video').forEach((v) => {
      const c = cardOf(v);
      if (!c) return;
      const id = c.t.match(ID_RE)[1];
      if (S.ads[id]) return;
      S.ads[id] = {
        library_id: id,
        start_date: parseDate(c.t),
        src: v.currentSrc || v.src || null,
        poster: v.poster || null,
        page_text: c.t.split('\n').map((s) => s.trim()).filter(Boolean).slice(0, 12).join(' | '),
      };
      S.order.push(id);
    });
  }

  window.CRP = {
    start(opts) {
      const o = Object.assign({ target: 60, maxMinutes: 8, intervalMs: 1500, stallTicks: 30 }, opts || {});
      if (S.iv) clearInterval(S.iv);
      S.running = true; S.stalled = 0; S.last = Object.keys(S.ads).length;
      const t0 = Date.now(); let k = 0;
      S.iv = setInterval(() => {
        collect(); k++;
        const n = Object.keys(S.ads).length;
        S.stalled = n === S.last ? S.stalled + 1 : 0; S.last = n;
        const done = n >= o.target || S.stalled >= o.stallTicks || Date.now() - t0 > o.maxMinutes * 60000;
        if (done) { clearInterval(S.iv); S.iv = null; S.running = false; return; }
        window.scrollTo(0, document.documentElement.scrollHeight - (k % 2 ? 900 : 0)); // vai e volta: forca novo carregamento
      }, o.intervalMs);
      return 'coletando...';
    },
    stop() { if (S.iv) clearInterval(S.iv); S.iv = null; S.running = false; collect(); return Object.keys(S.ads).length; },
    status() { collect(); return { count: Object.keys(S.ads).length, running: S.running, stalled: S.stalled }; },
    result() {
      collect();
      return JSON.stringify(S.order.map((id, i) => Object.assign({ rank: i }, S.ads[id])), null, 1);
    },
  };
  return 'CRP pronto. Use CRP.start({target:60}), CRP.status(), copy(CRP.result()).';
})();
