/* 自送 usage events → GoatCounter. Event names:
   order-<shopid>  官方訂餐連結點擊   line-<shopid> LINE 訂餐點擊
   tel-<shopid>    電話點擊           outbound      其他外站連結
   search / search-empty (title=關鍵字)
   suggest-open / report-open / report-open-shop / suggest-submit / report-submit */
(function () {
  if (window.zisongTrack) return;
  var queue = [];
  function page() { return location.pathname.replace(/^\/+/, '/') || '/'; }
  function flush() {
    var gc = window.goatcounter;
    if (!gc || typeof gc.count !== 'function') return false;
    while (queue.length) {
      var ev = queue.shift();
      try { gc.count({ path: ev[0], title: ev[1], event: true }); } catch (e) {}
    }
    return true;
  }
  function track(name, title) {
    if (!name) return;
    queue.push([String(name).slice(0, 120), String(title || page()).slice(0, 200)]);
    if (!flush()) {
      var tries = 0;
      var iv = setInterval(function () { if (flush() || ++tries > 20) clearInterval(iv); }, 500);
    }
  }
  window.zisongTrack = track;

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

  document.addEventListener('click', function (e) {
    var t = e.target;
    if (!t || !t.closest) return;
    var a = t.closest('a[href]');
    if (a) {
      var href = a.getAttribute('href') || '';
      var id = shopId(a);
      if (/^tel:/i.test(href)) { track(id ? 'tel-' + id : 'tel', page()); return; }
      if (/^mailto:/i.test(href)) { track('mailto', page()); return; }
      if (/^https?:/i.test(href) && a.hostname && a.hostname !== location.hostname) {
        if (!id) { track('outbound', a.hostname + ' @ ' + page()); return; }
        var kind = /(^|\.)line\.me$|(^|\.)lin\.ee$/i.test(a.hostname) ? 'line' : 'order';
        track(kind + '-' + id, a.hostname + ' @ ' + page());
        return;
      }
    }
    var b = t.closest('[data-report-open],[data-report-shop]');
    if (b) {
      if (b.hasAttribute('data-report-shop')) track('report-open-shop', b.getAttribute('data-report-shop'));
      else track(b.getAttribute('data-report-open') === 'suggest' ? 'suggest-open' : 'report-open', page());
    }
  }, true);

  document.addEventListener('submit', function (e) {
    var f = e.target;
    if (!f || !f.id) return;
    if (f.id === 'form-suggest') track('suggest-submit', page());
    else if (f.id === 'form-problem') track('report-submit', page());
  }, true);
})();
