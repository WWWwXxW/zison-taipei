# -*- coding: utf-8 -*-
"""Backfill deliveryMinType / deliveryMinValue / deliveryMinLabel from existing fields."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

NUM = r'(?:\d{1,3}(?:,\d{3})+|\d+)'


def parse_num(s: str) -> int:
    return int(str(s).replace(',', '').strip())


def text_blob(r: dict) -> str:
    return '\n'.join(str(r.get(k) or '') for k in ('terms', 'range', 'hours', 'evidence'))


def extract_quantity(blob: str):
    m = re.search(r'滿\s*(\d+)\s*(個|份)', blob)
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2)
    return {
        'deliveryMinType': 'quantity',
        'deliveryMinValue': n,
        'deliveryMinLabel': f'滿 {n} {unit}',
    }


def clause_after(blob: str, end: int) -> str:
    """Text from end until next strong punctuation."""
    stop = len(blob)
    for i in range(end, min(len(blob), end + 120)):
        if blob[i] in '。；;\n':
            stop = i
            break
    return blob[end:stop]


def reject_amount(blob: str, start: int, end: int, *, man_pattern: bool = False) -> bool:
    before = blob[max(0, start - 28): start]
    after = blob[end: min(len(blob), end + 16)]
    window = blob[max(0, start - 56): min(len(blob), end + 56)]
    clause = clause_after(blob, end)
    matched = blob[start:end]

    if re.search(r'(運費|外送費|物流|處理費|宅配費|服務費)\s*(?:為|：|:)?\s*(?:NT\$|\$|NT)?\s*$', before):
        return True
    if re.search(r'^(?:元)?\s*(?:運費|外送費|服務費)', after):
        return True
    if re.search(r'^(?:元)?\s*(?:折|九折|八五折|八折|七折)', after):
        return True
    # Immediate 免運 after the number => free-delivery threshold, not low消
    if re.search(r'^(?:元)?\s*(?:免運|免外送費)', after):
        return True
    # For 滿-based matches, 免運 later in the same clause => free-delivery tier list
    if man_pattern and re.search(r'免運|免外送費', clause):
        return True
    if re.search(r'為\s*(?:NT\$|\$|NT)?\s*\d', after):  # 滿NT$700為NT$40 fee discount
        return True
    if re.search(r'促銷|折扣門檻|不等於起送|不加收|可提前|預約', window):
        return True
    if re.search(r'^(?:元)?\s*(?:可提前|預約)', after):
        return True
    # Global signals: no order minimum / free-delivery-only tiers
    if re.search(r'不限金額|低消未知|未公布外送低消|未公布.{0,4}低消|低消未公開|一般低消未公開', blob):
        if not re.search(r'(?:通常)?低消|最低(?:訂購|消費)', matched):
            return True
    if re.search(r'(最低訂購金額|最低消費|低消).{0,6}(未公開|未知|UNKNOWN)', window):
        if not re.search(r'(?:通常)?低消|最低(?:訂購|消費)', matched):
            return True
        if re.search(r'(未公開|未知|UNKNOWN)', matched):
            return True
    return False


def extract_amount_min(blob: str):
    candidates = []

    patterns = [
        rf'(?:通常)?低消\s*(?:為|：|:)?\s*(?:NT\$|\$|NT)?\s*({NUM})',
        rf'最低(?:訂購|消費)(?:金額)?\s*(?:為|：|:)?\s*(?:NT\$|\$)?\s*({NUM})',
        rf'外送最低訂購\s*(?:NT\$|\$)?\s*({NUM})',
        rf'最低\s*(?:NT\$|\$)\s*({NUM})',
        rf'(?<!未)滿\s*(?:NT\$|\$)?\s*({NUM})\s*(?:元)?\s*(?:即可外送|可外送|可送)',
        rf'(?:公里|km)[^\n；]{{0,8}}最低(?:消費|訂購)?(?:金額)?\s*(?:NT\$|\$)?\s*({NUM})',
        rf'(?:[\d.]+)\s*(?:至|–|-|~)\s*(?:[\d.]+)\s*公里內?\s*(?:滿|最低(?:消費|訂購)?)\s*(?:NT\$|\$|NT)?\s*({NUM})',
        # bare band amounts only when written as 公里NT$N (烏弄-style mins); 運費 filtered in reject
        rf'(?:[\d.]+)\s*(?:至|–|-|~)\s*(?:[\d.]+)\s*公里內?\s*(?:NT\$|\$)\s*({NUM})',
        rf'低消\s*({NUM})\s*[／/]',
        rf'(?:[\d.]+)\s*公里內\s*最低(?:訂購|消費)?(?:金額)?\s*(?:NT\$|\$)?\s*({NUM})',
        rf'(?:[\d.]+)\s*公里內\s*(?:滿|最低)\s*(?:NT\$|\$)\s*({NUM})',
    ]

    for pat in patterns:
        for m in re.finditer(pat, blob, flags=re.IGNORECASE):
            try:
                n = parse_num(m.group(1))
            except ValueError:
                continue
            if n <= 0 or n > 100000:
                continue
            is_man = bool(re.search(r"滿", m.group(0)))
            if reject_amount(blob, m.start(), m.end(), man_pattern=is_man):
                continue
            # fee-table rows like 1.1–2公里NT$100／滿NT$700 — not 低消800／運費
            after_clause = clause_after(blob, m.end())
            if not re.search(r'(?:通常)?低消|最低(?:訂購|消費)', m.group(0)):
                if '／' in after_clause or '/' in after_clause[:8]:
                    if re.search(r'滿', after_clause):
                        continue
            candidates.append((n, m.start()))

    for m in re.finditer(rf'(?<!未)滿\s*(?:NT\$|\$)\s*({NUM})\s*(?:元)?', blob):
        if reject_amount(blob, m.start(), m.end(), man_pattern=True):
            continue
        ctx = blob[max(0, m.start() - 100): m.end() + 24]
        if not re.search(r'(Minimum|最低|低消|起送|外送|可送)', ctx, re.I):
            continue
        if re.search(r'(促銷|折扣|九折|八五折|不等於|不加收)', ctx):
            continue
        try:
            n = parse_num(m.group(1))
        except ValueError:
            continue
        if 0 < n <= 100000:
            candidates.append((n, m.start()))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[1])
    first_pos = candidates[0][1]
    cluster = [c for c in candidates if c[1] <= first_pos + 160]
    n = min(c[0] for c in cluster)
    return {
        'deliveryMinType': 'amount',
        'deliveryMinValue': n,
        'deliveryMinLabel': f'滿 ${n}',
    }


def extract_free_only(r: dict, blob: str):
    ft = r.get('freeDeliveryThreshold')
    if isinstance(ft, (int, float)) and not isinstance(ft, bool) and ft == int(ft) and int(ft) > 0:
        n = int(ft)
        return {
            'deliveryMinType': 'amount',
            'deliveryMinValue': n,
            'deliveryMinLabel': f'滿 ${n} 免運',
        }
    nums = []
    for m in re.finditer(rf'(?<!未)滿\s*(?:NT\$|\$)?\s*({NUM})\s*(?:元)?\s*(?:免運|免外送費)', blob):
        try:
            n = parse_num(m.group(1))
        except ValueError:
            continue
        if 0 < n <= 100000:
            nums.append(n)
    if nums:
        n = min(nums)
        return {
            'deliveryMinType': 'amount',
            'deliveryMinValue': n,
            'deliveryMinLabel': f'滿 ${n} 免運',
        }
    return None


def infer(r: dict) -> dict:
    blob = text_blob(r)
    qty = extract_quantity(blob)
    if qty:
        return qty
    amt = extract_amount_min(blob)
    if amt:
        return amt
    free = extract_free_only(r, blob)
    if free:
        return free
    return {
        'deliveryMinType': None,
        'deliveryMinValue': None,
        'deliveryMinLabel': None,
    }


def backfill(path: Path) -> tuple[list, list]:
    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    labeled = []
    for r in data:
        fields = infer(r)
        r['deliveryMinType'] = fields['deliveryMinType']
        r['deliveryMinValue'] = fields['deliveryMinValue']
        r['deliveryMinLabel'] = fields['deliveryMinLabel']
        if r['deliveryMinLabel']:
            labeled.append(r)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')
    return data, labeled


def write_data_js(data: list, dest: Path) -> None:
    dest.write_text(
        'window.RESTAURANTS = ' + json.dumps(data, ensure_ascii=False, indent=2) + ';\n',
        encoding='utf-8',
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', type=Path, default=Path('.'))
    args = ap.parse_args()
    root = args.root
    data, labeled = backfill(root / 'restaurants.json')
    write_data_js(data, root / 'data.js')
    print(f'{root}: total={len(data)} labeled={len(labeled)}')
    for r in labeled[:5]:
        print(f"  {r['id']} | {r['name']} | {r['deliveryMinLabel']}")


if __name__ == '__main__':
    main()
