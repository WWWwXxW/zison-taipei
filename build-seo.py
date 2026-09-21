#!/usr/bin/env python3
"""Regenerate district/*.html, cuisine/*.html, sitemap.xml, robots.txt, index browse blocks."""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://wwwwxxw.github.io/zison-taipei"
TODAY = date.today().isoformat()
SKIP_CUISINE = "餐館（料理類型未公開）"

DISTRICTS = [
    ("中正區", "zhongzheng"),
    ("大同區", "datong"),
    ("中山區", "zhongshan"),
    ("松山區", "songshan"),
    ("大安區", "daan"),
    ("萬華區", "wanhua"),
    ("信義區", "xinyi"),
    ("士林區", "shilin"),
    ("北投區", "beitou"),
    ("內湖區", "neihu"),
    ("南港區", "nangang"),
    ("文山區", "wenshan"),
]
DISTRICT_SLUG = {name: slug for name, slug in DISTRICTS}
DISTRICT_NAME = {slug: name for name, slug in DISTRICTS}

# Bucket pages: slug, display label, keyword list (substring match on cuisine + tags)
BUCKETS = [
    ("taiwanese", "台菜", ["台菜", "台式", "台灣料理", "台灣創意", "客家", "滷肉", "江浙", "上海", "合菜", "中式飯館"]),
    ("hotpot", "火鍋", ["火鍋", "麻辣", "涮鍋", "鍋物", "部隊鍋"]),
    ("japanese", "日式", ["日式", "壽司", "拉麵", "鰻魚", "沖繩", "和菓子", "定食", "丼"]),
    ("italian", "義式", ["義式", "披薩", "義大利", "Pizza", "薄皮披薩"]),
    ("thai", "泰式", ["泰式"]),
    ("korean", "韓式", ["韓式"]),
    ("chinese", "中式", ["中式", "川菜", "江浙", "粵", "湘", "上海", "烤鴨", "燒臘", "熱炒"]),
    ("american", "美式", ["美式", "漢堡", "BBQ", "速食"]),
    ("cafe-dessert", "咖啡甜點", ["甜點", "咖啡", "蛋糕", "可麗露", "烘焙", "甜品", "布丁", "糕點", "雞蛋糕", "豆花", "巧克力"]),
    ("bento", "便當小吃", ["便當", "小吃", "餐盒", "滷味", "雞排", "蔥油餅", "鹹水雞", "炸物"]),
]
BUCKET_SLUGS = {s for s, _, _ in BUCKETS}

# Exact cuisineTag → slug (same table as before + new Oddle tags)
TAG_SLUG = {
    "台菜": "taiwanese",
    "泰式": "thai",
    "韓式": "korean",
    "美式": "american",
    "火鍋": "hotpot",
    "日式": "japanese",
    "義式": "italian",
    "中式": "chinese",
    "Pizza": "pizza",
    "手搖飲": "hand-drink",
    "手搖飲料": "hand-beverage",
    "咖啡": "coffee",
    "甜點": "dessert",
    "早午餐": "brunch",
    "可麗露": "cannele",
    "咖啡豆": "coffee-beans",
    "素食蔬食": "vegetarian",
    "輕食": "light-bites",
    "台式便當": "taiwanese-bento",
    "西式料理": "western",
    "伴手禮": "souvenir",
    "南北貨": "dry-goods",
    "烘焙": "bakery",
    "健康餐盒": "healthy-box",
    "甜品": "tianpin",
    "蛋糕": "cake",
    "會議便當": "meeting-bento",
    "會議餐盒": "meeting-box",
    "茶飲": "tea-drink",
    # New Oddle discover tags (≥3 expected)
    "私房甜點": "private-dessert",
    "蔬食友善": "veggie-friendly",
    "蛋糕甜點": "cake-dessert",
    "中港料理": "chinese-hk",
    "南洋料理": "nanyang",
    "義法料理": "italo-french",
    "生鮮系列": "fresh-goods",
    "美式餐點": "american-meals",
    "日本和食": "washoku",
    "泰式料理": "thai-cuisine",
    "歐式料理": "european",
    "麻辣鍋": "mala-hotpot",
    "海鮮合菜": "seafood-banquet",
    "西餐廳": "western-dining",
    "台北早午餐": "taipei-brunch",
    "海鮮百匯": "seafood-buffet",
    "韓國料理": "korean-cuisine",
}


def escape_html(s: object) -> str:
    return (
        str(s if s is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def blob(r: dict) -> str:
    return (r.get("cuisine") or "") + " " + " ".join(r.get("cuisineTags") or [])


def order_href(r: dict) -> str | None:
    return r.get("orderUrl") or r.get("lineUrl") or None


def card_html(r: dict, prefix: str = "../") -> str:
    badges = [f'<span class="badge district">{escape_html(r.get("district") or "台北")}</span>']
    if r.get("chain"):
        badges.append('<span class="badge chain">連鎖</span>')
    actions = []
    oh = order_href(r)
    if oh:
        actions.append(
            f'<a class="btn btn-primary" href="{escape_html(oh)}" target="_blank" rel="noopener noreferrer">前往訂餐</a>'
        )
    phone = r.get("phone")
    if phone:
        tel = re.sub(r"-", "", phone)
        actions.append(f'<a class="btn btn-ghost" href="tel:{escape_html(tel)}">{escape_html(phone)}</a>')
    rid = r.get("id") or ""
    actions.append(f'<a class="btn btn-ghost" href="{prefix}detail.html?id={escape_html(rid)}">詳情</a>')
    parts = [
        f'<article class="card" data-id="{escape_html(rid)}">',
        f'<div class="badges">{"".join(badges)}</div>',
        f'<h2><a href="{prefix}detail.html?id={escape_html(rid)}">{escape_html(r.get("name"))}</a></h2>',
    ]
    if r.get("cuisine"):
        parts.append(f'<p class="cuisine-line">{escape_html(r["cuisine"])}</p>')
    if r.get("address"):
        parts.append(f'<p class="addr">{escape_html(r["address"])}</p>')
    if r.get("hours"):
        parts.append(f'<p class="hours">時段：{escape_html(r["hours"])}</p>')
    parts.append(f'<div class="actions">{"".join(actions)}</div></article>')
    return "".join(parts)


    # placeholder replaced below
    pass


# Use Python's locale-aware sort via str — zh collation approx by unicode
def sort_by_name(items: list[dict]) -> list[dict]:
    return sorted(items, key=lambda r: (r.get("name") or ""))


def slugify_tag(tag: str) -> str:
    if tag in TAG_SLUG:
        return TAG_SLUG[tag]
    # Fallback: try pypinyin if available
    try:
        from pypinyin import lazy_pinyin

        s = "-".join(lazy_pinyin(tag))
        s = re.sub(r"[^a-z0-9-]+", "-", s.lower()).strip("-")
        return s or "cuisine"
    except Exception:
        s = re.sub(r"\s+", "-", tag.lower())
        s = re.sub(r"[^a-z0-9\u4e00-\u9fff-]+", "", s)
        return s or "cuisine"


def resolve_tag_page_slug(tag: str) -> str:
    base = slugify_tag(tag)
    if base in BUCKET_SLUGS:
        return f"{base}-tag"
    return base


def district_page(name: str, slug: str, items: list[dict], all_district_counts: list[tuple[str, str, int]]) -> str:
    n = len(items)
    cards = "\n".join(card_html(r) for r in sort_by_name(items))
    nav_items = []
    for oname, oslug, oc in all_district_counts:
        if oslug == slug:
            continue
        nav_items.append(f'        <li><a href="{oslug}.html">{escape_html(oname)}</a>（{oc}）</li>')
    nav = "\n".join(nav_items)
    desc = f"整理{name}可經餐廳官網、LINE 或電話直接外送／宅配的店家，目前 {n} 家。自送官方外送目錄，不經外送平台。"
    filt = quote(name)
    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="description" content="{escape_html(desc)}" />
  <link rel="canonical" href="{BASE}/district/{slug}.html" />
  <title>{escape_html(name)}自送餐廳｜官方外送目錄｜自送</title>
  <link rel="stylesheet" href="../style.css" />
</head>
<body>
  <header class="site-header">
    <div class="inner">
      <div class="brand">
        <h1>自送</h1>
        <span class="tag">{escape_html(name)}</span>
      </div>
      <p class="tagline">找店家官方點餐與外送｜少吃平台價</p>
      <nav class="nav" aria-label="主要">
        <a href="../index.html">店家目錄</a>
        <a href="../about.html">關於本站</a>
      </nav>
    </div>
  </header>

  <main class="wrap">
    <article class="prose district-intro">
      <h1>{escape_html(name)}自送餐廳</h1>
      <p>尋找<strong>{escape_html(name)}</strong>可用餐廳官方網站、LINE 或電話直接外送／宅配的店家。本頁以靜態方式列出目前目錄中的 {n} 家；點「前往訂餐」即前往店家官方通道。本站不代訂、不收款。</p>
      <p class="district-actions">
        <a class="btn btn-primary" href="../index.html?district={filt}">在目錄篩選</a>
        <a class="btn btn-ghost" href="../index.html">全部店家</a>
      </p>
    </article>

    <div class="meta-bar">
      <div>共 <strong>{n}</strong> 家</div>
      <div>條件以店家官方頁為準</div>
    </div>

    <section class="cards" aria-label="店家列表">
{cards}
    </section>

    <nav class="prose district-nav" aria-label="其他行政區">
      <h2>其他行政區</h2>
      <ul class="district-link-list">
{nav}
      </ul>
    </nav>
  </main>

  <footer class="site-footer">
    <div class="inner">
      <p>© 自送 — 免費公開目錄。訂單與配送請直接與餐廳聯繫。</p>
      <p><a href="../about.html">目錄說明</a> · <a href="../index.html">店家目錄</a></p>
    </div>
  </footer>
</body>
</html>
"""


def cuisine_page(slug: str, label: str, items: list[dict], all_cuisine_counts: list[tuple[str, str, int]]) -> str:
    n = len(items)
    cards = "\n".join(card_html(r) for r in sort_by_name(items))
    nav_items = []
    for olabel, oslug, oc in all_cuisine_counts:
        if oslug == slug:
            continue
        nav_items.append(f'        <li><a href="{oslug}.html">{escape_html(olabel)}</a>（{oc}）</li>')
    nav = "\n".join(nav_items)
    desc = f"整理台北可經官方通道外送／宅配的{label}店家，目前 {n} 家。自送目錄，不經外送平台。"
    filt = quote(label)
    return f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="description" content="{escape_html(desc)}" />
  <link rel="canonical" href="{BASE}/cuisine/{slug}.html" />
  <title>台北{escape_html(label)}自送餐廳｜官方外送目錄｜自送</title>
  <link rel="stylesheet" href="../style.css" />
</head>
<body>
  <header class="site-header">
    <div class="inner">
      <div class="brand">
        <h1>自送</h1>
        <span class="tag">{escape_html(label)}</span>
      </div>
      <p class="tagline">找店家官方點餐與外送｜少吃平台價</p>
      <nav class="nav" aria-label="主要">
        <a href="../index.html">店家目錄</a>
        <a href="../about.html">關於本站</a>
      </nav>
    </div>
  </header>

  <main class="wrap">
    <article class="prose district-intro">
      <h1>台北{escape_html(label)}自送餐廳</h1>
      <p>以下為目錄中標示與<strong>{escape_html(label)}</strong>相關、且可經餐廳官網／LINE／電話直接外送或宅配的店家（目前 {n} 家）。本站不代訂、不收款。</p>
      <p class="district-actions">
        <a class="btn btn-primary" href="../index.html?cuisine={filt}">在目錄篩選</a>
        <a class="btn btn-ghost" href="../index.html">全部店家</a>
      </p>
    </article>

    <div class="meta-bar">
      <div>共 <strong>{n}</strong> 家</div>
      <div>條件以店家官方頁為準</div>
    </div>

    <section class="cards" aria-label="店家列表">
{cards}
    </section>

    <nav class="prose district-nav" aria-label="其他料理">
      <h2>其他料理分類</h2>
      <ul class="district-link-list">
{nav}
      </ul>
    </nav>
  </main>

  <footer class="site-footer">
    <div class="inner">
      <p>© 自送 — 免費公開目錄。訂單與配送請直接與餐廳聯繫。</p>
      <p><a href="../about.html">目錄說明</a> · <a href="../index.html">店家目錄</a></p>
    </div>
  </footer>
</body>
</html>
"""


def build_sitemap(district_slugs: list[str], cuisine_slugs: list[str]) -> str:
    urls = [
        ("/", 1.0, "weekly"),
        ("/index.html", 1.0, "weekly"),
        ("/about.html", 0.5, "monthly"),
    ]
    for s in district_slugs:
        urls.append((f"/district/{s}.html", 0.8, "weekly"))
    for s in cuisine_slugs:
        urls.append((f"/cuisine/{s}.html", 0.7, "weekly"))
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, pri, freq in urls:
        loc = BASE + ("" if path == "/" else path)
        if path == "/":
            loc = BASE + "/"
        parts.append("  <url>")
        parts.append(f"    <loc>{loc}</loc>")
        parts.append(f"    <lastmod>{TODAY}</lastmod>")
        parts.append(f"    <changefreq>{freq}</changefreq>")
        parts.append(f"    <priority>{pri}</priority>")
        parts.append("  </url>")
    parts.append("</urlset>")
    return "\n".join(parts) + "\n"


ROBOTS = f"""User-agent: *
Allow: /

Sitemap: {BASE}/sitemap.xml
"""


def update_index(district_counts: list[tuple[str, str, int]], cuisine_counts: list[tuple[str, str, int]]) -> None:
    index_path = ROOT / "index.html"
    text = index_path.read_text(encoding="utf-8")
    d_lis = "\n".join(
        f'        <li><a href="district/{slug}.html">{escape_html(name)}</a><span class="muted">（{n}）</span></li>'
        for name, slug, n in district_counts
    )
    c_lis = "\n".join(
        f'        <li><a href="cuisine/{slug}.html">{escape_html(label)}</a><span class="muted">（{n}）</span></li>'
        for label, slug, n in cuisine_counts
    )
    text2, n1 = re.subn(
        r'(<ul class="browse-list">\n)(.*?)(\n        </ul>\n      </div>\n      <div class="prose browse-block">\n        <h2>依料理瀏覽</h2>)',
        r"\1" + d_lis + r"\3",
        text,
        count=1,
        flags=re.S,
    )
    text3, n2 = re.subn(
        r'(<h2>依料理瀏覽</h2>\n        <ul class="browse-list">\n)(.*?)(\n        </ul>\n      </div>\n    </section>)',
        r"\1" + c_lis + r"\3",
        text2,
        count=1,
        flags=re.S,
    )
    if n1 != 1 or n2 != 1:
        raise SystemExit(f"index.html browse block replace failed: district={n1} cuisine={n2}")
    index_path.write_text(text3, encoding="utf-8")


def main() -> None:
    data = json.loads((ROOT / "restaurants.json").read_text(encoding="utf-8"))
    assert isinstance(data, list) and len(data) > 0

    # --- Districts ---
    by_district: dict[str, list[dict]] = defaultdict(list)
    for r in data:
        d = r.get("district")
        if d in DISTRICT_SLUG:
            by_district[d].append(r)

    district_pages: list[tuple[str, str, int, list[dict]]] = []
    for name, slug in DISTRICTS:
        items = by_district.get(name) or []
        if not items:
            continue
        district_pages.append((name, slug, len(items), items))

    district_counts_sorted = sorted(
        [(n, s, c) for n, s, c, _ in district_pages], key=lambda x: (-x[2], x[0])
    )

    dist_dir = ROOT / "district"
    dist_dir.mkdir(exist_ok=True)
    for old in dist_dir.glob("*.html"):
        old.unlink()
    for name, slug, _c, items in district_pages:
        (dist_dir / f"{slug}.html").write_text(
            district_page(name, slug, items, district_counts_sorted), encoding="utf-8"
        )

    # --- Cuisines ---
    cuisine_groups: dict[str, tuple[str, list[dict]]] = {}  # slug -> (label, items)

    for slug, label, kws in BUCKETS:
        items = [r for r in data if any(k in blob(r) for k in kws)]
        if len(items) >= 3:
            cuisine_groups[slug] = (label, items)

    tag_counts: Counter[str] = Counter()
    tag_members: dict[str, list[dict]] = defaultdict(list)
    for r in data:
        seen = set()
        for t in r.get("cuisineTags") or []:
            if not t or t == SKIP_CUISINE or t in seen:
                continue
            seen.add(t)
            tag_counts[t] += 1
            tag_members[t].append(r)

    for tag, cnt in tag_counts.items():
        if cnt < 3 or tag == SKIP_CUISINE:
            continue
        slug = resolve_tag_page_slug(tag)
        # If slug already used by a bucket with same label semantics, keep bucket;
        # -tag pages are for exact membership when base slug is a bucket.
        if slug in cuisine_groups and not slug.endswith("-tag"):
            # Exact tag page would overwrite bucket — only skip if it's the same membership intent.
            # Buckets always win the base slug; exact-only tags that map to unused slugs are fine.
            # If TAG_SLUG maps to a bucket slug without -tag (shouldn't after resolve), skip.
            continue
        cuisine_groups[slug] = (tag, tag_members[tag])

    cuisine_counts_sorted = sorted(
        [(label, slug, len(items)) for slug, (label, items) in cuisine_groups.items()],
        key=lambda x: (-x[2], x[0]),
    )

    cui_dir = ROOT / "cuisine"
    cui_dir.mkdir(exist_ok=True)
    for old in cui_dir.glob("*.html"):
        old.unlink()
    for slug, (label, items) in cuisine_groups.items():
        (cui_dir / f"{slug}.html").write_text(
            cuisine_page(slug, label, items, cuisine_counts_sorted), encoding="utf-8"
        )

    # --- sitemap + robots ---
    dist_slugs = [s for _, s, _ in district_counts_sorted]
    cui_slugs = [s for _, s, _ in cuisine_counts_sorted]
    (ROOT / "sitemap.xml").write_text(build_sitemap(dist_slugs, cui_slugs), encoding="utf-8")
    (ROOT / "robots.txt").write_text(ROBOTS, encoding="utf-8")

    # --- index browse ---
    update_index(district_counts_sorted, cuisine_counts_sorted)

    # Report
    print(f"restaurants: {len(data)}")
    print(f"district_pages: {len(district_counts_sorted)}")
    for name, slug, n in district_counts_sorted:
        print(f"  district/{slug}.html\t{name}\t{n}")
    print(f"cuisine_pages: {len(cuisine_counts_sorted)}")
    for label, slug, n in cuisine_counts_sorted:
        print(f"  cuisine/{slug}.html\t{label}\t{n}")


if __name__ == "__main__":
    main()
