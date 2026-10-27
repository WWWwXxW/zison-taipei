(function () {
  'use strict';

  var CITY_ORDER = ['台北市', '新北市', '基隆市', '桃園市', '新竹市', '新竹縣', '苗栗縣', '台中市', '南投縣', '彰化市', '彰化縣', '雲林縣', '嘉義市', '嘉義縣', '台南市', '高雄市'];
  /** District names that collide across cities nationwide — option/URL use city|district. */
  var AMBIGUOUS_DISTRICTS = {
    '北區': 1, '南區': 1, '東區': 1, '西區': 1, '中區': 1,
    '中正區': 1, '中山區': 1, '信義區': 1
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

  var TERM_LABELS = [
    ['Delivery fee (min listed)', '最低運費', false],
    ['Delivery fee max listed', '最高運費', false],
    ['Free-delivery threshold', '免運門檻', true],
    ['Minimum / shipping', '起送', false],
    ['Minimum order', '起送', false],
    ['Delivery fee', '運費', false],
    ['LINE ID', 'LINE ID', false],
    ['LINE', 'LINE', false],
    ['Range', '外送範圍', false]
  ];

  function blankish(value) {
    var s = String(value == null ? '' : value).trim().replace(/^[；;。．]+|[；;。．]+$/g, '');
    return !s || /^(unknown|n\/a|na|todo|null|none|undefined|-+|—+)$/i.test(s);
  }

  function formatAmount(raw) {
    if (!/^\d+(?:\.\d+)?$/.test(raw)) return '';
    var n = Number(raw);
    if (!isFinite(n)) return '';
    if (Math.round(n) === n) return 'NT$' + Math.round(n).toLocaleString('en-US');
    return 'NT$' + String(n);
  }

  function distanceKey(key) {
    var known = { within500m: '500公尺內', within1km: '1公里內', within2km: '2公里內' };
    if (known[key]) return known[key];
    var m = /^within(\d+)(m|km)$/.exec(key);
    if (!m) return '';
    return m[2] === 'm' ? (m[1] + '公尺內') : (m[1] + '公里內');
  }

  function formatThreshold(raw) {
    var text = String(raw || '').trim();
    if (blankish(text)) return '';
    var amount = formatAmount(text);
    if (amount) return amount;
    if (text.charAt(0) === '{' && text.charAt(text.length - 1) === '}') {
      try {
        var obj = JSON.parse(text);
        var parts = [];
        Object.keys(obj).forEach(function (key) {
          var label = distanceKey(key);
          var val = obj[key];
          if (!label || typeof val !== 'number') return;
          var shown = Math.round(val) === val ? Math.round(val) : val;
          parts.push(label + ' NT$' + (typeof shown === 'number' && Math.round(shown) === shown ? shown.toLocaleString('en-US') : shown));
        });
        return parts.join('、');
      } catch (e) { /* keep the original text below */ }
    }
    if (/unknown/i.test(text)) {
      text = text.replace(/\bUNKNOWN\b/gi, '未公開').replace(/^[；;\s]+|[；;\s]+$/g, '');
      if (blankish(text) || text === '未公開') return '';
    }
    return text;
  }

  /** Display-only cleanup of internal source/provenance labels (records keep the raw text). */
  var EN_DAYS = { Mon: '一', Tue: '二', Wed: '三', Thu: '四', Fri: '五', Sat: '六', Sun: '日' };
  function enTime(h, m, ap) {
    var n = Number(h) % 12; if (/pm/i.test(ap)) n += 12;
    return (n < 10 ? '0' : '') + n + ':' + m;
  }
  function englishHours(t) {
    if (!/\b(AM|PM|Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b/.test(t)) return t;
    t = t.replace(/",\s*"/g, ' ');
    t = t.replace(/(\d{1,2}):(\d{2})\s*(AM|PM)/g, function (_, h, m, ap) { return enTime(h, m, ap); });
    t = t.replace(/\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s*[-–]\s*(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b/g, function (_, a, b) { return '週' + EN_DAYS[a] + '至週' + EN_DAYS[b]; });
    t = t.replace(/\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\b/g, function (_, a) { return '週' + EN_DAYS[a]; });
    t = t.replace(/\bAM\s*/g, '上午 ').replace(/\bPM\s*/g, '下午 ');
    t = t.replace(/(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})/g, '$1–$2').replace(/,\s*/g, '、');
    return t;
  }
  var SRC_TAGS = /^(表|食記|\d{4} ?食記|頁面|平台|懶人包|dinbendon|頁示|店卡|交叉|彙整|公開彙整|\d{4}|\d{4} ?文|官網|刊登|目錄|名冊|EPB|補給站|萬家|LINE|訂便當網|店文)$/;
  function cleanHoursTags(t) {
    return t.replace(/（([^（）]*)）/g, function (all, inner) {
      var parts = inner.split(/[—；;]/).map(function (s) { return s.trim(); }).filter(function (s) { return s && !SRC_TAGS.test(s); });
      return parts.length ? '（' + parts.join('；') + '）' : '';
    });
  }
  function cleanSourceJargon(text) {
    var t = String(text == null ? '' : text);
    if (!t) return t;
    // chain templates
    t = t.replace(/肯德基官網找餐廳（[^）]*）列出本餐廳地址與營業時間；以本餐廳自己的地址查官網外送系統（[^）]*）回傳的就是本餐廳，確認本店接官網外送單。?/g, '肯德基官網門市查詢列出本餐廳地址與營業時間；用本餐廳地址查官網外送系統，回傳的就是本餐廳，所以本店有接官網外送單。');
    t = t.replace(/必勝客官方門市資料（[^）]*）/g, '必勝客官網門市資料');
    t = t.replace(/達美樂官網尋找門市（[^）]*）/g, '達美樂官網門市資料');
    t = t.replace(/德克士官網門市資訊（[^）]*）/g, '德克士官網門市資訊');
    t = t.replace(/Oddle Eats TW discover\/explore 目錄與單店頁 \S+ 之 addresses 明列(\S{2,4}?)地址且 enableDelivery\/eligibleForDelivery；官方店舖連結 [^\s。；]+。?/g, '店家官方 Oddle 訂餐頁列出$1地址，並顯示有開放外送。');
    t = t.replace(/官方 EATOGO API \S+?[：:]?\s*該分店 allowDelivery=1(（launch_delivery=1）)?；?/g, '品牌官方 EATOGO 訂餐系統顯示本分店有開外送；');
    t = t.replace(/deliveryDist 明列/g, '系統列出').replace(/API deliveryDist 上限/g, '官方訂餐系統上限');
    t = t.replace(/min_purchase\s*/g, '最低消費 ').replace(/delivery_free\s*/g, '免運 ');
    t = t.replace(/Oddle storefront dump/g, '店家官方 Oddle 訂餐頁資料').replace(/`/g, '');
    t = t.replace(/eligibleForDelivery:?\s*true/g, '有開放外送').replace(/deliveryZones/g, '外送區');
    t = t.replace(/（圓心約[^）]*）/g, '').replace(/（r=\d+m）/g, '');
    t = t.replace(/(\d+KM)\s*min\s*=\s*/g, '$1 最低消費 ').replace(/(\d+KM)(?=最低)/g, '$1 ');
    t = t.replace(/minimumOrderCost\s*=\s*/g, '最低消費 ').replace(/deliveryFreeAfter\s*=\s*/g, '滿額免運 ').replace(/freeAfter\s*=\s*/g, '免運 ').replace(/\bmin\s*=\s*/g, '最低消費 ').replace(/\bfee\s*=\s*/g, '運費 ').replace(/\bcost\s*=\s*/g, '運費 ');
    // platform labels
    t = t.replace(/訂便當（dinbendon）店家頁公開外送條件/g, '訂便當網店家頁寫明的外送條件');
    t = t.replace(/(?:dinbendon|訂便當)\s*(?:API detail shopId=\d+|公用店家頁／API|公用店家頁／搜尋摘要|公用店家明示|公用店家頁|公用店家|SSR meta|meta／店卡|meta|notice／publicNotice|notice／description|publicNotice|notice|description|簡介／訂購說明明示|簡介明示|簡介|訂購說明明示|訂購說明|店卡明示|電話欄明示|店家頁|API)?(?:明示)?\s*[:：]\s*/g, '訂便當網店家頁寫明：');
    t = t.replace(/dinbendon/gi, '訂便當網');
    t = t.replace(/訂便當網\s*(?:shop=\d+\s*)?(?:(?:detail|description|notice|publicNotice|pub|meta|說明|簡介|公用頁|sentAreas 可讀|店家資訊|bootstrap 文案|SSR|API|公開)[／/、\s]*)+(?:明示|寫明)?\s*[:：「]/g, function (m) { return '訂便當網店家頁寫明' + (/「$/.test(m) ? '「' : '：'); });
    t = t.replace(/[（(][^（）()]*(?:shop=|Batch|near-miss|解鎖|交叉|Gaps|異店|不另收|discovery|bootstrap|sentAreas)[^（）()]*[）)]/g, '');
    t = t.replace(/[；;][^；;]*(?:shop=|Batch|near-miss|解鎖|交叉|Gaps|異店|不另收)[^；;]*/g, '');
    t = t.replace(/(?:publicNotice|notice|description|detail|meta)(?:[／/](?:publicNotice|notice|description|detail|meta|pub|公用頁))*\s*[:：]/g, '店家頁另寫：').replace(/(?:公開\s*)?(?:publicNotice|notice|description)\b/g, '店家頁說明');
    t = t.replace(/permio\d\s*[:：]?\s*/g, '網路外送店家名單：');
    t = t.replace(/(?:\d{4}\s*)?(?:[A-Za-z]+\s*)?(?:\d{4}\s*)?(?:\S{0,4}防疫)?懶人包(?:店卡|親送門檻)?(?:明示)?/g, '網路整理的外送店家名單');
    t = t.replace(/EPD\s*(?=不鏽鋼)/g, '環保局').replace(/EPD 名單|環保局名冊明示|環保局名冊|環保局名單|\bEPB\b/g, '環保局公布的店家名單');
    t = t.replace(/(?:\d{4}\s*)?食記(?:店卡)?明示/g, '網路食記寫明').replace(/店卡明示/g, '店家資訊寫明').replace(/補給站明示/g, '網路外送補給站名單寫明').replace(/萬家微網站明示/g, '店家微網站寫明').replace(/amonblog 明示/g, '網路文章寫明').replace(/Mys 表明示/g, '網路整理名單寫明');
    t = t.replace(/bendon-dao/g, '便當訂購平台店家頁').replace(/268web(?: Part=\d+)?/g, '便當訂購網');
    t = t.replace(/Ocard Notices/g, 'Ocard 線上點餐頁公告').replace(/iCHEF Reminder／Chrome dump/g, 'iCHEF 線上點餐頁提醒').replace(/\bReminder\b/g, '提醒').replace(/／?Chrome dump/g, '');
    t = t.replace(/Official Oddle\s*/g, '店家官方 Oddle 訂餐頁').replace(/渠道[:：]\s*/g, '訂餐管道：');
    t = t.replace(/Oddle (?:el=true|eligibleForDelivery)/g, '店家官方 Oddle 訂餐頁顯示有開外送');
    t = t.replace(/enableDelivery\/eligibleForDelivery|enableDelivery|eligibleForDelivery|allowDelivery=1|launch_delivery=1/g, '有開外送');
    // internal references / bookkeeping
    t = t.replace(/（異於[^）]*）/g, '').replace(/（shop=\d+[^）]*）/g, '').replace(/[；;]?\s*Checked:\s*\d{4}-\d{2}-\d{2}/g, '').replace(/[；;]?\s*Batch:\s*[\w-]+/g, '');
    t = t.replace(/foodintainan(?:／[a-z]+)?\s*[\u4e00-\u9fff]{0,2}網路整理的外送店家名單/g, '網路整理的外送店家名單').replace(/(?:foodintainan|findglocal|footinder|candylife|vivawei|hululu)(?:／[a-z]+)?\s*/g, '網路店家資訊');
    t = t.replace(/SSR meta|\bmeta\b/g, '店家頁').replace(/店卡/g, '店家資訊').replace(/／?殼文/g, '').replace(/搜尋索引|搜尋摘要/g, '搜尋結果摘要').replace(/\s*Notices\b/g, '公告');
    t = t.replace(/\bUE\/FP\b|\bFP\/UE\b/g, 'Uber Eats／foodpanda').replace(/[；;]?\s*→?\s*order_url[^；;]*/g, '').replace(/=true\b/g, '');
    t = t.replace(/\s*shop=\d+/g, '').replace(/（launch_delivery=\d）；?/g, '').replace(/(?:有開放外送 \+ )?有開外送:true/gi, '官方訂餐頁顯示有開放外送').replace(/minimumOrderAmount\s*=\s*/g, '最低消費 ').replace(/deliveryFee\s*/g, '運費 ').replace(/Mys 表／文明示/g, '網路整理名單與文章寫明');
    t = t.replace(/（[^（）]*_dist=\d+[^（）]*）/g, '').replace(/[；;]同 store block[^；;]*/g, '').replace(/舊 amonblog/g, '舊網路文章').replace(/Minimum order\s*/g, '最低訂購 ');
    t = t.replace(/\bEPD\b\s*示?/g, '環保局名單');
    t = t.replace(/\blocator API\b/g, '門市查詢系統').replace(/\bAPI\b/g, '系統');
    t = t.replace(/https?:\/\/[^\s，。；、）」（]+/g, '').replace(/（\s*）|\(\s*\)/g, '').replace(/\s+([，。；、）])/g, '$1').replace(/：\s*。/g, '。');
    return t;
  }

  function readerProse(text) {
    if (text == null) return '';
    var t = cleanSourceJargon(String(text)).replace(/\*\*/g, '');
    t = t.replace(/\bUNKNOWN\b/gi, '未公開');
    t = t.replace(/\bbrand URL\b/gi, '品牌網址');
    t = t.replace(/deliveryCreatable:\s*true、?/gi, '');
    t = t.replace(/QA pass:\s*food-order\s*\+\s*Delivery/gi, '確認為外送訂餐頁');
    t = t.replace(/\s*→\s*medium\b/g, '');
    t = t.replace(/[ \t]{2,}/g, ' ').replace(/；{2,}/g, '；').replace(/^[；;\s]+|[；;\s]+$/g, '');
    if (blankish(t) || t === '未公開') return '';
    return t;
  }

  /** Internal terms template → Traditional Chinese. UNKNOWN segments are omitted.
      免運門檻 stays in this summary string and is never returned as a badge. */
  function readerTerms(text) {
    var raw = String(text == null ? '' : text).trim();
    if (!raw) return '';
    var labelRe = /(?:^|[；;])\s*(Delivery fee \(min listed\)|Delivery fee max listed|Free-delivery threshold|Minimum \/ shipping|Minimum order|Delivery fee|LINE ID|LINE|Range)\s*:\s*/g;
    var matches = [];
    var m;
    while ((m = labelRe.exec(raw))) matches.push({ label: m[1], start: m.index, end: labelRe.lastIndex });
    if (!matches.length) return readerProse(raw);
    var zh = {};
    TERM_LABELS.forEach(function (row) { zh[row[0]] = { name: row[1], secondary: row[2] }; });
    var primary = [], secondary = [], tail = [];
    matches.forEach(function (hit, i) {
      var end = i + 1 < matches.length ? matches[i + 1].start : raw.length;
      var value = raw.slice(hit.end, end).replace(/[；;]\s*$/, '').trim();
      var meta = zh[hit.label];
      if (!meta) return;
      var shown = '';
      if (hit.label === 'Free-delivery threshold') shown = formatThreshold(value);
      else if (hit.label === 'Delivery fee') shown = formatAmount(value) || (blankish(value) ? '' : readerProse(value));
      else shown = blankish(value) ? '' : readerProse(value);
      if (!shown) return;
      var piece = meta.name + '：' + shown;
      if (hit.label === 'LINE' || hit.label === 'LINE ID') tail.push(piece);
      else if (meta.secondary) secondary.push(piece);
      else primary.push(piece);
    });
    return primary.concat(secondary, tail).join('；');
  }

  function readerHours(text) {
    var t = String(text == null ? '' : text).trim().replace(/^hours\s+/i, '');
    if (blankish(t)) return '';
    t = englishHours(cleanHoursTags(t));
    t = readerProse(t);
    if (!t || t === '未公開') {
      if (/unknown/i.test(String(text)) && text.indexOf('（') === -1 && text.indexOf('(') === -1) return '';
    }
    if (t === '未公開') return '';
    return t;
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
      if (r.city !== city || !r.district) return;
      set[r.district] = 1;
    });
    return Object.keys(set).sort(function (a, b) {
      return a.localeCompare(b, 'zh-Hant');
    });
  }

  /**
   * Curated cuisine filters (~20). Dropdown shows these labels only.
   * Matching is keyword substring against cuisine + cuisineTags (casefold),
   * not exact raw-tag equality. A venue may match multiple filters.
   */
  var CUISINE_FILTERS = [
    { label: '便當／快餐', keywords: ['便當', '快餐', '飯包', '盒餐', '會議便當', '會議餐盒', '池上', '自助餐', '簡餐', '排骨飯', '烤肉飯', '雞腿', '排骨', '鐵路便當', '鐵道便當'], neutralize: ['排骨麵', '排骨酥麵', '排骨酥'] },
    { label: '健康餐盒', keywords: ['健康餐盒', '健康低卡', '健康便當', '低卡', '舒肥', '循環盒', '健身餐', '輕盈'] },
    { label: '燒臘', keywords: ['燒臘', '燒鴨', '烤鴨', '叉燒', '油雞'] },
    { label: '麵食', keywords: ['麵食', '涼麵', '牛肉麵', '刀削', '麵線', '義大利麵', '拉麵', '陽春麵', '担担', '擔擔', '鍋燒', '炒麵', '湯麵', '水餃', '鍋貼', '餛飩', '義麵'] },
    { label: '蓋飯／丼', keywords: ['蓋飯', '丼飯', '丼', '滷肉飯', '雞肉飯', '咖哩飯', '燒肉飯'] },
    { label: '火鍋', keywords: ['火鍋', '麻辣鍋', '涮鍋', '鍋物', '部隊鍋', '麻辣', '石頭火鍋', '小火鍋'] },
    { label: '小吃', keywords: ['小吃', '滷味', '鹹水雞', '蔥油餅', '肉羹', '滷肉', '臭豆腐', '刈包', '鹽酥雞', '鹹酥雞', '路邊'] },
    { label: '早午餐', keywords: ['早午餐', '輕食', '三明治', 'Brunch', 'brunch', '吐司', '蛋餅'] },
    { label: '咖啡／甜點', keywords: ['咖啡', '甜點', '蛋糕', '可麗露', '烘焙', '甜品', '布丁', '糕點', '私房甜點', '蛋糕甜點', '豆花', '巧克力', '糕餅', '麵包', '伴手禮'] },
    { label: '手搖飲', keywords: ['手搖', '茶飲', '手搖飲', '手搖飲料', '手搖茶飲', '飲料店', '珍奶', '珍珠奶茶'] },
    { label: '日式', keywords: ['日式', '日本和食', '和食', '壽司', '拉麵', '鰻魚', '定食', '丼', '刺身', '居酒屋', '日式便當', '丼飯', '握壽司'] },
    { label: '韓式', keywords: ['韓式', '韓國', '韓定食', '部隊鍋', '石鍋拌飯', '韓式炸雞'] },
    { label: '泰式／東南亞', keywords: ['泰式', '南洋', '海南雞', '越南', '印尼', '马来', '馬來', '咖哩', '叻沙', '新加坡'] },
    { label: '義式／西式', keywords: ['義式', '披薩', 'pizza', 'Pizza', '義大利', '義法', '西式', '歐式', '美式', '漢堡', '牛排', 'Pasta', 'pasta', '西餐廳'] },
    { label: '中式／台菜', keywords: ['中式', '台菜', '台式', '中港', '川菜', '粵菜', '湘菜', '合菜', '熱炒', '客家', '江浙', '上海', '家常', '港式', '粵式', '魯肉'] },
    { label: '蔬食／素食', keywords: ['蔬食', '素食', '素食蔬食', '蔬食友善', '純素', '奶蛋素', '植物肉'] },
    // 雞排 as fried-primary; neutralize 雞排麵/雞排飯 so noodle shops are not false positives
    { label: '炸物', keywords: ['炸物', '炸雞', '雞排', '鹽酥雞', '鹹酥雞', '唐揚', '炸豬排', '卡啦'], neutralize: ['雞排麵', '雞排飯'] },
    { label: '其他', keywords: [] } // special: venues matching no other filter
  ];

  function cuisineBlob(r) {
    return ((r.cuisine || '') + ' ' + (r.cuisineTags || []).join(' ')).toLowerCase();
  }

  function filterByKeywords(blob, keywords, neutralize) {
    var b = blob;
    if (neutralize && neutralize.length) {
      for (var n = 0; n < neutralize.length; n++) {
        var compound = String(neutralize[n]).toLowerCase();
        if (!compound) continue;
        // Remove compound tokens so keyword substrings inside them do not match
        while (b.indexOf(compound) !== -1) {
          b = b.replace(compound, '\u0000');
        }
      }
    }
    for (var i = 0; i < keywords.length; i++) {
      if (b.indexOf(String(keywords[i]).toLowerCase()) !== -1) return true;
    }
    return false;
  }

  function matchesCuisineFilter(r, cuisineLabel) {
    if (!cuisineLabel) return true;
    var blob = cuisineBlob(r);
    var filter = null;
    for (var i = 0; i < CUISINE_FILTERS.length; i++) {
      if (CUISINE_FILTERS[i].label === cuisineLabel) {
        filter = CUISINE_FILTERS[i];
        break;
      }
    }
    if (!filter) {
      // Legacy URL / unknown label: fall back to substring on label itself
      return blob.indexOf(cuisineLabel.toLowerCase()) !== -1;
    }
    if (filter.label === '其他') {
      for (var j = 0; j < CUISINE_FILTERS.length; j++) {
        var f = CUISINE_FILTERS[j];
        if (f.label === '其他') continue;
        if (filterByKeywords(blob, f.keywords, f.neutralize)) return false;
      }
      return true;
    }
    return filterByKeywords(blob, filter.keywords, filter.neutralize);
  }

  function cuisineOptions(_list) {
    return CUISINE_FILTERS.map(function (f) { return f.label; });
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

  var MEDIA_CUISINES = [
    { key: 'bento', label: '便當', icon: '▦', keywords: ['便當', '快餐', '飯包', '盒餐', '餐盒', '自助餐', '簡餐', '排骨飯', '烤肉飯', '雞腿飯', '雞肉飯', '滷肉飯'] },
    { key: 'noodles', label: '麵食', icon: '〰', keywords: ['麵', '麵食', '拉麵', '麵線', '水餃', '鍋貼', '餛飩'] },
    { key: 'drinks', label: '飲料', icon: '◌', keywords: ['飲料', '茶飲', '手搖', '咖啡', '珍奶', '珍珠奶茶', '果汁', '冰品'] },
    { key: 'hotpot', label: '火鍋', icon: '♨', keywords: ['火鍋', '麻辣鍋', '涮鍋', '鍋物', '部隊鍋', '小火鍋'] },
    { key: 'other', label: '其他', icon: '✦', keywords: [] }
  ];

  function mediaCuisine(r) {
    var blob = cuisineBlob(r);
    for (var i = 0; i < MEDIA_CUISINES.length - 1; i++) {
      if (filterByKeywords(blob, MEDIA_CUISINES[i].keywords)) return MEDIA_CUISINES[i];
    }
    return MEDIA_CUISINES[MEDIA_CUISINES.length - 1];
  }

  function mediaPlaceholderInner(r) {
    var media = mediaCuisine(r);
    return '<div class="card-media-placeholder card-media-placeholder--' + media.key + '" role="img" aria-label="' + escapeHtml(media.label) + '・尚無店家照片"' +
      '><span class="card-media-icon" aria-hidden="true">' + media.icon + '</span>' +
      '<span class="card-media-label">' + escapeHtml(media.label) + '</span>' +
      '<span class="card-media-hint">尚無店家照片</span></div>';
  }

  function cardMediaHtml(r) {
    var url = String(r.imageUrl || '').trim();
    var placeholder = mediaPlaceholderInner(r);
    if (!/^https?:\/\//i.test(url)) {
      return '<div class="card-media">' + placeholder + '</div>';
    }
    return '<div class="card-media">' +
      '<img src="' + escapeHtml(url) + '" loading="lazy" decoding="async" alt="" onerror="this.onerror=null;this.hidden=true;this.nextElementSibling.hidden=false;" />' +
      '<div class="card-media-fallback" hidden>' + placeholder + '</div>' +
      '</div>';
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
    actions.push('<a class="btn btn-ghost" href="shop/' + encodeURIComponent(r.id) + '.html">詳情</a>');
    actions.push('<button type="button" class="btn btn-ghost" data-report-shop="' + escapeHtml(r.name) + '">通報問題</button>');

    return (
      '<article class="card" data-id="' + escapeHtml(r.id) + '">' +
        cardMediaHtml(r) +
        '<div class="card-body">' +
          '<div class="badges">' + badges.join('') + '</div>' +
          '<h2><a href="shop/' + encodeURIComponent(r.id) + '.html">' + escapeHtml(r.name) + '</a></h2>' +
          channelChips(r) +
          (r.cuisine ? '<p class="cuisine-line">' + escapeHtml(r.cuisine) + '</p>' : '') +
          (function () { var addr = readerProse(r.address); return addr ? ('<p class="addr">' + escapeHtml(addr) + '</p>') : ''; })() +
          (function () { var hs = readerHours(r.hours); return hs ? ('<p class="hours">時段：' + escapeHtml(hs) + '</p>') : ''; })() +
          (function () { var dc = deliveryChips(r).join(''); return dc ? ('<div class="delivery-conditions" aria-label="外送條件">' + dc + '</div>') : ''; })() +
          '<div class="actions">' + actions.join('') + '</div>' +
        '</div>' +
      '</article>'
    );
  }


  /** Longest-first food terms for splitting CJK queries without spaces. */
  var SEARCH_TERMS = [
    '健康餐盒','手搖飲料','手搖茶飲','早午餐','牛肉麵','滷肉飯','雞肉飯','火雞肉飯',
    '牛排','便當','盒餐','餐盒','燒臘','燒鴨','火鍋','拉麵','壽司','丼飯','蓋飯',
    '小吃','麵食','涼麵','水餃','鍋貼','炸雞','雞排','鹽酥雞','咖哩','定食','居酒屋',
    '韓式','日式','泰式','義式','西餐','咖啡','甜點','蛋糕','飲料','茶飲','手搖',
    '素食','蔬食','自助餐','熱炒','合菜','鐵板','排骨','雞腿','豬排','魚排'
  ];

  function tokenizeQuery(q) {
    q = String(q || '').toLowerCase().trim();
    if (!q) return [];
    if (/\s/.test(q)) return q.split(/\s+/).filter(Boolean);
    var found = [];
    var rest = q;
    var terms = SEARCH_TERMS.slice().sort(function (a, b) { return b.length - a.length; });
    for (var i = 0; i < terms.length; i++) {
      var t = terms[i].toLowerCase();
      if (t.length >= 2 && rest.indexOf(t) !== -1) {
        found.push(t);
        rest = rest.split(t).join('\u0001');
      }
    }
    if (!found.length) return [q];
    var seen = {};
    var out = [];
    for (var j = 0; j < found.length; j++) {
      if (!seen[found[j]]) { seen[found[j]] = 1; out.push(found[j]); }
    }
    return out;
  }

  function haystackOf(r) {
    return [
      r.name, r.city, r.district, r.address, r.cuisine,
      (r.cuisineTags || []).join(' '), r.phone, r.evidence
    ].join(' ').toLowerCase();
  }

  function tokensMatchAnd(hay, tokens) {
    for (var i = 0; i < tokens.length; i++) {
      if (hay.indexOf(tokens[i]) === -1) return false;
    }
    return true;
  }

  function tokensMatchOr(hay, tokens) {
    for (var i = 0; i < tokens.length; i++) {
      if (hay.indexOf(tokens[i]) !== -1) return true;
    }
    return false;
  }

  function matches(r, q, city, district, cuisine, softOr) {
    if (city && r.city !== city) return false;
    if (district) {
      if (r.district !== district) return false;
    }
    if (cuisine && !matchesCuisineFilter(r, cuisine)) return false;
    if (q) {
      var hay = haystackOf(r);
      var raw = String(q).toLowerCase().trim();
      // Prefer exact phrase when present
      if (hay.indexOf(raw) !== -1) return true;
      var tokens = tokenizeQuery(q);
      if (!tokens.length) return true;
      if (softOr && tokens.length > 1) return tokensMatchOr(hay, tokens);
      return tokensMatchAnd(hay, tokens);
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
    // Old multi-area bookmark: show the Taipei (or selected city) listing, not a fake district.
    if (district === '台北多區') district = '';
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

      var searchRelaxed = false;
      var filtered = data.filter(function (r) {
        return matches(r, q, cityVal, districtVal, cuisine, false);
      });
      if (q && filtered.length === 0) {
        var _tok = tokenizeQuery(q);
        if (_tok.length > 1) {
          searchRelaxed = true;
          filtered = data.filter(function (r) {
            return matches(r, q, cityVal, districtVal, cuisine, true);
          });
        }
      }
      filtered.sort(function (a, b) {
        var pa = /^https?:\/\//i.test(String(a.imageUrl || '').trim()) ? 0 : 1;
        var pb = /^https?:\/\//i.test(String(b.imageUrl || '').trim()) ? 0 : 1;
        if (pa !== pb) return pa - pb;
        return (a.name || '').localeCompare(b.name || '', 'zh-Hant');
      });

      countEl.innerHTML = '顯示 <strong>' + filtered.length + '</strong> / ' + data.length + ' 家' +
        (cityVal ? ('（目前：' + escapeHtml(cityVal) + (districtVal ? (' · ' + escapeHtml(districtVal)) : '') + '）') : '');
      var hint = document.getElementById('search-relaxed-hint');
      if (!hint && countEl && countEl.parentNode) {
        hint = document.createElement('p');
        hint.id = 'search-relaxed-hint';
        hint.className = 'muted search-relaxed-hint';
        countEl.parentNode.insertBefore(hint, countEl.nextSibling);
      }
      if (hint) {
        hint.textContent = searchRelaxed
          ? '找不到同時符合的店，已改為較寬鬆搜尋（符合其中一個詞即可）。'
          : '';
        hint.hidden = !searchRelaxed;
      }
      var heroStats = $('#hero-stats');
      if (heroStats) {
        heroStats.innerHTML = '目前收錄 <strong>' + data.length + '</strong> 家店家自送通道';
      }
      trackSearch(q, filtered.length);
      if (!filtered.length) {
        listEl.innerHTML = '<div class="empty">找不到符合條件的店家，請調整關鍵字或篩選。</div>';
        return;
      }
      listEl.innerHTML = filtered.map(cardHtml).join('');
    }

    var lastTrackedQ = '';
    var trackTimer;
    function trackSearch(q, n) {
      clearTimeout(trackTimer);
      if (!q || q === lastTrackedQ) return;
      trackTimer = setTimeout(function () {
        lastTrackedQ = q;
        if (window.zisongTrack) window.zisongTrack(n ? 'search' : 'search-empty', q.toLowerCase().slice(0, 60));
      }, 1500);
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
    var r = data.find(function (x) { return x.id === id || x.slug === id; });
    // Menus live in menus.js (loaded by detail.html only) so data.js stays small for listings.
    var menus = window.ZISONG_MENUS;
    if (r && !r.menu && menus && menus[r.id]) r.menu = menus[r.id];
    return r;
  }

  /** Shops removed on 2026-10-22 (no verifiable source, or closed) -> their district listing. */
  var HIDDEN_SHOPS = {
    'daan-new-029': 'district/daan.html',
    'scout-b11-232': 'district/daan.html',
    'scout-b12-246': 'district/daan.html',
    'scout-b12-247': 'district/daan.html',
    'scout-b12-249': 'district/xinyi.html',
    'scout-b12-256': 'district/zhongshan.html',
    'scout-lead-346': 'district/zhongshan.html',
    'scout-lead-347': 'district/zhongshan.html',
    'scout-lead-349': 'district/zhongshan.html',
    'scout-lead-351': 'district/zhongshan.html',
    'scout-lead-360': 'district/zhongzheng.html',
    'scout-lead-363': 'district/zhongshan.html',
    'scout-lead-364': 'district/zhongshan.html',
    'scout-lead-367': 'district/zhongshan.html',
    'scout-lead-372': 'district/songshan.html',
    'scout-lead-373': 'district/songshan.html',
    'scout-lead-378': 'district/songshan.html',
    'scout-lead-379': 'district/songshan.html',
    'scout-lead-380': 'district/daan.html',
    'scout-lead-381': 'district/daan.html',
    'scout-lead-382': 'district/daan.html',
    'scout-lead-384': 'district/daan.html',
    'scout-lead-385': 'district/daan.html',
    'scout-lead-386': 'district/xinyi.html',
    'scout-lead-388': 'district/xinyi.html',
    'scout-lead-389': 'district/xinyi.html',
    'scout-lead-390': 'district/xinyi.html',
    'scout-lead-391': 'district/xinyi.html',
    'scout-lead-392': 'district/zhongzheng.html',
    'scout-lead-396': 'district/neihu.html',
    'scout-lead-401': 'district/xinyi.html',
    'scout-lead-404': 'district/xinyi.html',
    'scout-lead-407': 'district/xinyi.html',
    'scout-lead-409': 'district/xinyi.html',
    'scout-lead-414': 'district/daan.html',
    'scout-lead-415': 'district/daan.html',
    'scout-lead-416': 'district/daan.html',
    'scout-lead-417': 'district/xinyi.html',
    'scout-lead-421': 'district/xinyi.html',
    'scout-lead-422': 'district/xinyi.html',
    'scout-lead-427': 'district/wanhua.html',
    'scout-lead-428': 'district/wanhua.html',
    'scout-lead-430': 'district/neihu.html',
    'scout-lead-432': 'district/nangang.html',
    'scout-lead-435': 'district/beitou.html',
    'scout-lead-437': 'district/daan.html',
    'scout-lead-454': 'district/datong.html',
    'scout-lead-455': 'district/wenshan.html',
    'scout-lead-456': 'district/shilin.html',
    'scout-lead-462': 'district/zhongzheng.html',
    'scout-lead-466': 'district/zhongshan.html',
    'scout-lead-469': 'district/shilin.html',
    'scout-lead-470': 'district/daan.html',
    'scout-lead-478': 'district/zhongshan.html',
    'scout-lead-479': 'district/zhongshan.html',
    'scout-lead-480': 'district/zhongshan.html',
    'scout-lead-481': 'district/zhongzheng.html',
    'scout-lead-482': 'district/daan.html',
    'scout-lead-484': 'district/xinyi.html',
    'scout-lead-490': 'district/daan.html',
    'scout-lead-491': 'district/zhongshan.html',
    'scout-lead-494': 'district/zhongshan.html',
    'scout-lead-501': 'district/zhongshan.html',
    'scout-lead-502': 'district/zhongshan.html',
    'scout-lead-503': 'district/zhongshan.html'
  };

  /** Old single-record chain pages, now split into one record per branch. */
  var SPLIT_CHAINS = {
    'scout-b1-16': '瑞記海南雞飯', 'scout-b1-17': '必勝客', 'scout-b1-18': '達美樂',
    'scout-b1-19': '肯德基', 'scout-b1-20': '德克士',
    'scout-b4-101': '非常泰', 'scout-b4-102': '1010湘', 'scout-b4-103': '時時香',
    'nt-scout-lead-10': '關山珍享便當'
  };

  function menuSourceName(url) {
    var u = String(url || '');
    if (/dinbendon/i.test(u)) return '訂便當';
    if (/oddle\.me/i.test(u)) return 'Oddle';
    if (/ichefpos\.com/i.test(u)) return 'iCHEF 線上點餐';
    if (/eatogo\.com\.tw/i.test(u)) return 'EATOGO';
    if (/ocard\.co/i.test(u)) return 'Ocard';
    if (/inline\.app/i.test(u)) return 'inline';
    if (/nidin\.shop/i.test(u)) return '你訂';
    return '店家官方頁面';
  }

  function linkifyText(text) {
    var re = /https?:\/\/[^\s；，,]+/g;
    var out = '';
    var last = 0;
    var m;
    while ((m = re.exec(text))) {
      out += escapeHtml(text.slice(last, m.index));
      var url = m[0];
      out += '<a href="' + escapeHtml(url) + '" target="_blank" rel="noopener noreferrer">' + escapeHtml(/line\.me|lin\.ee/i.test(url) ? lineLinkText(url) : linkLabel(url)) + '</a>';
      last = m.index + url.length;
    }
    out += escapeHtml(text.slice(last));
    return out;
  }

  /** LINE wording from the sourced note, else the existing account link. */
  function lineLinkText(u) {
    var m = /(@[A-Za-z0-9._\-]+)/.exec(decodeURIComponent(String(u || '').replace(/%(?![0-9A-Fa-f]{2})/g, '%25')));
    return m ? '加 LINE 好友（' + m[1] + '）' : '加 LINE 好友';
  }

  function detailLineHtml(r) {
    var note = r.line != null ? String(r.line).trim() : '';
    if (note) return linkifyText(note);
    if (r.lineUrl) {
      return '<a href="' + escapeHtml(r.lineUrl) + '" target="_blank" rel="noopener noreferrer">' + escapeHtml(lineLinkText(r.lineUrl)) + '</a>';
    }
    if (r.lineId) return escapeHtml(r.lineId);
    return null;
  }

  function phoneParts(phone) {
    return String(phone || '').split(/、|，/).map(function (s) { return s.trim(); }).filter(Boolean);
  }

  function phoneTel(part) {
    return String(part).replace(/\s*(?:分機|轉|#|ext\.?).*$/i, '').replace(/[^\d+]/g, '');
  }

  function phoneLinksHtml(phone) {
    return phoneParts(phone).map(function (p) {
      var tel = phoneTel(p);
      if (!tel) return escapeHtml(p);
      return '<a href="tel:' + escapeHtml(tel) + '">' + escapeHtml(p) + '</a>';
    }).join('、');
  }

  function officialLabel(u, button) {
    if (/facebook\.com|instagram\.com/i.test(u)) return '店家粉專';
    if (/dinbendon|oddle\.me|eatogo|ichefpos|ocard\.co|nidin\.shop|inline\.app|bendon-dao|quickclick|iding\.tw|imenu\.com|dudooeat/i.test(u)) return button ? '店家菜單・訂餐頁' : '店家菜單頁';
    return button ? '官網・菜單' : '店家官網';
  }

  /** Readable link text: label + host, instead of the raw URL. */
  function linkLabel(u) {
    var host = '';
    var m = /^https?:\/\/([^\/?#:]+)/i.exec(String(u || ''));
    if (m) host = m[1].replace(/^www\./i, '');
    var label = officialLabel(u, false);
    return host ? label + '（' + host + '）' : label;
  }

  function menuPriceText(price) {
    var p = String(price).trim();
    if (/^\d/.test(p)) return '$' + p;
    return p;
  }

  /** Priced menu only. No block when the shop has no priced items. */
  function detailMenuHtml(r) {
    var menu = r.menu;
    if (!menu || !menu.items || !menu.items.length) return '';
    var rows = [];
    var lastCat = null;
    var shown = 0;
    for (var i = 0; i < menu.items.length; i++) {
      var it = menu.items[i] || {};
      var name = it.name != null ? String(it.name).trim() : '';
      var price = it.price != null ? String(it.price).trim() : '';
      if (!name || !/\d/.test(price)) continue;
      var cat = it.category != null ? String(it.category).trim() : '';
      if (cat && cat !== lastCat) {
        rows.push('<li class="menu-cat">' + escapeHtml(cat) + '</li>');
        lastCat = cat;
      }
      shown++;
      var desc = it.description != null ? String(it.description).trim() : '';
      if (desc) {
        rows.push('<li class="has-desc"><div class="menu-row"><span class="menu-name">' + escapeHtml(name) + '</span><span class="menu-price">' + escapeHtml(menuPriceText(price)) + '</span></div><p class="menu-desc">' + escapeHtml(desc) + '</p></li>');
      } else {
        rows.push('<li><span class="menu-name">' + escapeHtml(name) + '</span><span class="menu-price">' + escapeHtml(menuPriceText(price)) + '</span></li>');
      }
    }
    if (!rows.length) return '';
    var srcUrl = String(r.menuSource || menu.source || '').trim();
    var srcName = menuSourceName(srcUrl);
    var when = String(r.menuCheckedAt || menu.fetchedOn || '').trim();
    var srcBit = '';
    if (srcUrl && /^https?:\/\//i.test(srcUrl)) {
      srcBit = '<a href="' + escapeHtml(srcUrl) + '" target="_blank" rel="noopener noreferrer">' + escapeHtml(srcName || srcUrl) + '</a>';
    }
    var lead = '';
    if (menu.total && menu.total > shown) {
      lead = '列出 ' + shown + ' 項，完整 ' + menu.total + ' 項見' + (srcBit || '店家頁面') + '。';
    } else if (srcBit) {
      lead = '菜單來源：' + srcBit + '。';
    }
    var upd = menu.sourceUpdated ? String(menu.sourceUpdated).trim() : '';
    var sourceLine = '<p class="menu-source">' + lead + (upd ? '店家最後更新 ' + escapeHtml(upd) + '，' : '') + (when ? '本站核對 ' + escapeHtml(when) + '。' : '') + '價格與供應以店家為準。</p>';
    return '<section class="detail-menu" aria-label="菜單"><h2>菜單</h2><ul>' + rows.join('') + '</ul>' + sourceLine + '</section>';
  }

  /** Shops without a priced menu: show what they sell and how to ask. */
  function detailNoMenuHtml(r) {
    if (r.menu && r.menu.items && r.menu.items.length) return '';
    var tags = (r.cuisineTags || []).filter(function (t) { return t && !/未公開/.test(t); });
    if (!tags.length && r.cuisine && !/未公開/.test(r.cuisine)) {
      tags = String(r.cuisine).split(/[、／\/，,]/).map(function (t) { return t.trim(); }).filter(Boolean);
    }
    var chips = tags.length
      ? '<div class="menu-tags">' + tags.map(function (t) { return '<span class="menu-tag">' + escapeHtml(t) + '</span>'; }).join('') + '</div>'
      : '';
    var first = phoneParts(r.phone)[0];
    var ask;
    if (first && phoneTel(first)) {
      ask = '菜單請洽店家：<a href="tel:' + escapeHtml(phoneTel(first)) + '">' + escapeHtml(first) + '</a>';
      if (r.officialUrl) ask += '，或看<a href="' + escapeHtml(r.officialUrl) + '" target="_blank" rel="noopener noreferrer">' + officialLabel(r.officialUrl) + '</a>';
    } else if (r.officialUrl) {
      ask = '菜單請看<a href="' + escapeHtml(r.officialUrl) + '" target="_blank" rel="noopener noreferrer">' + officialLabel(r.officialUrl) + '</a>';
    } else if (r.orderUrl || r.lineUrl) {
      ask = '菜單請看上方的店家官方訂餐頁';
    } else {
      ask = '菜單請洽店家';
    }
    return '<section class="detail-menu detail-nomenu" aria-label="供應餐點"><h2>供應餐點</h2>' + chips + '<p class="menu-ask">' + ask + '。</p></section>';
  }

  /** One clear delivery line near the top, from the shop's own stated terms only. */
  function detailDeliveryHtml(r) {
    var text = r.deliverySummary ? String(r.deliverySummary).trim() : '';
    if (!text) text = '店家自己外送，條件請電話問店家';
    return '<p class="detail-delivery"><strong>外送條件：</strong>' + escapeHtml(text) + '</p>';
  }

  function initDetail() {
    var root = $('#detail');
    if (!root) return;
    var id = getParam('id') || getParam('slug');
    var r = id ? findByIdOrSlug(id) : null;
    if (!r && id && SPLIT_CHAINS[id]) {
      location.replace('index.html?city=&q=' + encodeURIComponent(SPLIT_CHAINS[id]));
      return;
    }
    if (!r && id && HIDDEN_SHOPS[id]) {
      location.replace(HIDDEN_SHOPS[id]);
      return;
    }
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
    if (r.officialUrl && r.officialUrl !== oh) {
      var offLabel = officialLabel(r.officialUrl, true);
      actions.push('<a class="btn ' + (oh ? 'btn-ghost' : 'btn-primary') + ' btn-official" href="' + escapeHtml(r.officialUrl) + '" target="_blank" rel="noopener noreferrer">' + offLabel + '</a>');
    }
    if (r.phone) {
      phoneParts(r.phone).forEach(function (p) {
        var tel = phoneTel(p);
        if (!tel) return;
        actions.push('<a class="btn btn-ghost" href="tel:' + escapeHtml(tel) + '">撥打電話 ' + escapeHtml(p) + '</a>');
      });
    }
    if (r.lineUrl) {
      actions.push('<a class="btn btn-ghost" href="' + escapeHtml(r.lineUrl) + '" target="_blank" rel="noopener noreferrer">LINE 官方帳號</a>');
    }
    actions.push('<button type="button" class="btn btn-ghost" data-report-shop="' + escapeHtml(r.name) + '">通報問題</button>');

    var freeText = '';
    if (r.freeDeliveryThreshold != null) {
      freeText = typeof r.freeDeliveryThreshold === 'number'
        ? ('滿 NT$' + r.freeDeliveryThreshold)
        : (formatThreshold(String(r.freeDeliveryThreshold)) || String(r.freeDeliveryThreshold));
    }
    var feeText = '';
    if (r.deliveryFee != null) {
      feeText = typeof r.deliveryFee === 'number'
        ? ('NT$' + r.deliveryFee)
        : String(r.deliveryFee);
    }

    var backCity = r.city ? ('?city=' + encodeURIComponent(r.city) + (r.district ? '&district=' + encodeURIComponent(encodeDistrictValue(r.city, r.district)) : '')) : '';
    root.innerHTML =
      '<div class="detail-card">' +
        '<a class="back-link" href="index.html' + backCity + '">← 回目錄</a>' +
        '<div class="badges">' + badges.join('') + '</div>' +
        '<h1>' + escapeHtml(r.name) + '</h1>' +
        detailDeliveryHtml(r) +
        (/^https?:\/\//i.test(String(r.imageUrl || '').trim())
          ? '<figure class="shop-photo" style="margin:16px 0 8px;border-radius:12px;overflow:hidden;background:#f3ead8"><img src="' + escapeHtml(r.imageUrl) + '" alt="' + escapeHtml(r.name) + ' 餐點照片" style="display:block;width:100%;height:auto;max-height:440px;object-fit:cover" onerror="this.parentNode.hidden=true" />' +
            '<figcaption style="font-size:12px;color:#7a6a5a;padding:6px 10px;margin:0">餐點照片取自店家官方頁面' + (r.imageSource ? '（<a href="' + escapeHtml(r.imageSource) + '" target="_blank" rel="noopener noreferrer">來源</a>）' : '') + '，實際餐點以店家為準</figcaption></figure>'
          : '') +
        channelChips(r) +
        '<div class="notice">本站不代訂、不收款。請直接在餐廳官方網站／LINE／電話下單。外送門檻與運費以店家官方結帳頁為準。</div>' +
        '<div class="actions">' +
          actions.join('') +
        '</div>' +
        detailMenuHtml(r) +
        detailNoMenuHtml(r) +
        '<dl>' +
          row('料理類型', r.cuisine) +
          row('縣市', r.city) +
          row('行政區', r.district) +
          row('地址', readerProse(r.address) || null) +
          row('起送', (r.deliveryTerms && r.deliveryTerms.minOrder) || null) +
          row('範圍', (r.deliveryTerms && r.deliveryTerms.area) || null) +
          row('結單', (r.deliveryTerms && r.deliveryTerms.cutoff) || null) +
          row('外送條件', r.deliveryNote) +
          row('外送費', feeText || null) +
          row('電話', r.phone ? phoneLinksHtml(r.phone) : null, true) +
          row('官網', r.officialUrl && r.officialUrl !== oh ? ('<a href="' + escapeHtml(r.officialUrl) + '" target="_blank" rel="noopener noreferrer">' + escapeHtml(linkLabel(r.officialUrl)) + '</a>') : null, true) +
          row('官方訂餐連結', oh ? ('<a href="' + escapeHtml(oh) + '" target="_blank" rel="noopener noreferrer">' + escapeHtml(linkLabel(oh)) + '</a>') : null, true) +
          row('LINE', detailLineHtml(r), true) +
          row('營業時間', readerHours(r.hours) || null) +
          row('配送範圍說明', readerProse(r.range) || null) +
          row('免運門檻（參考）', freeText || null) +
          row('最後核對', r.checkedAt) +
          row('外送條件備註', readerProse(r.deliveryNotes) || null) +
          row('說明／條件摘要', readerTerms(r.terms) || null) +
          row('收錄依據摘要', readerProse(r.evidence) || null) +
        '</dl>' +
      '</div>';
  }

  var REPORT_MAIL = 'zisong.taiwan@gmail.com';

  function showReportForm(which, shopName) {
    var suggest = document.getElementById('form-suggest');
    var problem = document.getElementById('form-problem');
    if (!suggest && !problem) return;
    if (suggest) suggest.hidden = which !== 'suggest';
    if (problem) problem.hidden = which !== 'problem';
    var form = which === 'problem' ? problem : suggest;
    if (!form) return;
    if (which === 'problem' && shopName) {
      var shop = form.querySelector('[name="shop"]');
      if (shop) shop.value = shopName;
    }
    var box = document.getElementById('footer-reports') || form;
    if (box.scrollIntoView) box.scrollIntoView({ block: 'start' });
    var focusEl = form.querySelector(which === 'problem' && shopName ? '[name="kind"]' : 'input,select,textarea');
    if (focusEl && focusEl.focus) focusEl.focus();
  }

  function reportField(form, name) {
    var el = form.elements[name];
    return el ? String(el.value || '').trim() : '';
  }

  function sendMailto(subject, lines) {
    var body = lines.filter(Boolean).join('\n');
    window.location.href = 'mailto:' + REPORT_MAIL +
      '?subject=' + encodeURIComponent(subject) +
      '&body=' + encodeURIComponent(body);
  }

  function initReports() {
    document.addEventListener('click', function (e) {
      var t = e.target;
      if (!t || !t.closest) return;
      var openBtn = t.closest('[data-report-open]');
      if (openBtn) {
        e.preventDefault();
        showReportForm(openBtn.getAttribute('data-report-open') || 'problem', '');
        return;
      }
      var shopBtn = t.closest('[data-report-shop]');
      if (shopBtn) {
        e.preventDefault();
        showReportForm('problem', shopBtn.getAttribute('data-report-shop') || '');
      }
    });
    var suggest = document.getElementById('form-suggest');
    if (suggest) {
      suggest.addEventListener('submit', function (e) {
        e.preventDefault();
        var name = reportField(suggest, 'name');
        var place = reportField(suggest, 'place');
        var contact = reportField(suggest, 'contact');
        var note = reportField(suggest, 'note');
        if (!name || !place || !contact) return;
        sendMailto('[自送] 建議加店', [
          '店名：' + name,
          '縣市／行政區：' + place,
          '官方訂餐連結或電話：' + contact,
          note ? ('補充：' + note) : ''
        ]);
      });
    }
    var problem = document.getElementById('form-problem');
    if (problem) {
      problem.addEventListener('submit', function (e) {
        e.preventDefault();
        var shop = reportField(problem, 'shop');
        var kind = reportField(problem, 'kind');
        var note = reportField(problem, 'note');
        if (!shop || !kind) return;
        sendMailto('[自送] 通報問題', [
          '哪一家：' + shop,
          '問題類型：' + kind,
          note ? ('補充：' + note) : ''
        ]);
      });
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    initReports();
    if ($('#list')) initIndex();
    if ($('#detail')) initDetail();
  });
})();
