(function () {
  'use strict';

  const DISTRICTS = [
    '大同區','中山區','中正區','萬華區','大安區','松山區',
    '信義區','內湖區','南港區','士林區','北投區','文山區','台北多區'
  ];

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

  function getParam(name) {
    return new URLSearchParams(location.search).get(name);
  }

  function setParams(obj) {
    const sp = new URLSearchParams(location.search);
    Object.keys(obj).forEach(function (k) {
      if (obj[k] == null || obj[k] === '') sp.delete(k);
      else sp.set(k, obj[k]);
    });
    const q = sp.toString();
    history.replaceState(null, '', q ? ('?' + q) : location.pathname);
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function cuisineOptions(list) {
    const set = new Set();
    list.forEach(function (r) {
      (r.cuisineTags || []).forEach(function (t) { if (t) set.add(t); });
      if (r.cuisine) set.add(r.cuisine.split(/[、,/／]/)[0].trim());
    });
    return Array.from(set).filter(Boolean).sort(function (a, b) {
      return a.localeCompare(b, 'zh-Hant');
    });
  }

  function orderHref(r) {
    return r.orderUrl || r.lineUrl || null;
  }

  function cardHtml(r) {
    const badges = [];
    badges.push('<span class="badge district">' + escapeHtml(r.district || '台北') + '</span>');
    if (r.chain) badges.push('<span class="badge chain">連鎖</span>');
    if (r.featured) badges.push('<span class="badge">精選</span>');

    const actions = [];
    const oh = orderHref(r);
    if (oh) {
      actions.push('<a class="btn btn-primary" href="' + escapeHtml(oh) + '" target="_blank" rel="noopener noreferrer">前往訂餐</a>');
    }
    if (r.phone) {
      actions.push('<a class="btn btn-ghost" href="tel:' + escapeHtml(r.phone.replace(/-/g, '')) + '">' + escapeHtml(r.phone) + '</a>');
    }
    actions.push('<a class="btn btn-ghost" href="detail.html?id=' + encodeURIComponent(r.id) + '">詳情</a>');

    return (
      '<article class="card" data-id="' + escapeHtml(r.id) + '">' +
        '<div class="badges">' + badges.join('') + '</div>' +
        '<h2><a href="detail.html?id=' + encodeURIComponent(r.id) + '">' + escapeHtml(r.name) + '</a></h2>' +
        (r.cuisine ? '<p class="cuisine-line">' + escapeHtml(r.cuisine) + '</p>' : '') +
        (r.address ? '<p class="addr">' + escapeHtml(r.address) + '</p>' : '') +
        (r.hours ? '<p class="hours">時段：' + escapeHtml(r.hours) + '</p>' : '') +
        '<div class="actions">' + actions.join('') + '</div>' +
      '</article>'
    );
  }

  function matches(r, q, district, cuisine) {
    if (district && r.district !== district) return false;
    if (cuisine) {
      const blob = ((r.cuisine || '') + ' ' + (r.cuisineTags || []).join(' ')).toLowerCase();
      if (blob.indexOf(cuisine.toLowerCase()) === -1) return false;
    }
    if (q) {
      const hay = [
        r.name, r.district, r.address, r.cuisine,
        (r.cuisineTags || []).join(' '), r.phone, r.evidence
      ].join(' ').toLowerCase();
      const tokens = q.toLowerCase().trim().split(/\s+/);
      for (let i = 0; i < tokens.length; i++) {
        if (hay.indexOf(tokens[i]) === -1) return false;
      }
    }
    return true;
  }

  function initIndex() {
    const data = window.RESTAURANTS || [];
    const qEl = $('#q');
    const dEl = $('#district');
    const cEl = $('#cuisine');
    const listEl = $('#list');
    const countEl = $('#count');
    if (!listEl) return;

    DISTRICTS.forEach(function (d) {
      if (!data.some(function (r) { return r.district === d; })) return;
      const opt = document.createElement('option');
      opt.value = d;
      opt.textContent = d;
      dEl.appendChild(opt);
    });

    cuisineOptions(data).forEach(function (c) {
      const opt = document.createElement('option');
      opt.value = c;
      opt.textContent = c;
      cEl.appendChild(opt);
    });

    qEl.value = getParam('q') || '';
    dEl.value = getParam('district') || '';
    cEl.value = getParam('cuisine') || '';

    function render() {
      const q = qEl.value.trim();
      const district = dEl.value;
      const cuisine = cEl.value;
      setParams({ q: q || null, district: district || null, cuisine: cuisine || null });

      const filtered = data.filter(function (r) { return matches(r, q, district, cuisine); });
      // featured first, then name
      filtered.sort(function (a, b) {
        if (!!b.featured - !!a.featured) return (!!b.featured) - (!!a.featured);
        return (a.name || '').localeCompare(b.name || '', 'zh-Hant');
      });

      countEl.innerHTML = '顯示 <strong>' + filtered.length + '</strong> / ' + data.length + ' 家';
      if (!filtered.length) {
        listEl.innerHTML = '<div class="empty">找不到符合條件的店家，請調整關鍵字或篩選。</div>';
        return;
      }
      listEl.innerHTML = filtered.map(cardHtml).join('');
    }

    let t;
    qEl.addEventListener('input', function () {
      clearTimeout(t);
      t = setTimeout(render, 120);
    });
    dEl.addEventListener('change', render);
    cEl.addEventListener('change', render);
    render();
  }

  function findByIdOrSlug(id) {
    const data = window.RESTAURANTS || [];
    return data.find(function (r) { return r.id === id || r.slug === id; });
  }

  function initDetail() {
    const root = $('#detail');
    if (!root) return;
    const id = getParam('id') || getParam('slug');
    const r = id ? findByIdOrSlug(id) : null;
    if (!r) {
      root.innerHTML =
        '<div class="detail-card"><h1>找不到店家</h1>' +
        '<p>請回到<a href="index.html">首頁</a>重新搜尋。</p></div>';
      return;
    }
    document.title = r.name + '｜自送台北';

    function row(label, value, html) {
      if (value == null || value === '') return '';
      return '<div><dt>' + escapeHtml(label) + '</dt><dd>' +
        (html ? value : escapeHtml(String(value))) + '</dd></div>';
    }

    const badges = [];
    badges.push('<span class="badge district">' + escapeHtml(r.district || '') + '</span>');
    if (r.chain) badges.push('<span class="badge chain">全國／大型連鎖</span>');

    const actions = [];
    const oh = orderHref(r);
    if (oh) {
      actions.push('<a class="btn btn-primary" href="' + escapeHtml(oh) + '" target="_blank" rel="noopener noreferrer">前往官方訂餐</a>');
    }
    if (r.phone) {
      actions.push('<a class="btn btn-ghost" href="tel:' + escapeHtml(r.phone.replace(/-/g, '')) + '">撥打電話 ' + escapeHtml(r.phone) + '</a>');
    }
    if (r.lineUrl) {
      actions.push('<a class="btn btn-ghost" href="' + escapeHtml(r.lineUrl) + '" target="_blank" rel="noopener noreferrer">LINE 官方帳號</a>');
    }

    let freeText = '';
    if (r.freeDeliveryThreshold != null) {
      freeText = typeof r.freeDeliveryThreshold === 'number'
        ? ('滿 NT$' + r.freeDeliveryThreshold)
        : String(r.freeDeliveryThreshold);
    }
    let feeText = '';
    if (r.deliveryFee != null) {
      feeText = typeof r.deliveryFee === 'number'
        ? ('NT$' + r.deliveryFee)
        : String(r.deliveryFee);
    }

    root.innerHTML =
      '<div class="detail-card">' +
        '<p style="margin:0 0 .5rem"><a href="index.html">← 回目錄</a></p>' +
        '<div class="badges">' + badges.join('') + '</div>' +
        '<h1>' + escapeHtml(r.name) + '</h1>' +
        '<div class="notice">本站不代訂、不收款。請直接在餐廳官方網站／LINE／電話下單。</div>' +
        '<div class="actions" style="display:flex;flex-wrap:wrap;gap:.45rem;margin:.5rem 0 1rem">' +
          actions.join('') +
        '</div>' +
        '<dl>' +
          row('料理類型', r.cuisine) +
          row('行政區', r.district) +
          row('地址', r.address) +
          row('電話', r.phone ? ('<a href="tel:' + escapeHtml(r.phone.replace(/-/g, '')) + '">' + escapeHtml(r.phone) + '</a>') : null, true) +
          row('官方訂餐連結', oh ? ('<a href="' + escapeHtml(oh) + '" target="_blank" rel="noopener noreferrer">' + escapeHtml(oh) + '</a>') : null, true) +
          row('LINE', r.lineId || r.lineUrl) +
          row('接單／外送時段', r.hours) +
          row('配送範圍說明', r.range) +
          row('免運門檻（參考）', freeText || null) +
          row('運費（參考）', feeText || null) +
          row('最後核對', r.checkedAt) +
          row('說明／條件摘要', r.terms) +
          row('收錄依據摘要', r.evidence) +
        '</dl>' +
      '</div>';
  }

  document.addEventListener('DOMContentLoaded', function () {
    if ($('#list')) initIndex();
    if ($('#detail')) initDetail();
  });
})();
