# -*- coding: utf-8 -*-
"""
این ماژول صفحه‌ی اصلی tgju.org را می‌خواند و از داخل جدول‌های آن، قیمت
آیتم‌های موردنظر (طلا / دلار / نقره / ...) را استخراج می‌کند.

نکته: چون این کار «اسکرپینگ» (scraping) است و به ساختار HTML سایت وابسته
است، اگر سایت ساختار خودش را عوض کند ممکن است لازم باشد این فایل به‌روز شود.
سعی شده پارسر تا حد امکان انعطاف‌پذیر نوشته شود (بر اساس شروع نام ردیف،
نه اندیس دقیق ستون یا کلاس CSS خاص) تا در برابر تغییرات جزئی مقاوم باشد.
"""

import logging
import re
import time
from dataclasses import dataclass
from typing import Dict, Optional

import requests
from bs4 import BeautifulSoup

from config import SOURCE_URL

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
    # این هدرها از کش‌شدن پاسخ توسط CDN سایت مبدأ جلوگیری می‌کنند
    # تا همیشه آخرین نسخه‌ی صفحه (نه یک نسخه‌ی قدیمی ذخیره‌شده) دریافت شود.
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
}


@dataclass
class PriceRow:
    name: str
    price: str
    change_percent: Optional[str] = None
    change_value: Optional[str] = None


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def fetch_html(url: str = SOURCE_URL, timeout: int = 15) -> str:
    # پارامتر تصادفی مبتنی بر زمان به آدرس اضافه می‌شود تا هر بار
    # یک آدرس «تازه» از نظر کش دیده شود و CDN مجبور شود نسخه‌ی جدید بدهد.
    cache_buster = int(time.time())
    sep = "&" if "?" in url else "?"
    bust_url = f"{url}{sep}_={cache_buster}"

    resp = requests.get(bust_url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.text



def parse_all_rows(html: str) -> Dict[str, PriceRow]:
    """
    تمام جدول‌های صفحه را می‌گردد و برای هر ردیف، اولین ستون را به‌عنوان
    «نام» و دومین ستون را به‌عنوان «قیمت» در نظر می‌گیرد. اگر ستون سوم
    شامل درصد/مقدار تغییر باشد، آن را هم استخراج می‌کند.
    خروجی: دیکشنری {نام_ردیف: PriceRow}
    """
    soup = BeautifulSoup(html, "html.parser")
    rows_found: Dict[str, PriceRow] = {}

    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = tr.find_all(["td", "th"])
            if len(cells) < 2:
                continue

            name = _clean_text(cells[0].get_text())
            price = _clean_text(cells[1].get_text())

            # ردیف‌های بی‌ربط (هدر جدول و ...) را رد کن
            if not name or not price:
                continue
            if not re.search(r"\d", price):
                continue

            change_percent = None
            change_value = None
            if len(cells) >= 3:
                change_text = _clean_text(cells[2].get_text())
                m = re.search(r"\(([-+]?[\d.]+%)\)\s*([-+]?[\d,.]+)?", change_text)
                if m:
                    change_percent = m.group(1)
                    change_value = m.group(2)
                elif change_text:
                    change_value = change_text

            # اگر این نام قبلاً دیده نشده، ذخیره کن (اولین مقدار معمولاً معتبرترین است)
            if name not in rows_found:
                rows_found[name] = PriceRow(
                    name=name,
                    price=price,
                    change_percent=change_percent,
                    change_value=change_value,
                )

    return rows_found


def get_prices(item_names) -> Dict[str, Optional[PriceRow]]:
    """
    برای لیستی از نام‌های موردنظر (مثلاً ["دلار", "طلای 18 عیار"])،
    ردیف متناظر را از صفحه استخراج و برمی‌گرداند.
    اگر نامی پیدا نشود مقدار None برمی‌گردد (و در لاگ هشدار داده می‌شود).
    """
    html = fetch_html()
    all_rows = parse_all_rows(html)

    result: Dict[str, Optional[PriceRow]] = {}
    for target in item_names:
        target_clean = _clean_text(target)
        match = all_rows.get(target_clean)

        # اگر تطابق دقیق پیدا نشد، دنبال تطابق تقریبی (شروع با همان متن) بگرد
        if match is None:
            for row_name, row in all_rows.items():
                if row_name.startswith(target_clean) or target_clean.startswith(row_name):
                    match = row
                    break

        if match is None:
            logger.warning("قیمت '%s' در صفحه پیدا نشد.", target)

        result[target] = match

    return result


if __name__ == "__main__":
    # اجرای مستقیم این فایل برای تست سریع (خروجی در ترمینال چاپ می‌شود)
    logging.basicConfig(level=logging.INFO)
    from config import ITEMS

    prices = get_prices(list(ITEMS.keys()))
    for key, row in prices.items():
        if row:
            print(f"{key}: {row.price}  تغییر: {row.change_percent} ({row.change_value})")
        else:
            print(f"{key}: پیدا نشد!")
