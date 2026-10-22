/* 自送 usage events → GoatCounter. Event names:
   order-<shopid>  官方訂餐連結點擊   line-<shopid> LINE 訂餐點擊
   tel-<shopid>    電話點擊           outbound      其他外站連結
   search / search-empty (title=關鍵字)
   suggest-open / report-open / report-open-shop / suggest-submit / report-submit

   goatcounter.count() is only called after count.js has installed it.
   Clicks that happen earlier stay queued. pagehide flushes with sendBeacon
   (count.js's own transport, or the same POST if the CDN script never loads).
   GET /count is 405 on zisong.goatcounter.com, so this file never falls back
   to an image beacon. Listeners do not cancel navigation. */
(function () {
  if (window.zisongTrack) return;
  var DEFAULT_ENDPOINT = 'https://zisong.goatcounter.com/count';
  var queue = [];
  var timer = null;

  function page() { return location.pathname.replace(/^\/+/, '/') || '/'; }

  function endpoint() {
    var s = document.querySelector('script[data-goatcounter]');
    var url = s && (s.getAttribute('data-goatcounter') || s.dataset.goatcounter);
    return url || DEFAULT_ENDPOINT;
  }

  function countReady() {
    return !!(window.goatcounter && typeof window.goatcounter.count === 'function');
  }

  function sendDirect(ev) {
    var url = endpoint() +
      '?p=' + encodeURIComponent(ev[0]) +
      '&t=' + encodeURIComponent(ev[1] || '') +
      '&e=true' +
      '&rnd=' + Math.random().toString(36).slice(2, 7);
    try {
      if (navigator.sendBeacon && navigator.sendBeacon(url)) return true;
    } catch (e) {}
    try {
      var xhr = new XMLHttpRequest();
      xhr.open('POST', url, true);
      xhr.send();
      return true;
    } catch (e2) {}
    return false;
  }

  function flush() {
    if (!queue.length) return true;
    if (!countReady()) return false;
    var pending = queue;
    queue = [];
    for (var i = 0; i < pending.length; i++) {
      var ev = pending[i];
      try {
        window.goatcounter.count({ path: ev[0], title: ev[1], event: true });
      } catch (err) {
        queue.push(ev);
      }
    }
    return queue.length === 0;
  }

  function arm() {
    if (timer) return;
    var tries = 0;
    timer = setInterval(function () {
      tries += 1;
      if (flush() || tries > 120) {
        clearInterval(timer);
        timer = null;
      }
    }, 250);
  }

  function track(name, title) {
    if (!name) return;
    queue.push([String(name).slice(0, 120), String(title || page()).slice(0, 200)]);
    if (!flush()) arm();
  }
  window.zisongTrack = track;

  function flushOnLeave() {
    if (flush()) return;
    var pending = queue;
    queue = [];
    for (var i = 0; i < pending.length; i++) sendDirect(pending[i]);
  }

  var gcScript = document.querySelector('script[data-goatcounter]');
  if (gcScript && !countReady()) gcScript.addEventListener('load', flush);
  window.addEventListener('pagehide', flushOnLeave);

  function shopId(el) {
    var c = el.closest && el.closest('[data-id]');
    if (c) return c.getAttribute('data-id');
    var m = location.pathname.match(/\/shop\/([^\/]+)\.html$/);
    if (m) { try { return decodeURIComponent(m[1]); } catch (e) { return m[1]; } }
    if (/\/detail\.html$/.test(location.pathname)) {
      var q = new URLSearchParams(location.search).get('id');
      if (q) return q;
    }
    return '';
  }

  function lineHost(host) {
    return /(^|\.)line\.me$|(^|\.)lin\.ee$|(^|\.)line\.naver\.jp$/i.test(host || '');
  }

  function onActivate(e) {
    var t = e.target;
    if (!t || !t.closest) return;
    if (typeof e.button === 'number' && e.button !== 0 && e.type === 'click') return;
    var a = t.closest('a[href]');
    if (a) {
      var href = a.getAttribute('href') || '';
      var id = shopId(a);
      if (/^tel:/i.test(href)) { track(id ? 'tel-' + id : 'tel', page()); return; }
      if (/^mailto:/i.test(href)) { track('mailto', page()); return; }
      var external = /^https?:/i.test(href) || /^\/\//.test(href);
      if (external && a.hostname && a.hostname !== location.hostname) {
        if (!id) { track('outbound', a.hostname + ' @ ' + page()); return; }
        var kind = lineHost(a.hostname) ? 'line' : 'order';
        track(kind + '-' + id, a.hostname + ' @ ' + page());
        return;
      }
    }
    var b = t.closest('[data-report-open],[data-report-shop]');
    if (b) {
      if (b.hasAttribute('data-report-shop')) track('report-open-shop', b.getAttribute('data-report-shop'));
      else track(b.getAttribute('data-report-open') === 'suggest' ? 'suggest-open' : 'report-open', page());
    }
  }

  document.addEventListener('click', onActivate, true);
  document.addEventListener('auxclick', onActivate, true);

  document.addEventListener('submit', function (e) {
    var f = e.target;
    if (!f || !f.id) return;
    if (f.id === 'form-suggest') track('suggest-submit', page());
    else if (f.id === 'form-problem') track('report-submit', page());
  }, true);
})();
