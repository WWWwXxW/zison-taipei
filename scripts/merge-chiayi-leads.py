#!/usr/bin/env python3
"""Merge Chiayi Scout corpus into restaurants.json.
Preserves city=嘉義市 and city=嘉義縣 as separate values.
Merchant channels only; dedupe name+district & order URL."""
from __future__ import annotations

import importlib.util
import json
import re
import sys
import unicodedata
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
CORPUS = Path("/workspace/chiayi-own-delivery-leads.md")
TODAY = date.today().isoformat()
ID_PREFIX = "cy-scout-lead"

_bf_path = Path(__file__).resolve().parent / "backfill-delivery-min.py"
_spec = importlib.util.spec_from_file_location("backfill_delivery_min", _bf_path)
_bf = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_bf)
infer_delivery_min = _bf.infer

# 嘉義市 districts
CY_CITY_DISTRICT_CANON = {
    "東": "東區", "東區": "東區",
    "西": "西區", "西區": "西區",
    "嘉義市多區": "嘉義市多區",
}
# 嘉義縣 districts (市／鎮／鄉)
CY_COUNTY_DISTRICT_CANON = {
    "太保": "太保市", "太保市": "太保市",
    "朴子": "朴子市", "朴子市": "朴子市",
    "民雄": "民雄鄉", "民雄鄉": "民雄鄉",
    "大林": "大林鎮", "大林鎮": "大林鎮",
    "中埔": "中埔鄉", "中埔鄉": "中埔鄉",
    "水上": "水上鄉", "水上鄉": "水上鄉",
    "番路": "番路鄉", "番路鄉": "番路鄉",
    "新港": "新港鄉", "新港鄉": "新港鄉",
    "六腳": "六腳鄉", "六腳鄉": "六腳鄉",
    "東石": "東石鄉", "東石鄉": "東石鄉",
    "布袋": "布袋鎮", "布袋鎮": "布袋鎮",
    "義竹": "義竹鄉", "義竹鄉": "義竹鄉",
    "鹿草": "鹿草鄉", "鹿草鄉": "鹿草鄉",
    "竹崎": "竹崎鄉", "竹崎鄉": "竹崎鄉",
    "梅山": "梅山鄉", "梅山鄉": "梅山鄉",
    "阿里山": "阿里山鄉", "阿里山鄉": "阿里山鄉",
    "溪口": "溪口鄉", "溪口鄉": "溪口鄉",
    "嘉義縣多區": "嘉義縣多區",
}
DISTRICT_CANON = {**CY_CITY_DISTRICT_CANON, **CY_COUNTY_DISTRICT_CANON}
DISTRICT_SHORT = {
    "東區": "東", "西區": "西",
    "太保市": "太保", "朴子市": "朴子", "民雄鄉": "民雄", "大林鎮": "大林",
    "中埔鄉": "中埔", "水上鄉": "水上", "番路鄉": "番路",
    "新港鄉": "新港", "六腳鄉": "六腳", "東石鄉": "東石", "布袋鎮": "布袋",
    "義竹鄉": "義竹", "鹿草鄉": "鹿草", "竹崎鄉": "竹崎", "梅山鄉": "梅山",
    "阿里山鄉": "阿里山", "溪口鄉": "溪口",
}

CITY_DISTRICT_KEYS = {
    "嘉義市": ["東區", "西區", "東", "西"],
    "嘉義縣": [
        "太保", "朴子", "民雄", "大林", "中埔", "水上", "番路",
        "新港", "六腳", "東石", "布袋", "義竹", "鹿草", "竹崎",
        "梅山", "阿里山", "溪口",
    ],
}

PLATFORM_HOST_RE = re.compile(
    r"(ubereats\.com|uber\.com|foodpanda\.(tw|com)|deliveryhero|"
    r"google\.(com|com\.tw)/maps|maps\.app\.goo\.gl|ifoodie\.tw|"
    r"openrice\.com)",
    re.I,
)
BOOKING_RE = re.compile(r"inline\.app/booking|openrice\.com/.*/booking", re.I)
DIRECTORY_HOST_RE = re.compile(
    r"(ifoodie\.tw|openrice\.com|google\.(com|com\.tw)|maps\.app\.goo\.gl|"
    r"facebook\.com|instagram\.com|yelp\.|tripadvisor\.)",
    re.I,
)
URL_RE = re.compile(r"https?://[^\s|;,）)(\]（【]+", re.I)
PHONE_RE = re.compile(
    r"(?:\+?886[-\s]?)?"
    r"(?:"
    r"0?9\d{2}[-\s]?\d{3}[-\s]?\d{3}"  # mobile
    r"|\(?0?5\)?[-\s]?\d{3,4}[-\s]?\d{3,4}"  # Chiayi landline
    r"|\(?0?4\)?[-\s]?\d{3,4}[-\s]?\d{4}"  # Changhua / Taichung
    r"|\(?0?3\)?[-\s]?\d{3,4}[-\s]?\d{4}"  # Hsinchu / Taoyuan
    r"|\(?0?2\)?[-\s]?\d{3,4}[-\s]?\d{4}"  # Taipei
    r"|\(?0?6\)?[-\s]?\d{3,4}[-\s]?\d{3,4}"  # Tainan
    r"|\(?0?7\)?[-\s]?\d{3,4}[-\s]?\d{4}"  # Kaohsiung
    r"|\d{4}[-\s]?\d{4}"  # bare 8-digit local
    r")",
)
LINE_AT_RE = re.compile(r"(?:LINE\s*)?@([a-zA-Z0-9._-]{3,})", re.I)
ADDR_RE = re.compile(
    r"((?:嘉義[市縣])?[\u4e00-\u9fff]{0,8}(?:路|街|道|大道|巷|弄|段)[^\s;；|]{0,30}\d+[-\d]*號?(?:之\d+)?(?:\d+樓)?)"
)

LEAD_RE = re.compile(r"^(\d+)\.\s+\*\*(.+?)\*\*\s*\|\s*(.+)$", re.M)
# Culled leads may use ~~**Name**~~ **CULLED …** | …
CULLED_LEAD_RE = re.compile(
    r"^(\d+)\.\s+~~?\*\*(.+?)\*\*~~?\s+\*\*CULLED[^*]*\*\*\s*\|\s*(.+)$",
    re.M | re.I,
)
BATCH_HDR_RE = re.compile(r"^## Batch (\d+)\b", re.M)
SUFFIX_RE = re.compile(
    r"(house|restaurant|kitchen|cafe|café|diner|bistro|餐廳|小館|食堂|飯店|酒店)$",
    re.I,
)

DELIVERY_EVIDENCE_RE = re.compile(
    r"(外送|自送|會送|會自送|可以送|可送|才送|就送|就可以送|親送|配送|宅配|自營外送|電話外送|enableDelivery|"
    r"eligibleForDelivery|delivery|運費|免運|最低訂購|低消|運送距離|"
    r"即可外送|可外送|送餐|外帶外送|送到|送達|"
    r"(?:\d+|[一二三四五六七八九十兩]+)\s*(?:個|份|元|塊)?\s*(?:以上)?\s*(?:就送|才送|可送|就可以送|起送|送)|"
    r"(?:\d+|[一二三四五六七八九十兩]+)\s*個以上|"
    r"滿\s*(?:NT\$?|\$)?\s*\d+|最低\s*\*?\*?\s*\d+|EPD\s*名單|"
    r"Same\s+Oddle|Same\s+brand\s+storefront|品牌\s*Oddle|"
    r"公開運費|運費階梯|fee\s*ladder|跨區域|保溫配送|專屬.*配送|"
    r"minimumOrderCost|min(?:imum)?(?:\s*order)?(?:\s*cost)?\s*[:=]?\s*\d+|"
    r"el\s*=\s*true|enableDelivery\s*:\s*true|Minimum\s+order|"
    r"專人運送|merchant[\s-]*arranged|外燴)",
    re.I,
)
NO_DELIVERY_RE = re.compile(
    r"(enableDelivery\s*:\s*false|eligibleForDelivery\s*:\s*false|"
    r"空殼|empty\s*shell|無餐點|僅自取|只自取|僅外帶|pickup[\s-]*only|"
    r"booking[\s-]*only|el\s*=\s*false)",
    re.I,
)
PRIVATE_KITCHEN_RE = re.compile(r"私廚|私人廚房|預約制私廚")


def nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "")


def norm_name(s: str) -> str:
    s = nfkc(s).strip()
    s = re.sub(r"[（(][^）)]*[）)]", "", s)
    s = re.sub(r"\s+", "", s)
    s = SUFFIX_RE.sub("", s)
    return s.casefold()


def norm_url(u: str | None) -> str | None:
    if not u:
        return None
    u = u.strip().rstrip(").,;，。；]")
    u = re.split(r"[（(【]", u, maxsplit=1)[0]
    try:
        p = urlparse(u)
    except Exception:
        return u.rstrip("/").lower()
    host = (p.netloc or "").lower()
    path = (p.path or "").rstrip("/")
    path = re.sub(r"/(en_TW|zh_TW|zh_CN)(/stores)?$", "", path, flags=re.I)
    path = re.sub(r"/stores$", "", path, flags=re.I)
    q = ""
    if p.query:
        keep = []
        for part in p.query.split("&"):
            key = part.split("=", 1)[0].lower()
            if key in {"shop", "store", "id", "storeid", "companyid"}:
                keep.append(part)
        if keep:
            q = "&".join(keep)
    return urlunparse(
        ("https" if p.scheme.startswith("http") else p.scheme, host, path, "", q, "")
    ).lower()


def clean_url(u: str) -> str:
    return u.strip().rstrip(").,;，。；]")


def is_platform(u: str) -> bool:
    return bool(PLATFORM_HOST_RE.search(u))


def is_booking_only(u: str) -> bool:
    return bool(BOOKING_RE.search(u))


def is_directory(u: str) -> bool:
    return bool(DIRECTORY_HOST_RE.search(u))


def is_line_url(u: str) -> bool:
    host = urlparse(u).netloc.lower()
    return host in {"line.me", "page.line.me", "lin.ee"} or host.endswith(".line.me")


def normalize_city(city: str) -> str | None:
    c = nfkc(city).strip()
    if "嘉義市" in c:
        return "嘉義市"
    if "嘉義縣" in c:
        return "嘉義縣"
    return None


def pick_district(area: str, city: str) -> str:
    area_n = nfkc(area)
    multi_fallback = f"{city}多區" if city in ("嘉義市", "嘉義縣") else "嘉義市多區"
    keys = CITY_DISTRICT_KEYS.get(city, [])
    if re.search(r"多店|多門市|多區|multi|citywide|跨區|跨市縣", area_n, re.I):
        return multi_fallback
    # Prefer longer keys first (東區 before 東)
    found = [k for k in keys if k in area_n]
    if found:
        found.sort(key=len, reverse=True)
        return DISTRICT_CANON[found[0]]
    for tok in re.split(r"[・·/／、,，\s（）()→\-]+", area_n):
        tok = tok.strip()
        if not tok:
            continue
        if city == "嘉義市" and tok in CY_CITY_DISTRICT_CANON:
            return CY_CITY_DISTRICT_CANON[tok]
        if city == "嘉義縣" and tok in CY_COUNTY_DISTRICT_CANON:
            return CY_COUNTY_DISTRICT_CANON[tok]
    if area_n.strip() in {city, "嘉義"}:
        return multi_fallback
    if city == "嘉義市":
        return multi_fallback
    return multi_fallback


def cuisine_tags(cuisine: str) -> list[str]:
    cuisine = nfkc(cuisine).strip()
    if not cuisine or cuisine.upper() == "UNKNOWN":
        return []
    parts = re.split(r"[／/、,，|｜]+", cuisine)
    tags = [p.strip() for p in parts if p.strip()]
    return tags or [cuisine]


def channel_urls_and_phone(contact: str) -> tuple[list[str], list[str], str | None]:
    contact = nfkc(contact)
    urls = [clean_url(u) for u in URL_RE.findall(contact)]
    merchant_urls: list[str] = []
    line_urls: list[str] = []
    for u in urls:
        if is_platform(u) or is_booking_only(u) or is_directory(u):
            continue
        if is_line_url(u):
            line_urls.append(u)
        else:
            merchant_urls.append(u)
    for m in LINE_AT_RE.finditer(contact):
        lid = m.group(1)
        candidate = f"https://line.me/R/ti/p/@{lid}"
        if not any(lid.lower() in x.lower() for x in line_urls):
            line_urls.append(candidate)

    phones = PHONE_RE.findall(contact)
    phone = re.sub(r"[\s()]", "", phones[0]) if phones else None
    return merchant_urls, line_urls, phone


def pick_primary(merchant_urls: list[str], line_urls: list[str]) -> tuple[str | None, str | None]:
    def score(u: str) -> int:
        host = urlparse(u).netloc.lower()
        path = urlparse(u).path.lower()
        if "oddle.me" in host:
            return 100
        if "ichefpos.com" in host:
            return 95
        if "dudooeat.com" in host:
            return 90
        if "dinbendon" in host or "268web" in host:
            return 89
        if "iding.tw" in host or "idine" in host:
            return 88
        if "inline.app" in host and "/order" in path:
            return 87
        if "nidin.shop" in host or "ocard.co" in host:
            return 85
        if "imenu" in host:
            return 84
        if "bendon-dao" in host or "bendon.me" in host:
            return 83
        if "skm.com.tw" in host or "rsv.skm" in host:
            return 82
        if "kanorio.com" in host:
            return 75
        if is_line_url(u):
            return 80
        if re.search(r"order|訂[購餐]|delivery|外送|takeout|外帶|menu", u, re.I):
            return 70
        return 40

    ordered = sorted(merchant_urls, key=score, reverse=True)
    order = ordered[0] if ordered else (line_urls[0] if line_urls else None)
    line = line_urls[0] if line_urls else (order if order and is_line_url(order) else None)
    return order, line


def extract_address(notes: str) -> str | None:
    notes = nfkc(notes or "")
    notes = re.sub(r"\*\*Maps[^*]*\*\*", "", notes)
    m = ADDR_RE.search(notes)
    if not m:
        return None
    addr = m.group(1).strip().rstrip("；;，,")
    return addr if len(addr) >= 4 else None


def format_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    phone = re.sub(r"[\s()]", "", phone)
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("886"):
        digits = "0" + digits[3:]
    if len(digits) == 10 and digits.startswith("09"):
        return f"{digits[:4]}-{digits[4:7]}-{digits[7:]}"
    if len(digits) == 10 and digits.startswith("05"):
        return f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
    if len(digits) == 9 and digits.startswith("05"):
        # Chiayi 05 + 7-digit local
        return f"{digits[:2]}-{digits[2:]}"
    if len(digits) == 9 and digits.startswith("5"):
        digits = "0" + digits
        return f"{digits[:2]}-{digits[2:]}"
    if len(digits) == 8:
        return f"05-{digits}"
    if len(digits) == 10 and digits.startswith("04"):
        return f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
    if len(digits) == 10 and digits.startswith("03"):
        return f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
    if len(digits) == 10 and digits.startswith("02"):
        return f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
    if len(digits) == 10 and digits.startswith("06"):
        return f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
    if len(digits) == 10 and digits.startswith("07"):
        return f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
    return phone


def assign_batches(md: str) -> dict[int, int]:
    headers = [(m.start(), int(m.group(1))) for m in BATCH_HDR_RE.finditer(md)]
    out: dict[int, int] = {}
    for m in list(LEAD_RE.finditer(md)) + list(CULLED_LEAD_RE.finditer(md)):
        num = int(m.group(1))
        pos = m.start()
        batch = 1
        for hpos, b in headers:
            if hpos < pos:
                batch = b
            else:
                break
        out[num] = batch
    return out


def has_delivery_evidence(lead: dict) -> bool:
    blob = " ".join(
        [
            lead.get("evidence") or "",
            lead.get("notes_raw") or "",
            lead.get("contact_raw") or "",
        ]
    )
    if NO_DELIVERY_RE.search(blob):
        return False
    if not DELIVERY_EVIDENCE_RE.search(blob):
        return False
    if PRIVATE_KITCHEN_RE.search(blob):
        ou = lead.get("orderUrl") or ""
        host = urlparse(ou).netloc.lower() if ou else ""
        realtime = any(
            x in host
            for x in (
                "oddle.me", "ichefpos.com", "dudooeat.com", "ocard.co",
                "nidin.shop", "inline.app", "imenu", "iding.tw",
            )
        ) or (ou and "/order" in ou.lower())
        if not realtime:
            return False
    ou = lead.get("orderUrl") or ""
    if "oddle.me" in ou.lower():
        if re.search(r"enableDelivery\s*:\s*false|eligibleForDelivery\s*:\s*false|空殼|empty|el\s*=\s*false", blob, re.I):
            return False
    return True


def _parse_one(num: int, name: str, rest: str, batch_of: dict[int, int], force_culled: bool = False) -> dict | None:
    name_clean = re.sub(r"~~.*?~~", "", name).strip()
    name_clean = re.sub(r"\s+", " ", name_clean)
    parts = [p.strip() for p in rest.split("|")]
    if len(parts) == 9:
        city_raw, area, cuisine, evidence, contact, hours, notes, source, confidence = parts
    elif len(parts) == 8:
        city_raw = "嘉義市"
        area, cuisine, evidence, contact, hours, notes, source, confidence = parts
    else:
        return None
    city = normalize_city(city_raw)
    if not city:
        return None
    confidence = re.sub(r"\*+", "", confidence).strip()
    conf_l = confidence.lower()
    if force_culled or "culled" in conf_l or "culled" in name.lower() or "歇業" in confidence:
        confidence = "culled"
    elif conf_l.startswith("high"):
        confidence = "high"
    elif conf_l.startswith("medium"):
        confidence = "medium"
    elif conf_l.startswith("low"):
        confidence = "low"

    district = pick_district(area, city)
    merchant_urls, line_urls, phone = channel_urls_and_phone(contact)
    blob_ch = contact + " " + notes + " " + " ".join(merchant_urls)
    shop_ids = set(re.findall(r"dinbendon(?:\.net/do/idine\?shop=|\s+shop\s*=\s*)(\d+)", blob_ch, flags=re.I))
    shop_ids.update(re.findall(r"dinbendon\.net/do/shop/(\d+)", blob_ch, flags=re.I))
    merchant_urls = [u for u in merchant_urls if "dinbendon.net/do/idine" not in u.lower()]
    for sid in sorted(shop_ids):
        u = f"https://www.dinbendon.net/do/shop/{sid}"
        if u not in merchant_urls:
            merchant_urls.append(u)
    if not phone:
        ph2 = PHONE_RE.findall(nfkc(notes + " " + contact))
        if ph2:
            phone = format_phone(ph2[0])
        else:
            phone = None
    else:
        phone = format_phone(phone)
    order_url, line_url = pick_primary(merchant_urls, line_urls)
    all_urls = list(dict.fromkeys(merchant_urls + line_urls))

    hours_clean = None if not hours or hours.upper() == "UNKNOWN" or hours == "—" else hours.strip()
    return {
        "num": num,
        "batch": batch_of.get(num, 1),
        "name": name_clean or name,
        "city": city,
        "district": district,
        "area_raw": area,
        "cuisine": cuisine.strip(),
        "cuisineTags": cuisine_tags(cuisine),
        "evidence": evidence.strip(),
        "notes_raw": notes,
        "contact_raw": contact,
        "orderUrl": order_url,
        "lineUrl": line_url,
        "allUrls": all_urls,
        "phone": phone,
        "hours": hours_clean,
        "address": extract_address(notes),
        "source": source.strip(),
        "confidence": confidence,
    }


def parse_leads(md: str) -> list[dict]:
    batch_of = assign_batches(md)
    leads = []
    seen_nums: set[int] = set()
    for m in LEAD_RE.finditer(md):
        num = int(m.group(1))
        lead = _parse_one(num, m.group(2).strip(), m.group(3), batch_of)
        if lead:
            leads.append(lead)
            seen_nums.add(num)
    for m in CULLED_LEAD_RE.finditer(md):
        num = int(m.group(1))
        if num in seen_nums:
            continue
        lead = _parse_one(num, m.group(2).strip(), m.group(3), batch_of, force_culled=True)
        if lead:
            leads.append(lead)
            seen_nums.add(num)
    leads.sort(key=lambda x: x["num"])
    return leads


def make_id(num: int, existing_ids: set[str]) -> str:
    for cand in (f"{ID_PREFIX}-{num}", f"cy-scout-corpus-{num}", f"cy-lead-{num}-{TODAY.replace('-', '')}"):
        if cand not in existing_ids:
            return cand
    return f"cy-lead-{num}-{TODAY.replace('-', '')}-x"


def lead_to_record(lead: dict, rid: str) -> dict:
    slug = re.sub(r"\s+", "", lead["name"])
    slug = re.sub(r"[（(].*?[）)]", "", slug)[:40] or lead["name"][:40]
    rec: dict = {
        "id": rid,
        "slug": slug,
        "name": lead["name"],
        "city": lead["city"],
        "district": lead["district"],
        "cuisine": lead["cuisine"],
        "cuisineTags": lead["cuisineTags"],
        "chain": False,
        "featured": False,
        "origin": "scout",
        "confidence": lead["confidence"],
        "checkedAt": TODAY,
        "deliveryMinType": None,
        "deliveryMinValue": None,
        "deliveryMinLabel": None,
        "freeDeliveryThreshold": None,
        "deliveryFee": None,
    }
    if lead.get("hours"):
        rec["hours"] = lead["hours"]
    if lead.get("evidence"):
        rec["evidence"] = lead["evidence"]
    if lead.get("source"):
        rec["source"] = lead["source"]
    if lead.get("orderUrl"):
        rec["orderUrl"] = lead["orderUrl"]
    if lead.get("lineUrl"):
        rec["lineUrl"] = lead["lineUrl"]
        if not rec.get("orderUrl"):
            rec["orderUrl"] = lead["lineUrl"]
    if lead.get("phone"):
        rec["phone"] = lead["phone"]
    if lead.get("address"):
        rec["address"] = lead["address"]

    probe = {
        "terms": lead.get("evidence") or "",
        "range": lead.get("notes_raw") or "",
        "hours": lead.get("hours") or "",
        "evidence": lead.get("evidence") or "",
        "freeDeliveryThreshold": None,
    }
    fields = infer_delivery_min(probe)
    rec["deliveryMinType"] = fields["deliveryMinType"]
    rec["deliveryMinValue"] = fields["deliveryMinValue"]
    rec["deliveryMinLabel"] = fields["deliveryMinLabel"]
    return rec


def has_merchant_channel(lead: dict) -> bool:
    return bool(lead.get("orderUrl") or lead.get("lineUrl") or lead.get("phone") or lead.get("allUrls"))


def primary_is_platform(lead: dict) -> bool:
    contact = lead.get("contact_raw") or ""
    urls = [clean_url(u) for u in URL_RE.findall(contact)]
    if not urls:
        return False
    non_platform = [u for u in urls if not is_platform(u) and not is_directory(u) and not is_booking_only(u)]
    if non_platform:
        return False
    if lead.get("phone") or lead.get("lineUrl"):
        return False
    return True


def merge_into(root: Path, md: str) -> dict:
    existing = json.loads((root / "restaurants.json").read_text(encoding="utf-8"))
    before = len(existing)

    existing_ids = {r["id"] for r in existing}
    name_district: set[tuple[str, str]] = set()
    names_any: dict[str, set[str]] = {}
    order_urls: set[str] = set()
    brand_hosts: set[str] = set()
    _MULTI = (
        "oddle.me", "ichefpos.com", "dudooeat.com", "inline.app",
        "nidin.shop", "ocard.co", "line.me", "lin.ee", "quickclick.cc",
        "myship.7-11.com.tw", "dinbendon.net", "dinbendon.com",
        "268web.com.tw", "imenu.com.tw", "iding.tw",
        "reurl.cc", "reurl.com", "bit.ly", "tinyurl.com", "pse.is",
        "lihi1.com", "lihi.io", "ppt.cc", "portaly.cc",
        "bendon-dao.com", "bendon.me", "foodomo.com", "quickorder.tw",
        "order.place", "o.easystore.co", "web66.tw", "kanorio.com",
        "buygood.com.tw", "skm.com.tw", "rink.cc", "linktr.ee",
    )

    def _brand_host(u: str | None) -> str | None:
        if not u:
            return None
        try:
            h = urlparse(u).netloc.lower()
        except Exception:
            return None
        if h.startswith("www."):
            h = h[4:]
        if any(h == s or h.endswith("." + s) for s in _MULTI):
            return None
        return h

    for r in existing:
        nn = norm_name(r.get("name") or "")
        dist = r.get("district") or ""
        name_district.add((nn, dist))
        names_any.setdefault(nn, set()).add(dist)
        for key in ("orderUrl", "lineUrl"):
            nu = norm_url(r.get(key))
            if nu:
                order_urls.add(nu)
            bh = _brand_host(r.get(key))
            if bh:
                brand_hosts.add(bh)

    leads = parse_leads(md)
    skip_reasons: Counter[str] = Counter()
    skipped_sample: list[dict] = []
    added: list[dict] = []

    def note_skip(lead: dict, reason: str) -> None:
        skip_reasons[reason] += 1
        if len(skipped_sample) < 80:
            skipped_sample.append({
                "num": lead["num"],
                "name": lead["name"],
                "city": lead.get("city"),
                "reason": reason,
            })

    for lead in leads:
        if lead.get("confidence") == "culled":
            note_skip(lead, "culled")
            continue
        if primary_is_platform(lead):
            note_skip(lead, "ue_fp_primary")
            continue
        if not has_merchant_channel(lead):
            note_skip(lead, "no_channel")
            continue
        if not has_delivery_evidence(lead):
            note_skip(lead, "no_delivery_evidence")
            continue

        nn = norm_name(lead["name"])
        dist = lead["district"]

        if (nn, dist) in name_district:
            note_skip(lead, "dup_name_district")
            continue

        if nn in names_any:
            existing_dists = names_any[nn]
            multi_markers = {
                "桃園多區", "台中多區", "新北多區", "台北多區", "高雄多區",
                "台南多區", "新竹市多區", "新竹縣多區", "彰化市多區", "彰化縣多區",
                "嘉義市多區", "嘉義縣多區",
            }
            if dist in multi_markers or (existing_dists & multi_markers):
                note_skip(lead, "dup_name_district")
                continue
            area = lead.get("area_raw") or ""
            overlap = False
            for ed in existing_dists:
                short = DISTRICT_SHORT.get(ed, re.sub(r"[區市鎮鄉]$", "", ed))
                if short and short in area and len(short) >= 2:
                    overlap = True
                    break
            if overlap:
                note_skip(lead, "dup_name_district")
                continue

        lead_norms = [norm_url(u) for u in lead.get("allUrls") or []]
        lead_norms = [u for u in lead_norms if u]
        if any(u in order_urls for u in lead_norms):
            note_skip(lead, "dup_order_url")
            continue

        lead_hosts = {_brand_host(u) for u in (lead.get("allUrls") or [])}
        lead_hosts.discard(None)
        if lead_hosts & brand_hosts:
            note_skip(lead, "dup_order_url")
            continue

        rid = make_id(lead["num"], existing_ids)
        rec = lead_to_record(lead, rid)
        added.append(rec)
        existing_ids.add(rid)
        name_district.add((nn, dist))
        names_any.setdefault(nn, set()).add(dist)
        for u in lead_norms:
            order_urls.add(u)
        for u in lead.get("allUrls") or []:
            bh = _brand_host(u)
            if bh:
                brand_hosts.add(bh)

    merged = existing + added
    (root / "restaurants.json").write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (root / "data.js").write_text(
        "window.RESTAURANTS = " + json.dumps(merged, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )

    by_dist = Counter(r["district"] for r in added)
    by_city = Counter(r["city"] for r in added)
    labeled = sum(1 for r in added if r.get("deliveryMinLabel"))
    report = {
        "before": before,
        "after": len(merged),
        "added": len(added),
        "leads_parsed": len(leads),
        "skipped": sum(skip_reasons.values()),
        "skip_reasons": dict(skip_reasons),
        "added_by_city": dict(by_city.most_common()),
        "added_by_district": dict(by_dist.most_common()),
        "added_with_deliveryMinLabel": labeled,
        "sample_new": [
            {
                "id": r["id"],
                "name": r["name"],
                "city": r.get("city"),
                "district": r["district"],
                "orderUrl": r.get("orderUrl"),
                "phone": r.get("phone"),
                "deliveryMinLabel": r.get("deliveryMinLabel"),
            }
            for r in added[:8]
        ],
        "added_ids": [r["id"] for r in added],
        "added_names": [r["name"] for r in added],
        "skipped_sample": skipped_sample,
        "policy": (
            "KEEP all existing cities. Merchant channels only (own web / Oddle / LINE / phone / "
            "iCHEF / dudoo / Ocard / dinbendon / 268web / imenu / iding / inline.app/order / SKM). Require "
            "delivery evidence. Exclude UE/FP-primary, booking-only, empty Oddle, private kitchen "
            "without realtime order, culled/closed. Dedupe name+district and channel URLs/brand "
            "hosts. city=嘉義市 OR 嘉義縣 (separate); IDs: cy-scout-lead-{n}. Phones include 05-."
        ),
        "checkedAt": TODAY,
        "corpus": str(CORPUS),
        "root": str(root),
    }
    return report


def main() -> None:
    roots = [ROOT]
    if len(sys.argv) > 1:
        roots = [Path(p) for p in sys.argv[1:]]
    md = CORPUS.read_text(encoding="utf-8")
    for root in roots:
        report = merge_into(root, md)
        out = root / "chiayi-leads-merge-report.json"
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "root": str(root),
                    **{k: report[k] for k in (
                        "before", "after", "added", "leads_parsed", "skipped",
                        "skip_reasons", "sample_new", "added_with_deliveryMinLabel",
                        "added_by_city", "added_by_district",
                    )},
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
