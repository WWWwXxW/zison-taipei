(function () {
  'use strict';

  var CITY_ORDER = ['台北市', '新北市', '桃園市', '新竹市', '新竹縣', '台中市', '南投縣', '彰化市', '彰化縣', '雲林縣', '嘉義市', '嘉義縣', '台南市', '高雄市'];
  /** District names that collide across cities nationwide — option/URL use city|district. */
  var AMBIGUOUS_DISTRICTS = {
    '北區': 1, '南區': 1, '東區': 1, '西區': 1, '中區': 1
  };

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

  function getParam(name) {
    return new URLSearchParams(location.search).get(name);
  }

  function setParams(obj) {
    var sp = new URLSearchParams(location.search);
    Object.keys(obj).forEach(function (k) {
      if (obj[k] == null || obj[k] === '') sp.delete(k);
      else sp.set(k, obj[k]);
    });
    var q = sp.toString();
    history.replaceState(null, '', q ? ('?' + q) : location.pathname);
  }

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function encodeDistrictValue(city, district) {
    if (!district) return '';
    if (AMBIGUOUS_DISTRICTS[district] && city) return city + '|' + district;
    return district;
  }

  function parseDistrictParam(raw, cityHint) {
    if (!raw) return { city: cityHint || '', district: '' };
    if (raw.indexOf('|') !== -1) {
      var parts = raw.split('|');
      return { city: parts[0] || cityHint || '', district: parts.slice(1).join('|') };
    }
    return { city: cityHint || '', district: raw };
  }

  function citiesPresent(list) {
    var set = {};
    list.forEach(function (r) {
      if (r.city) set[r.city] = 1;
    });
    var ordered = CITY_ORDER.filter(function (c) { return set[c]; });
    Object.keys(set).sort(function (a, b) {
      return a.localeCompare(b, 'zh-Hant');
    }).forEach(function (c) {
      if (ordered.indexOf(c) === -1) ordered.push(c);
    });
    return ordered;
  }

  function districtsForCity(list, city) {
    if (!city) return [];
    var set = {};
    list.forEach(function (r) {
      if (r.city === city && r.district) set[r.district] = 1;
    });
    return Object.keys(set).sort(function (a, b) {
      return a.localeCompare(b, 'zh-Hant');
    });
  }

  function cuisineOptions(list) {
    var set = new Set();
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

  function isLineUrl(u) {
    if (!u) return false;
    return /line\.me|lin\.ee|line\.naver/i.test(u);
  }

  function isOddleUrl(u) {
    if (!u) return false;
    return /oddle\.me/i.test(u);
  }

  /** Channel chips inferred from existing fields only (電話 / LINE / Oddle / 官網). */
  function channelChips(r) {
    var chips = [];
    if (r.phone) {
      chips.push('<span class="channel phone">電話</span>');
    }
    var hasLine = !!(r.lineUrl || r.lineId) || isLineUrl(r.orderUrl);
    if (hasLine) {
      chips.push('<span class="channel line">LINE</span>');
    }
    if (isOddleUrl(r.orderUrl)) {
      chips.push('<span class="channel oddle">Oddle</span>');
    } else if (r.orderUrl && !isLineUrl(r.orderUrl)) {
      chips.push('<span class="channel web">官網</span>');
    }
    if (!chips.length) return '';
    return '<div class="channels" aria-label="訂餐通道">' + chips.join('') + '</div>';
  }

  /** Delivery chips: 起送 primary; 免運 secondary (never the hero). */
  function deliveryChips(r) {
    var chips = [];
    var label = r.deliveryMinLabel;
    var isFreeLabel = label && String(label).indexOf('免運') !== -1;
    if (label && String(label).trim() && label !== '未知' && String(label).toUpperCase() !== 'UNKNOWN' && !isFreeLabel) {
      chips.push('<span class="badge delivery-min">' + escapeHtml(label) + '</span>');
    }
    var freeLabel = null;
    if (isFreeLabel) {
      freeLabel = String(label).trim();
    } else if (r.freeDeliveryThreshold != null && r.freeDeliveryThreshold !== '') {
      var n = Number(r.freeDeliveryThreshold);
      freeLabel = isFinite(n) ? ('滿 $' + n + ' 免運') : null;
    }
    if (freeLabel) {
      chips.push('<span class="badge delivery-free" title="免運門檻通常較高，付運費往往仍划算">' + escapeHtml(freeLabel) + '</span>');
    }
    return chips.slice(0, 2);
  }

  /** District chip (solid) + muted city chip — sitewide. */
  function placeBadges(r) {
    var badges = [];
    var district = r.district || '';
    var city = r.city || '';
    if (district) {
      badges.push('<span class="badge district">' + escapeHtml(district) + '</span>');
    }
    if (city) {
      badges.push('<span class="badge city">' + escapeHtml(city) + '</span>');
    }
    if (!badges.length) {
      badges.push('<span class="badge district">未標行政區</span>');
    }
    return badges;
  }

  function cardHtml(r) {
    var badges = placeBadges(r);
    if (r.chain) badges.push('<span class="badge chain">連鎖</span>');

    var actions = [];
    var oh = orderHref(r);
    if (oh) {
      actions.push('<a class="btn btn-primary" href="' + escapeHtml(oh) + '" target="_blank" rel="noopener noreferrer">前往官方訂餐 ↗</a>');
    }
    if (r.phone) {
      actions.push('<a class="btn btn-ghost" href="tel:' + escapeHtml(r.phone.replace(/-/g, '')) + '">' + escapeHtml(r.phone) + '</a>');
    }
    actions.push('<a class="btn btn-ghost" href="detail.html?id=' + encodeURIComponent(r.id) + '">詳情</a>');

    return (
      '<article class="card" data-id="' + escapeHtml(r.id) + '">' +
        '<div class="badges">' + badges.join('') + '</div>' +
        '<h2><a href="detail.html?id=' + encodeURIComponent(r.id) + '">' + escapeHtml(r.name) + '</a></h2>' +
        channelChips(r) +
        (r.cuisine ? '<p class="cuisine-line">' + escapeHtml(r.cuisine) + '</p>' : '') +
        (r.address ? '<p class="addr">' + escapeHtml(r.address) + '</p>' : '') +
        (r.hours ? '<p class="hours">時段：' + escapeHtml(r.hours) + '</p>' : '') +
        (function () { var dc = deliveryChips(r).join(''); return dc ? ('<div class="delivery-conditions" aria-label="外送條件">' + dc + '</div>') : ''; })() +
        '<div class="actions">' + actions.join('') + '</div>' +
      '</article>'
    );
  }

  function matches(r, q, city, district, cuisine) {
    if (city && r.city !== city) return false;
    if (district && r.district !== district) return false;
    if (cuisine) {
      var blob = ((r.cuisine || '') + ' ' + (r.cuisineTags || []).join(' ')).toLowerCase();
      if (blob.indexOf(cuisine.toLowerCase()) === -1) return false;
    }
    if (q) {
      var hay = [
        r.name, r.city, r.district, r.address, r.cuisine,
        (r.cuisineTags || []).join(' '), r.phone, r.evidence
      ].join(' ').toLowerCase();
      var tokens = q.toLowerCase().trim().split(/\s+/);
      for (var i = 0; i < tokens.length; i++) {
        if (hay.indexOf(tokens[i]) === -1) return false;
      }
    }
    return true;
  }

  function rebuildDistrictSelect(dEl, data, city, selectedDistrict) {
    dEl.innerHTML = '';
    if (!city) {
      dEl.disabled = true;
      var ph = document.createElement('option');
      ph.value = '';
      ph.textContent = '先選縣市';
      dEl.appendChild(ph);
      return;
    }
    dEl.disabled = false;
    var all = document.createElement('option');
    all.value = '';
    all.textContent = '全部行政區';
    dEl.appendChild(all);
    districtsForCity(data, city).forEach(function (d) {
      var opt = document.createElement('option');
      opt.value = encodeDistrictValue(city, d);
      opt.textContent = d;
      dEl.appendChild(opt);
    });
    var want = encodeDistrictValue(city, selectedDistrict);
    if (want && Array.prototype.some.call(dEl.options, function (o) { return o.value === want; })) {
      dEl.value = want;
    } else {
      dEl.value = '';
    }
  }

  function initIndex() {
    var data = window.RESTAURANTS || [];
    var qEl = $('#q');
    var cityEl = $('#city');
    var dEl = $('#district');
    var cEl = $('#cuisine');
    var listEl = $('#list');
    var countEl = $('#count');
    if (!listEl || !cityEl || !dEl) return;

    citiesPresent(data).forEach(function (city) {
      var opt = document.createElement('option');
      opt.value = city;
      opt.textContent = city;
      cityEl.appendChild(opt);
    });

    cuisineOptions(data).forEach(function (c) {
      var opt = document.createElement('option');
      opt.value = c;
      opt.textContent = c;
      cEl.appendChild(opt);
    });

    qEl.value = getParam('q') || '';
    cEl.value = getParam('cuisine') || '';

    var rawCity = getParam('city');
    var rawDistrict = getParam('district') || '';
    var parsed = parseDistrictParam(rawDistrict, rawCity || '');
    // Default city = 台北市 when no city param (and district didn't imply otherwise)
    var city = rawCity;
    if (city == null || city === undefined) {
      // absent from URL → default Taipei
      city = parsed.city || '台北市';
    }
    // empty string means user chose 全部縣市
    var district = parsed.district || '';
    if (parsed.city && (!city || city === parsed.city)) {
      city = parsed.city;
    }
    if (district && city && data.every(function (r) {
      return !(r.city === city && r.district === district);
    })) {
      // invalid combo
      district = '';
    }
    cityEl.value = city || '';
    rebuildDistrictSelect(dEl, data, city || '', district);

    function render() {
      var q = qEl.value.trim();
      var cityVal = cityEl.value;
      var parsedD = parseDistrictParam(dEl.value, cityVal);
      var districtVal = parsedD.district;
      var cuisine = cEl.value;
      var districtParam = encodeDistrictValue(cityVal, districtVal) || null;
      setParams({
        q: q || null,
        city: cityVal || null,
        district: districtParam,
        cuisine: cuisine || null
      });

      var filtered = data.filter(function (r) {
        return matches(r, q, cityVal, districtVal, cuisine);
      });
      filtered.sort(function (a, b) {
        return (a.name || '').localeCompare(b.name || '', 'zh-Hant');
      });

      countEl.innerHTML = '顯示 <strong>' + filtered.length + '</strong> / ' + data.length + ' 家' +
        (cityVal ? ('（目前：' + escapeHtml(cityVal) + (districtVal ? (' · ' + escapeHtml(districtVal)) : '') + '）') : '');
      var heroStats = $('#hero-stats');
      if (heroStats) {
        heroStats.innerHTML = '目前收錄 <strong>' + data.length + '</strong> 家店家自送通道';
      }
      if (!filtered.length) {
        listEl.innerHTML = '<div class="empty">找不到符合條件的店家，請調整關鍵字或篩選。</div>';
        return;
      }
      listEl.innerHTML = filtered.map(cardHtml).join('');
    }

    var t;
    qEl.addEventListener('input', function () {
      clearTimeout(t);
      t = setTimeout(render, 120);
    });
    cityEl.addEventListener('change', function () {
      rebuildDistrictSelect(dEl, data, cityEl.value, '');
      render();
    });
    dEl.addEventListener('change', render);
    cEl.addEventListener('change', render);
    render();
  }

  function findByIdOrSlug(id) {
    var data = window.RESTAURANTS || [];
    return data.find(function (r) { return r.id === id || r.slug === id; });
  }

  function initDetail() {
    var root = $('#detail');
    if (!root) return;
    var id = getParam('id') || getParam('slug');
    var r = id ? findByIdOrSlug(id) : null;
    if (!r) {
      root.innerHTML =
        '<div class="detail-card"><h1>找不到店家</h1>' +
        '<p>請回到<a href="index.html">首頁</a>重新搜尋。</p></div>';
      return;
    }
    document.title = r.name + '｜自送';

    function row(label, value, html) {
      if (value == null || value === '') return '';
      return '<div><dt>' + escapeHtml(label) + '</dt><dd>' +
        (html ? value : escapeHtml(String(value))) + '</dd></div>';
    }

    var badges = placeBadges(r);
    deliveryChips(r).forEach(function (c) { badges.push(c); });
    if (r.chain) badges.push('<span class="badge chain">全國／大型連鎖</span>');

    var actions = [];
    var oh = orderHref(r);
    if (oh) {
      actions.push('<a class="btn btn-primary" href="' + escapeHtml(oh) + '" target="_blank" rel="noopener noreferrer">前往官方訂餐</a>');
    }
    if (r.phone) {
      actions.push('<a class="btn btn-ghost" href="tel:' + escapeHtml(r.phone.replace(/-/g, '')) + '">撥打電話 ' + escapeHtml(r.phone) + '</a>');
    }
    if (r.lineUrl) {
      actions.push('<a class="btn btn-ghost" href="' + escapeHtml(r.lineUrl) + '" target="_blank" rel="noopener noreferrer">LINE 官方帳號</a>');
    }

    var freeText = '';
    if (r.freeDeliveryThreshold != null) {
      freeText = typeof r.freeDeliveryThreshold === 'number'
        ? ('滿 NT$' + r.freeDeliveryThreshold)
        : String(r.freeDeliveryThreshold);
    }
    var feeText = '';
    if (r.deliveryFee != null) {
      feeText = typeof r.deliveryFee === 'number'
        ? ('NT$' + r.deliveryFee)
        : String(r.deliveryFee);
    }

    var backCity = r.city ? ('?city=' + encodeURIComponent(r.city)) : '';
    root.innerHTML =
      '<div class="detail-card">' +
        '<a class="back-link" href="index.html' + backCity + '">← 回目錄</a>' +
        '<div class="badges">' + badges.join('') + '</div>' +
        '<h1>' + escapeHtml(r.name) + '</h1>' +
        channelChips(r) +
        '<div class="notice">本站不代訂、不收款。請直接在餐廳官方網站／LINE／電話下單。外送門檻與運費以店家官方結帳頁為準。</div>' +
        '<div class="actions">' +
          actions.join('') +
        '</div>' +
        '<dl>' +
          row('料理類型', r.cuisine) +
          row('縣市', r.city) +
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
          row('外送條件備註', r.deliveryNotes) +
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
