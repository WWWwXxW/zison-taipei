#!/usr/bin/env python3
"""Merge Kaohsiung Scout corpus into restaurants.json. Merchant channels only; dedupe name+district & order URL."""
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
CORPUS = Path("/workspace/kaohsiung-own-delivery-leads.md")
TODAY = date.today().isoformat()
ID_PREFIX = "kh-scout-lead"

_bf_path = Path(__file__).resolve().parent / "backfill-delivery-min.py"
_spec = importlib.util.spec_from_file_location("backfill_delivery_min", _bf_path)
_bf = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_bf)
infer_delivery_min = _bf.infer

# Scout QA: #84 = #34 樂咖中華 duplicate; #15 ≪ #64 寶町 same address — keep one each
SKIP_LEAD_NUMS = {84}  # exact duplicate of #34
SUPERSEDED_LEAD_NUMS = {15}  # superseded by #64 寶町

DISTRICT_CANON = {
    "三民": "三民區", "三民區": "三民區",
    "鳳山": "鳳山區", "鳳山區": "鳳山區",
    "左營": "左營區", "左營區": "左營區",
    "苓雅": "苓雅區", "苓雅區": "苓雅區",
    "新興": "新興區", "新興區": "新興區",
    "楠梓": "楠梓區", "楠梓區": "楠梓區",
    "前鎮": "前鎮區", "前鎮區": "前鎮區",
    "鼓山": "鼓山區", "鼓山區": "鼓山區",
    "小港": "小港區", "小港區": "小港區",
    "仁武": "仁武區", "仁武區": "仁武區",
    "前金": "前金區", "前金區": "前金區",
    "鹽埕": "鹽埕區", "鹽埕區": "鹽埕區",
    "岡山": "岡山區", "岡山區": "岡山區",
    "路竹": "路竹區", "路竹區": "路竹區",
    "大社": "大社區", "大社區": "大社區",
    "彌陀": "彌陀區", "彌陀區": "彌陀區",
    "旗山": "旗山區", "旗山區": "旗山區",
    "旗津": "旗津區", "旗津區": "旗津區",
    "鳥松": "鳥松區", "鳥松區": "鳥松區",
    "林園": "林園區", "林園區": "林園區",
    "湖內": "湖內區", "湖內區": "湖內區",
    "茄萣": "茄萣區", "茄萣區": "茄萣區",
    "橋頭": "橋頭區", "橋頭區": "橋頭區",
    "燕巢": "燕巢區", "燕巢區": "燕巢區",
    "梓官": "梓官區", "梓官區": "梓官區",
    "大寮": "大寮區", "大寮區": "大寮區",
    "大樹": "大樹區", "大樹區": "大樹區",
    "美濃": "美濃區", "美濃區": "美濃區",
    "阿蓮": "阿蓮區", "阿蓮區": "阿蓮區",
    "田寮": "田寮區", "田寮區": "田寮區",
    "永安": "永安區", "永安區": "永安區",
    "梓官": "梓官區",
    "那瑪夏": "那瑪夏區", "那瑪夏區": "那瑪夏區",
    "甲仙": "甲仙區", "甲仙區": "甲仙區",
    "六龜": "六龜區", "六龜區": "六龜區",
    "杉林": "杉林區", "杉林區": "杉林區",
    "內門": "內門區", "內門區": "內門區",
    "茂林": "茂林區", "茂林區": "茂林區",
    "桃源": "桃源區", "桃源區": "桃源區",
    "高雄多區": "高雄多區",
}
DISTRICT_SHORT = {v: k for k, v in DISTRICT_CANON.items() if not k.endswith("區") and k != "高雄多區"}

KH_DISTRICT_KEYS = [
    "那瑪夏", "茄萣", "橋頭", "燕巢", "梓官", "湖內", "大寮", "大樹", "美濃", "阿蓮",
    "田寮", "永安", "甲仙", "六龜", "杉林", "內門", "茂林", "桃源",
    "三民", "鳳山", "左營", "苓雅", "新興", "楠梓", "前鎮", "鼓山", "小港", "仁武",
    "前金", "鹽埕", "岡山", "路竹", "大社", "彌陀", "旗山", "旗津", "鳥松", "林園",
]

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
    r"|\(?0?7\)?[-\s]?\d{3,4}[-\s]?\d{4}"  # Kaohsiung landline
    r"|\(?0?4\)?[-\s]?\d{3,4}[-\s]?\d{4}"  # Taichung
    r"|\(?0?2\)?[-\s]?\d{3,4}[-\s]?\d{4}"  # Taipei
    r"|\d{4}[-\s]?\d{4}"  # bare 8-digit local
    r")",
)
LINE_AT_RE = re.compile(r"(?:LINE\s*)?@([a-zA-Z0-9._-]{3,})", re.I)
ADDR_RE = re.compile(
    r"((?:高雄市)?[\u4e00-\u9fff]{0,6}(?:路|街|道|大道|巷|弄|段)[^\s;；|]{0,30}\d+[-\d]*號?(?:之\d+)?(?:\d+樓)?)"
)

LEAD_RE = re.compile(r"^(\d+)\.\s+\*\*(.+?)\*\*[^\n|]*\|\s*(.+)$", re.M)
BATCH_HDR_RE = re.compile(r"^## Batch (\d+)\b", re.M)
SUFFIX_RE = re.compile(
    r"(house|restaurant|kitchen|cafe|café|diner|bistro|餐廳|小館|食堂|飯店|酒店)$",
    re.I,
)

DELIVERY_EVIDENCE_RE = re.compile(
    r"(外送|會送|會自送|可送|才送|就送|就可以送|配送|宅配|自營外送|電話外送|enableDelivery|"
    r"eligibleForDelivery|delivery|運費|免運|最低訂購|低消|運送距離|"
    r"即可外送|可外送|送餐|外帶外送|送到|送達|"
    r"(?:\d+|[一二三四五六七八九十兩]+)\s*(?:個|份)?\s*(?:以上)?\s*(?:就送|才送|可送|就可以送|起送|送)|"
    r"(?:\d+|[一二三四五六七八九十兩]+)\s*個以上|"
    r"滿\s*(?:NT\$?|\$)?\s*\d+|最低\s*\*?\*?\s*\d+|EPD\s*名單|"
    r"Same\s+Oddle|Same\s+brand\s+storefront|品牌\s*Oddle|"
    r"公開運費|運費階梯|fee\s*ladder|跨區域|"
    r"專人運送|merchant[\s-]*arranged|Minimum\s+order)",
    re.I,
)
NO_DELIVERY_RE = re.compile(
    r"(enableDelivery\s*:\s*false|eligibleForDelivery\s*:\s*false|"
    r"空殼|empty\s*shell|無餐點|僅自取|只自取|僅外帶|"
    r"(?<![非不])pickup[\s-]*only|"
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



def is_store_specific_url(u: str) -> bool:
    """True for per-store storefronts; False for shared brand FAQ/marketing pages."""
    try:
        p = urlparse(u)
    except Exception:
        return False
    host = (p.netloc or "").lower()
    path = (p.path or "").lower()
    q = (p.query or "").lower()
    if is_line_url(u):
        return False
    if "dinbendon" in host and ("shop=" in q or "/shop/" in path or "shop=" in path):
        return True
    if "bendon-dao" in host and "/shops/" in path:
        return True
    if "ichefpos.com" in host and "/store/" in path:
        return True
    if "oddle.me" in host:
        return True
    if "ocard.co" in host and path.count("/") >= 2:
        return True
    if "dudooeat.com" in host or "imenu" in host:
        return True
    if "inline.app" in host and "/order" in path:
        return True
    if "nidin.shop" in host:
        return True
    if re.search(r"/do/shop/\d+", path):
        return True
    return False

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


def pick_district(area: str) -> str:
    area_n = nfkc(area)
    if re.search(r"多店|多門市|多區|multi|citywide|高雄市區|會議餐盒", area_n, re.I):
        return "高雄多區"
    found = []
    for key in KH_DISTRICT_KEYS:
        if key in area_n:
            found.append(key)
    if len(found) == 1:
        return DISTRICT_CANON[found[0]]
    if len(found) > 1:
        found.sort(key=len, reverse=True)
        return DISTRICT_CANON[found[0]]
    if area_n.strip() in {"高雄市", "高雄", "高市"}:
        return "高雄多區"
    for tok in re.split(r"[・·/／、,，\s（）()→\-]+", area_n):
        tok = tok.strip()
        if tok in DISTRICT_CANON:
            return DISTRICT_CANON[tok]
    return "高雄多區"


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
        if "bendon-dao" in host or "bendon.me" in host:
            return 88
        if "inline.app" in host and "/order" in path:
            return 87
        if "nidin.shop" in host or "ocard.co" in host:
            return 85
        if "imenu" in host:
            return 84
        if is_line_url(u):
            return 80
        if re.search(r"order|訂[購餐]|delivery|外送|takeout|外帶", u, re.I):
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


def norm_address(addr: str | None) -> str | None:
    if not addr:
        return None
    a = nfkc(addr)
    a = re.sub(r"^高雄市", "", a)
    a = re.sub(r"[\s\-－—]", "", a)
    a = re.sub(r"[之]", "-", a)
    return a.casefold() if len(a) >= 4 else None


def format_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    phone = re.sub(r"[\s()]", "", phone)
    digits = re.sub(r"\D", "", phone)
    if digits.startswith("886"):
        digits = "0" + digits[3:]
    if len(digits) == 10 and digits.startswith("09"):
        return f"{digits[:4]}-{digits[4:7]}-{digits[7:]}"
    if len(digits) == 10 and digits.startswith("07"):
        return f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
    if len(digits) == 9 and digits.startswith("7"):
        digits = "0" + digits
        return f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
    if len(digits) == 8:
        return f"07-{digits[:4]}-{digits[4:]}"
    if len(digits) == 10 and digits.startswith("04"):
        return f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
    if len(digits) == 10 and digits.startswith("02"):
        return f"{digits[:2]}-{digits[2:6]}-{digits[6:]}"
    return phone


def assign_batches(md: str) -> dict[int, int]:
    headers = [(m.start(), int(m.group(1))) for m in BATCH_HDR_RE.finditer(md)]
    out: dict[int, int] = {}
    for m in LEAD_RE.finditer(md):
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
    for m in NO_DELIVERY_RE.finditer(blob):
        prefix = blob[max(0, m.start() - 4) : m.start()]
        # Ignore negated phrases like 「非 pickup-only」
        if any(x in prefix for x in ("非", "不", "not", "No ", "no ")):
            continue
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
                "nidin.shop", "inline.app", "imenu",
            )
        ) or (ou and "/order" in ou.lower())
        if not realtime:
            return False
    ou = lead.get("orderUrl") or ""
    if "oddle.me" in ou.lower():
        if re.search(r"enableDelivery\s*:\s*false|eligibleForDelivery\s*:\s*false|空殼|empty|el\s*=\s*false", blob, re.I):
            return False
    return True


def parse_leads(md: str) -> list[dict]:
    batch_of = assign_batches(md)
    leads = []
    for m in LEAD_RE.finditer(md):
        num = int(m.group(1))
        name = m.group(2).strip()
        name_clean = re.sub(r"~~.*?~~", "", name).strip()
        name_clean = re.sub(r"\s+", " ", name_clean)
        parts = [p.strip() for p in m.group(3).split("|")]
        if len(parts) == 9:
            city, area, cuisine, evidence, contact, hours, notes, source, confidence = parts
        elif len(parts) == 8:
            city = "高雄市"
            area, cuisine, evidence, contact, hours, notes, source, confidence = parts
        else:
            continue
        if city and ("台北" in city or "新北" in city or "台中" in city or "臺中" in city) and "高雄" not in city:
            continue
        confidence = re.sub(r"\*+", "", confidence).strip()
        conf_l = confidence.lower()
        if "culled" in conf_l or "culled" in name.lower() or "歇業" in confidence:
            confidence = "culled"
        elif conf_l.startswith("high"):
            confidence = "high"
        elif conf_l.startswith("medium"):
            confidence = "medium"
        elif conf_l.startswith("low"):
            confidence = "low"

        district = pick_district(area)
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
            phone = format_phone(phone)
        order_url, line_url = pick_primary(merchant_urls, line_urls)
        all_urls = list(dict.fromkeys(merchant_urls + line_urls))

        hours_clean = None if not hours or hours.upper() == "UNKNOWN" or hours == "—" else hours.strip()
        leads.append(
            {
                "num": num,
                "batch": batch_of.get(num, 1),
                "name": name_clean or name,
                "city": "高雄市",
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
        )
    return leads


def make_id(num: int, existing_ids: set[str]) -> str:
    for cand in (f"{ID_PREFIX}-{num}", f"kh-scout-corpus-{num}", f"kh-lead-{num}-{TODAY.replace('-', '')}"):
        if cand not in existing_ids:
            return cand
    return f"kh-lead-{num}-{TODAY.replace('-', '')}-x"


def lead_to_record(lead: dict, rid: str) -> dict:
    slug = re.sub(r"\s+", "", lead["name"])
    slug = re.sub(r"[（(].*?[）)]", "", slug)[:40] or lead["name"][:40]
    rec: dict = {
        "id": rid,
        "slug": slug,
        "name": lead["name"],
        "city": "高雄市",
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
    addr_district: set[tuple[str, str]] = set()

    for r in existing:
        nn = norm_name(r.get("name") or "")
        dist = r.get("district") or ""
        name_district.add((nn, dist))
        names_any.setdefault(nn, set()).add(dist)
        for key in ("orderUrl", "lineUrl"):
            nu = norm_url(r.get(key))
            if nu:
                order_urls.add(nu)
        na = norm_address(r.get("address"))
        if na and dist:
            addr_district.add((na, dist))

    leads = parse_leads(md)
    skip_reasons: Counter[str] = Counter()
    skipped_sample: list[dict] = []
    added: list[dict] = []

    def note_skip(lead: dict, reason: str) -> None:
        skip_reasons[reason] += 1
        if len(skipped_sample) < 80:
            skipped_sample.append({"num": lead["num"], "name": lead["name"], "reason": reason})

    for lead in leads:
        if lead["num"] in SKIP_LEAD_NUMS:
            note_skip(lead, "scout_dup_84_eq_34")
            continue
        if lead["num"] in SUPERSEDED_LEAD_NUMS:
            note_skip(lead, "scout_superseded_15_by_64")
            continue
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
            if dist == "高雄多區" or "高雄多區" in existing_dists or "台中多區" in existing_dists or "新北多區" in existing_dists or "台北多區" in existing_dists:
                note_skip(lead, "dup_name_district")
                continue
            area = lead.get("area_raw") or ""
            overlap = False
            for ed in existing_dists:
                short = DISTRICT_SHORT.get(ed, ed.replace("區", ""))
                if short and short in area and len(short) >= 2:
                    overlap = True
                    break
            if overlap:
                note_skip(lead, "dup_name_district")
                continue

        # Dedupe store-specific storefront URLs only — shared brand LINE /
        # marketing FAQ pages must not collapse distinct branches.
        lead_norms = []
        for u in lead.get("allUrls") or []:
            if not is_store_specific_url(u):
                continue
            nu = norm_url(u)
            if nu:
                lead_norms.append(nu)
        if any(u in order_urls for u in lead_norms):
            note_skip(lead, "dup_order_url")
            continue

        # Same-address same-district collision (e.g. #15/#64) — keep first kept lead
        na = norm_address(lead.get("address"))
        if na and (na, dist) in addr_district:
            note_skip(lead, "dup_address_district")
            continue

        rid = make_id(lead["num"], existing_ids)
        rec = lead_to_record(lead, rid)
        added.append(rec)
        existing_ids.add(rid)
        name_district.add((nn, dist))
        names_any.setdefault(nn, set()).add(dist)
        for u in lead_norms:
            order_urls.add(u)
        if na:
            addr_district.add((na, dist))

    merged = existing + added
    (root / "restaurants.json").write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (root / "data.js").write_text(
        "window.RESTAURANTS = " + json.dumps(merged, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )

    by_dist = Counter(r["district"] for r in added)
    labeled = sum(1 for r in added if r.get("deliveryMinLabel"))
    report = {
        "before": before,
        "after": len(merged),
        "added": len(added),
        "leads_parsed": len(leads),
        "skipped": sum(skip_reasons.values()),
        "skip_reasons": dict(skip_reasons),
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
            for r in added[:5]
        ],
        "added_ids": [r["id"] for r in added],
        "added_names": [r["name"] for r in added],
        "skipped_sample": skipped_sample,
        "scout_qa": {
            "skip_84_eq_34": "樂咖低卡餐盒 中華店 — keep #34 only",
            "skip_15_superseded_by_64": "珍好佳 ≪ 寶町 義華路32號 — keep #64 only",
        },
        "policy": (
            "KEEP Taipei+New Taipei+Taichung. Merchant channels only (own web / Oddle / LINE / phone / "
            "iCHEF / dudoo / Ocard / dinbendon / bendon-dao / 268web / imenu / inline.app/order). Require "
            "delivery evidence. Exclude UE/FP-primary, booking-only, empty Oddle, private kitchen "
            "without realtime order, culled/closed. Dedupe name+district, channel URLs, and "
            "address+district. Scout QA: #84=#34 skip; #15≪#64 skip #15. city=高雄市; districts with 區. "
            "IDs: kh-scout-lead-{n}."
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
        out = root / "kaohsiung-leads-merge-report.json"
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(
            json.dumps(
                {
                    "root": str(root),
                    **{k: report[k] for k in (
                        "before", "after", "added", "leads_parsed", "skipped",
                        "skip_reasons", "sample_new", "added_with_deliveryMinLabel",
                        "added_by_district", "scout_qa",
                    )},
                },
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
