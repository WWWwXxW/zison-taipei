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

    # New Taipei
    ("板橋區", "banqiao"),
    ("中和區", "zhonghe"),
    ("永和區", "yonghe"),
    ("新莊區", "xinzhuang"),
    ("三重區", "sanchong"),
    ("蘆洲區", "luzhou"),
    ("土城區", "tucheng"),
    ("樹林區", "shulin"),
    ("淡水區", "tamsui"),
    ("林口區", "linkou"),
    ("汐止區", "xizhi"),
    ("新店區", "xindian"),
    ("八里區", "bali"),
    ("深坑區", "shenkeng"),
    ("三峽區", "sanxia"),
    ("五股區", "wugu"),
    ("鶯歌區", "yingge"),
    ("瑞芳區", "ruifang"),
    ("金山區", "jinshan"),
    ("三芝區", "sanzhi"),
    ("石門區", "shimen"),
    ("坪林區", "pinglin"),
    ("貢寮區", "gongliao"),
    ("萬里區", "wanli"),
    ("雙溪區", "shuangxi"),
    ("平溪區", "pingxi"),
    ("烏來區", "wulai"),
    ("石碇區", "shiding"),
    ("泰山區", "taishan"),
    ("新北多區", "newtaipei-multi"),

    # Taichung
    ("中區", "taichung-central"),
    ("東區", "taichung-east"),
    ("南區", "taichung-south"),
    ("西區", "taichung-west"),
    ("北區", "taichung-north"),
    ("北屯區", "beitun"),
    ("西屯區", "xitun"),
    ("南屯區", "nantun"),
    ("太平區", "taiping"),
    ("大里區", "dali"),
    ("霧峰區", "wufeng"),
    ("烏日區", "wuri"),
    ("豐原區", "fengyuan"),
    ("后里區", "houli"),
    ("石岡區", "shigang"),
    ("東勢區", "dongshi"),
    ("和平區", "heping"),
    ("新社區", "xinshe"),
    ("潭子區", "tanzi"),
    ("大雅區", "daya"),
    ("神岡區", "shengang"),
    ("大肚區", "dadu"),
    ("沙鹿區", "shalu"),
    ("龍井區", "longjing"),
    ("梧棲區", "wuqi"),
    ("清水區", "qingshui"),
    ("大甲區", "dajia"),
    ("外埔區", "waipu"),
    ("台中大安區", "taichung-daan"),
    ("台中多區", "taichung-multi"),

    # Kaohsiung
    ("三民區", "sanmin"),
    ("鳳山區", "fengshan"),
    ("左營區", "zuoying"),
    ("苓雅區", "lingya"),
    ("新興區", "xinxing"),
    ("楠梓區", "nanzi"),
    ("前鎮區", "qianzhen"),
    ("鼓山區", "gushan"),
    ("小港區", "xiaogang"),
    ("仁武區", "renwu"),
    ("前金區", "qianjin"),
    ("鹽埕區", "yancheng"),
    ("岡山區", "gangshan"),
    ("路竹區", "luzhu"),
    ("大社區", "dashe"),
    ("彌陀區", "mito"),
    ("旗山區", "qishan"),
    ("旗津區", "qijin"),
    ("鳥松區", "niaosong"),
    ("林園區", "linyuan"),
    ("湖內區", "hunei"),
    ("茄萣區", "qieding"),
    ("橋頭區", "qiaotou"),
    ("燕巢區", "yanchao"),
    ("梓官區", "ziguan"),
    ("大寮區", "daliao"),
    ("大樹區", "dashu"),
    ("美濃區", "meinong"),
    ("高雄多區", "kaohsiung-multi"),

    # Taoyuan
    ("桃園區", "taoyuan"),
    ("中壢區", "zhongli"),
    ("平鎮區", "pingzhen"),
    ("八德區", "bade"),
    ("楊梅區", "yangmei"),
    ("蘆竹區", "taoyuan-luzhu"),  # distinct from Kaohsiung 路竹區 luzhu
    ("大溪區", "daxi"),
    ("龍潭區", "longtan"),
    ("龜山區", "guishan"),
    ("大園區", "dayuan"),
    ("觀音區", "guanyin"),
    ("新屋區", "xinwu"),
    ("復興區", "fuxing-ty"),
    ("桃園多區", "taoyuan-multi"),

    # Tainan (東/南/北區 already listed under Taichung — shared slug; unique districts below)
    ("中西區", "zhongxi"),
    ("安平區", "anping"),
    ("安南區", "annan"),
    ("永康區", "yongkang"),
    ("歸仁區", "guiren"),
    ("新化區", "xinhua-tn"),
    ("左鎮區", "zuozhen"),
    ("玉井區", "yujing"),
    ("楠西區", "nanxi"),
    ("南化區", "nanhua"),
    ("仁德區", "rende"),
    ("關廟區", "guanmiao"),
    ("龍崎區", "longqi"),
    ("官田區", "guantian"),
    ("麻豆區", "madou"),
    ("佳里區", "jiali"),
    ("西港區", "xigang"),
    ("七股區", "qigu"),
    ("將軍區", "jiangjun"),
    ("學甲區", "xuejia"),
    ("北門區", "beimen"),
    ("新營區", "xinying"),
    ("後壁區", "houbi"),
    ("白河區", "baihe"),
    ("東山區", "dongshan"),
    ("六甲區", "liujia"),
    ("下營區", "xiaying"),
    ("柳營區", "liuying"),
    ("鹽水區", "yanshui"),
    ("善化區", "shanhua"),
    ("大內區", "danei"),
    ("山上區", "shangshan"),
    ("新市區", "xinshi"),
    ("安定區", "anding"),
    ("台南多區", "tainan-multi"),

    # Hsinchu City
    ("香山區", "xiangshan"),
    ("新竹市多區", "hsinchu-city-multi"),

    # Hsinchu County
    ("竹北市", "zhubei"),
    ("竹東鎮", "zhudong"),
    ("新埔鎮", "xinpu"),
    ("關西鎮", "guanxi"),
    ("湖口鄉", "hukou"),
    ("新豐鄉", "xinfeng"),
    ("芎林鄉", "qionglin"),
    ("橫山鄉", "hengshan"),
    ("北埔鄉", "beipu"),
    ("寶山鄉", "baoshan"),
    ("峨眉鄉", "emei"),
    ("尖石鄉", "jianshi"),
    ("五峰鄉", "wufeng-hc"),
    ("新竹縣多區", "hsinchu-county-multi"),

    # Changhua City (single-level — district label = 彰化市)
    ("彰化市", "changhua-city"),
    ("彰化市多區", "changhua-city-multi"),

    # Changhua County
    ("員林市", "yuanlin"),
    ("鹿港鎮", "lukang"),
    ("和美鎮", "heme"),
    ("北斗鎮", "beidou"),
    ("溪湖鎮", "xihu"),
    ("田中鎮", "tianzhong"),
    ("二林鎮", "erlin"),
    ("線西鄉", "xianxi"),
    ("伸港鄉", "shengang"),
    ("福興鄉", "fuxing-ch"),
    ("秀水鄉", "xiushui"),
    ("花壇鄉", "huatan"),
    ("芬園鄉", "fenyuan"),
    ("大村鄉", "dacun"),
    ("埔鹽鄉", "puyan"),
    ("埔心鄉", "puxin"),
    ("永靖鄉", "yongjing"),
    ("社頭鄉", "shetou"),
    ("彰化縣多區", "changhua-county-multi"),

    # Yunlin County
    ("斗六市", "douliu"),
    ("斗南鎮", "dounan"),
    ("虎尾鎮", "huwei"),
    ("西螺鎮", "xiluo"),
    ("土庫鎮", "tuku"),
    ("北港鎮", "beigang"),
    ("古坑鄉", "gukeng"),
    ("大埤鄉", "dapi"),
    ("莿桐鄉", "citong"),
    ("林內鄉", "linnei"),
    ("二崙鄉", "erlun"),
    ("崙背鄉", "lunbei"),
    ("麥寮鄉", "mailiao"),
    ("東勢鄉", "dongshi-yl"),
    ("褒忠鄉", "baozhong"),
    ("台西鄉", "taixi"),
    ("元長鄉", "yuanchang"),
    ("四湖鄉", "sihu"),
    ("口湖鄉", "kouhu"),
    ("水林鄉", "shuilin"),
    ("雲林縣多區", "yunlin-county-multi"),

    # Chiayi City (東區/西區 are AMBIGUOUS — shared slug with Taichung; browse uses city|district filter)
    ("嘉義市多區", "chiayi-city-multi"),

    # Chiayi County
    ("太保市", "taibao"),
    ("朴子市", "puzi"),
    ("民雄鄉", "minxiong"),
    ("大林鎮", "dalin"),
    ("中埔鄉", "zhongpu"),
    ("水上鄉", "shuishang"),
    ("番路鄉", "fanlu"),
    ("新港鄉", "xingang-cy"),
    ("六腳鄉", "liujiao"),
    ("東石鄉", "dongshi-cy"),
    ("布袋鎮", "budai"),
    ("義竹鄉", "yizhu"),
    ("鹿草鄉", "lucao"),
    ("竹崎鄉", "zhuqi"),
    ("梅山鄉", "meishan"),
    ("阿里山鄉", "alishan"),
    ("溪口鄉", "xikou"),
    ("嘉義縣多區", "chiayi-county-multi"),
]
DISTRICT_SLUG = {name: slug for name, slug in DISTRICTS}
DISTRICT_NAME = {slug: name for name, slug in DISTRICTS}

CITY_ORDER = ["台北市", "新北市", "桃園市", "新竹市", "新竹縣", "台中市", "彰化市", "彰化縣", "雲林縣", "嘉義市", "嘉義縣", "台南市", "高雄市"]

# District → city (same partitions as DISTRICTS list above)
_DISTRICT_CITY_PARTS = [
    (["中正區", "大同區", "中山區", "松山區", "大安區", "萬華區", "信義區", "士林區", "北投區", "內湖區", "南港區", "文山區", "台北多區"], "台北市"),
    (["板橋區", "中和區", "永和區", "新莊區", "三重區", "蘆洲區", "土城區", "樹林區", "淡水區", "林口區", "汐止區", "新店區", "八里區", "深坑區", "三峽區", "五股區", "鶯歌區", "瑞芳區", "金山區", "三芝區", "石門區", "坪林區", "貢寮區", "萬里區", "雙溪區", "平溪區", "烏來區", "石碇區", "泰山區", "新北多區"], "新北市"),
    (["中區", "東區", "南區", "西區", "北區", "北屯區", "西屯區", "南屯區", "太平區", "大里區", "霧峰區", "烏日區", "豐原區", "后里區", "石岡區", "東勢區", "和平區", "新社區", "潭子區", "大雅區", "神岡區", "大肚區", "沙鹿區", "龍井區", "梧棲區", "清水區", "大甲區", "外埔區", "台中大安區", "台中多區"], "台中市"),
    (["三民區", "鳳山區", "左營區", "苓雅區", "新興區", "楠梓區", "前鎮區", "鼓山區", "小港區", "仁武區", "前金區", "鹽埕區", "岡山區", "路竹區", "大社區", "彌陀區", "旗山區", "旗津區", "鳥松區", "林園區", "湖內區", "茄萣區", "橋頭區", "燕巢區", "梓官區", "大寮區", "大樹區", "美濃區", "高雄多區"], "高雄市"),
    (["桃園區", "中壢區", "平鎮區", "八德區", "楊梅區", "蘆竹區", "大溪區", "龍潭區", "龜山區", "大園區", "觀音區", "新屋區", "復興區", "桃園多區"], "桃園市"),
    (["中西區", "安平區", "安南區", "永康區", "歸仁區", "新化區", "左鎮區", "玉井區", "楠西區", "南化區", "仁德區", "關廟區", "龍崎區", "官田區", "麻豆區", "佳里區", "西港區", "七股區", "將軍區", "學甲區", "北門區", "新營區", "後壁區", "白河區", "東山區", "六甲區", "下營區", "柳營區", "鹽水區", "善化區", "大內區", "山上區", "新市區", "安定區", "台南多區"], "台南市"),
    (["香山區", "新竹市多區"], "新竹市"),
    (["竹北市", "竹東鎮", "新埔鎮", "關西鎮", "湖口鄉", "新豐鄉", "芎林鄉", "橫山鄉", "北埔鄉", "寶山鄉", "峨眉鄉", "尖石鄉", "五峰鄉", "新竹縣多區"], "新竹縣"),
    (["彰化市", "彰化市多區"], "彰化市"),
    (["員林市", "鹿港鎮", "和美鎮", "北斗鎮", "溪湖鎮", "田中鎮", "二林鎮", "線西鄉", "伸港鄉", "福興鄉", "秀水鄉", "花壇鄉", "芬園鄉", "大村鄉", "埔鹽鄉", "埔心鄉", "永靖鄉", "社頭鄉", "彰化縣多區"], "彰化縣"),
    (["斗六市", "斗南鎮", "虎尾鎮", "西螺鎮", "土庫鎮", "北港鎮", "古坑鄉", "大埤鄉", "莿桐鄉", "林內鄉", "二崙鄉", "崙背鄉", "麥寮鄉", "東勢鄉", "褒忠鄉", "台西鄉", "元長鄉", "四湖鄉", "口湖鄉", "水林鄉", "雲林縣多區"], "雲林縣"),
    (["嘉義市多區"], "嘉義市"),
    (["太保市", "朴子市", "民雄鄉", "大林鎮", "中埔鄉", "水上鄉", "番路鄉", "新港鄉", "六腳鄉", "東石鄉", "布袋鎮", "義竹鄉", "鹿草鄉", "竹崎鄉", "梅山鄉", "阿里山鄉", "溪口鄉", "嘉義縣多區"], "嘉義縣"),
]
DISTRICT_CITY: dict[str, str] = {}
for _names, _city in _DISTRICT_CITY_PARTS:
    for _n in _names:
        DISTRICT_CITY[_n] = _city

AMBIGUOUS_DISTRICTS = {"北區", "南區", "東區", "西區", "中區"}

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
    badges = []
    district = r.get("district") or ""
    city = r.get("city") or ""
    if district:
        badges.append(f'<span class="badge district">{escape_html(district)}</span>')
    if city:
        badges.append(f'<span class="badge city">{escape_html(city)}</span>')
    if not badges:
        badges.append('<span class="badge district">未標行政區</span>')
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
    city = ""
    if items:
        city = (items[0].get("city") or "") or DISTRICT_CITY.get(name, "")
    else:
        city = DISTRICT_CITY.get(name, "")
    if name in AMBIGUOUS_DISTRICTS and city:
        filt_d = quote(f"{city}|{name}")
    else:
        filt_d = quote(name)
    city_q = f"&city={quote(city)}" if city else ""
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
        <a class="btn btn-primary" href="../index.html?district={filt_d}{city_q}">在目錄篩選</a>
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


def update_index(
    district_counts: list[tuple[str, str, int]],
    cuisine_counts: list[tuple[str, str, int]],
    data: list[dict],
) -> None:
    """Rewrite index browse: city-grouped districts + cuisine list.

    Groups by live venue city so multi-city ambiguous districts (東區/西區/…)
    appear under each city. Ambiguous districts link to index filter
    (?city=&district=city|district); unique districts link to static pages.
    """
    index_path = ROOT / "index.html"
    text = index_path.read_text(encoding="utf-8")

    slug_of = {name: slug for name, slug, _n in district_counts}
    # Live counts: city → district → n
    live: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in data:
        c = (r.get("city") or "").strip()
        d = (r.get("district") or "").strip()
        if c and d:
            live[c][d] += 1

    city_keys = [c for c in CITY_ORDER if c in live]
    for c in sorted(live.keys()):
        if c not in city_keys:
            city_keys.append(c)

    parts: list[str] = []
    for city in city_keys:
        items = sorted(live[city].items(), key=lambda x: (-x[1], x[0]))
        parts.append(f"        <h3>{escape_html(city)}</h3>")
        parts.append('        <ul class="browse-list">')
        for name, n in items:
            if name in AMBIGUOUS_DISTRICTS:
                href = f"index.html?city={quote(city)}&district={quote(city + '|' + name)}"
                label = name
            elif name in slug_of:
                href = f"district/{slug_of[name]}.html"
                label = name
            else:
                href = f"index.html?city={quote(city)}&district={quote(name)}"
                label = name
            parts.append(
                f'        <li><a href="{href}">{escape_html(label)}</a>'
                f'<span class="muted">（{n}）</span></li>'
            )
        parts.append("        </ul>")
    d_block = "\n".join(parts)

    c_lis = "\n".join(
        f'        <li><a href="cuisine/{slug}.html">{escape_html(label)}</a>'
        f'<span class="muted">（{n}）</span></li>'
        for label, slug, n in cuisine_counts
    )

    text2, n1 = re.subn(
        r'(<div class="prose browse-block">\n\s*<h2>)依(?:行政區|縣市)瀏覽(</h2>\n)(.*?)(\n      </div>\n      <div class="prose browse-block">\n        <h2>依料理瀏覽</h2>)',
        r"\1依縣市瀏覽\2" + d_block + r"\4",
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
    text3 = text3.replace("依行政區／料理瀏覽所有分類", "依縣市／料理瀏覽所有分類")
    text3 = text3.replace("依縣市／料理瀏覽所有分類", "依縣市／料理瀏覽所有分類")  # idempotent
    if n1 != 1 or n2 != 1:
        raise SystemExit(f"index.html browse block replace failed: district={n1} cuisine={n2}")
    index_path.write_text(text3, encoding="utf-8")


def main() -> None:
    data = json.loads((ROOT / "restaurants.json").read_text(encoding="utf-8"))
    assert isinstance(data, list) and len(data) > 0
    missing_city = [r.get("id") for r in data if not (r.get("city") or "").strip()]
    if missing_city:
        raise SystemExit(f"city coverage incomplete: {len(missing_city)} venues missing city: {missing_city[:50]}")

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
    update_index(district_counts_sorted, cuisine_counts_sorted, data)

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
