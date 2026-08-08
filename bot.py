# -*- coding: utf-8 -*-
"""
بات تلگرامی گزارش قیمت طلا / دلار / نقره و ...

نحوه‌ی کار:
    هر N ثانیه (تنظیم‌شده در config.py) صفحه‌ی tgju.org را می‌خواند،
    قیمت‌های موردنظر را استخراج می‌کند و یک پیام فرمت‌شده به کانال
    تلگرام موردنظر پست می‌کند.

اجرا:
    python3 bot.py

برای اجرای دائمی روی سرور، به README.md (بخش systemd) مراجعه کنید.
"""

import logging
import sys
import time
from datetime import datetime

import requests

from config import BOT_TOKEN, CHANNEL_ID, ITEMS, POST_INTERVAL_SECONDS
from scraper import get_prices

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("gold-price-bot")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"


def build_message() -> str:
    prices = get_prices(list(ITEMS.keys()))

    now = datetime.now().strftime("%H:%M:%S")
    lines = [f"📊 <b>گزارش لحظه‌ای قیمت‌ها</b>", f"🕒 {now}", ""]

    any_found = False
    for source_name, display_name in ITEMS.items():
        row = prices.get(source_name)
        if row is None:
            continue
        any_found = True

        change_str = ""
        if row.change_percent:
            arrow = "🔺" if not row.change_percent.startswith("-") else "🔻"
            change_str = f" ({arrow} {row.change_percent})"

        lines.append(f"{display_name}: <b>{row.price}</b>{change_str}")

    lines.append("")
    

    if not any_found:
        return ""

    return "\n".join(lines)


def send_to_telegram(text: str) -> bool:
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(TELEGRAM_API, data=payload, timeout=15)
        if resp.status_code != 200:
            logger.error("خطا در ارسال به تلگرام: %s - %s", resp.status_code, resp.text)
            return False
        return True
    except requests.RequestException as e:
        logger.error("خطای شبکه هنگام ارسال به تلگرام: %s", e)
        return False


def run_once() -> None:
    try:
        message = build_message()
    except Exception as e:
        logger.exception("خطا در دریافت/پردازش قیمت‌ها: %s", e)
        return

    if not message:
        logger.warning("هیچ قیمتی استخراج نشد؛ این دور پست نمی‌شود.")
        return

    if send_to_telegram(message):
        logger.info("پیام با موفقیت در کانال پست شد.")


def main() -> None:
    if BOT_TOKEN == "PUT_YOUR_BOT_TOKEN_HERE":
        logger.error(
            "توکن بات تنظیم نشده! لطفاً در config.py مقدار BOT_TOKEN را وارد کنید "
            "یا متغیر محیطی BOT_TOKEN را ست کنید."
        )
        sys.exit(1)

    logger.info("بات شروع به کار کرد. فاصله‌ی ارسال: %s ثانیه", POST_INTERVAL_SECONDS)

    while True:
        run_once()
        time.sleep(POST_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
