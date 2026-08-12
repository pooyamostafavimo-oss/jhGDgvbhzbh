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
from zoneinfo import ZoneInfo

import requests

from config import (
    BOT_TOKEN,
    CHANNEL_ID,
    ITEMS,
    NEW_MESSAGE_INTERVAL_SECONDS,
    POST_INTERVAL_SECONDS,
)
from scraper import get_prices
from state import load_state, save_state

# ساعت پیام‌ها باید طبق منطقه‌ی زمانی ایران (تهران) نمایش داده شود،
# چون سرورهای GitHub Actions با ساعت UTC اجرا می‌شوند.
IRAN_TZ = ZoneInfo("Asia/Tehran")

# نام روزهای هفته به فارسی (برای نمایش تاریخ)
WEEKDAYS_FA = {
    0: "دوشنبه",
    1: "سه‌شنبه",
    2: "چهارشنبه",
    3: "پنجشنبه",
    4: "جمعه",
    5: "شنبه",
    6: "یکشنبه",
}

# نام ماه‌های شمسی
MONTHS_FA = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> "tuple[int, int, int]":
    """
    تبدیل تاریخ میلادی به شمسی (جلالی)، بدون نیاز به نصب کتابخانه‌ی جانبی.
    الگوریتم استاندارد و شناخته‌شده‌ی تبدیل گرگوری به جلالی است.
    """
    g_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    j_days_in_month = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]

    gy2 = gy - 1600
    gm2 = gm - 1
    gd2 = gd - 1

    g_day_no = 365 * gy2 + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400
    for i in range(gm2):
        g_day_no += g_days_in_month[i]
    if gm2 > 1 and ((gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)):
        g_day_no += 1
    g_day_no += gd2

    j_day_no = g_day_no - 79

    j_np = j_day_no // 12053
    j_day_no %= 12053

    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461

    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365

    jm = 12
    jd = j_day_no + 1
    for i in range(11):
        if j_day_no < j_days_in_month[i]:
            jm = i + 1
            jd = j_day_no + 1
            break
        j_day_no -= j_days_in_month[i]

    return jy, jm, jd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("gold-price-bot")

SEND_API = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
EDIT_API = f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText"


def get_change_arrow(change_percent: str) -> str:
    """
    بر اساس مقدار درصد تغییر (مثلاً "1.15%", "-2%", "0%")، اموجی مناسب را برمی‌گرداند:
    - صفر (یا خیلی نزدیک به صفر): ➖
    - مثبت: 🔺
    - منفی: 🔻
    """
    try:
        value = float(change_percent.replace("%", "").replace("+", "").strip())
    except (ValueError, AttributeError):
        # اگر به هر دلیلی نتوانستیم عدد را تشخیص دهیم، فقط بر اساس علامت منفی تصمیم بگیر
        return "🔻" if change_percent.strip().startswith("-") else "🔺"

    if value == 0:
        return "➖"
    return "🔺" if value > 0 else "🔻"


def build_message() -> str:
    prices = get_prices(list(ITEMS.keys()))

    now = datetime.now(IRAN_TZ)
    weekday_fa = WEEKDAYS_FA.get(now.weekday(), "")
    jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)
    month_fa = MONTHS_FA[jm - 1]
    date_str = f"{jd} {month_fa} {jy}"
    time_str = now.strftime("%H:%M:%S")

    lines = [
        "📊 <b>گزارش لحظه‌ای قیمت‌ها</b>",
        f"🗓 {weekday_fa} {date_str} - 🕒 {time_str} (به وقت تهران)",
        "",
    ]

    any_found = False
    for source_name, display_name in ITEMS.items():
        row = prices.get(source_name)
        if row is None:
            continue
        any_found = True

        change_str = ""
        if row.change_percent:
            arrow = get_change_arrow(row.change_percent)
            change_str = f" ({arrow} {row.change_percent})"

        lines.append(f"{display_name}: <b>{row.price}</b>{change_str}")

    lines.append("")
    lines.append('📢 <a href="https://t.me/Tala_Dollar_ir">@Tala_Dollar_ir</a>')

    if not any_found:
        return ""

    return "\n".join(lines)


def _extract_description(resp: requests.Response) -> str:
    try:
        return resp.json().get("description", resp.text)
    except ValueError:
        return resp.text


def send_new_message(text: str) -> "int | None":
    """یک پیام جدید ارسال می‌کند و در صورت موفقیت، آیدی آن پیام را برمی‌گرداند."""
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(SEND_API, data=payload, timeout=15)
        if resp.status_code != 200:
            logger.error("خطا در ارسال پیام جدید به تلگرام: %s - %s", resp.status_code, _extract_description(resp))
            return None
        return resp.json().get("result", {}).get("message_id")
    except requests.RequestException as e:
        logger.error("خطای شبکه هنگام ارسال پیام به تلگرام: %s", e)
        return None


def edit_existing_message(text: str, message_id: int) -> bool:
    """
    تلاش می‌کند پیام قبلی را ویرایش کند.
    خروجی True یعنی: پیام ویرایش شد (یا از قبل همین محتوا را داشت) و نیازی
    به ارسال پیام جدید نیست.
    خروجی False یعنی: ویرایش ممکن نشد (مثلاً پیام حذف شده یا خیلی قدیمی
    است) و باید یک پیام جدید ارسال شود.
    """
    payload = {
        "chat_id": CHANNEL_ID,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(EDIT_API, data=payload, timeout=15)
        if resp.status_code == 200:
            return True

        description = _extract_description(resp)
        # اگر محتوای پیام دقیقاً همان محتوای قبلی باشد، تلگرام خطای
        # "message is not modified" می‌دهد؛ این یعنی پیام از قبل به‌روز
        # بوده، پس این حالت را هم موفقیت در نظر می‌گیریم.
        if "not modified" in description.lower():
            return True

        logger.warning(
            "ویرایش پیام قبلی ممکن نشد (%s - %s)؛ به‌جای آن یک پیام جدید ارسال می‌شود.",
            resp.status_code,
            description,
        )
        return False
    except requests.RequestException as e:
        logger.error("خطای شبکه هنگام ویرایش پیام در تلگرام: %s", e)
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

    state = load_state()
    message_id = state.get("message_id")
    same_channel = state.get("chat_id") == CHANNEL_ID
    last_new_message_ts = state.get("last_new_message_ts", 0)
    first_ever_run = not message_id

    now_ts = time.time()
    state_changed = False

    # ۱) پیام پین‌شده (اصلی) را همیشه ویرایش می‌کنیم؛ این پیام هیچ‌وقت عوض
    # نمی‌شود، مگر این‌که ویرایش آن ممکن نباشد (مثلاً حذف شده یا بیش از ۴۸
    # ساعت از ارسالش گذشته باشد) که در آن صورت یک پیام جدید جایگزینش می‌شود.
    edited = False
    if message_id and same_channel:
        edited = edit_existing_message(message, message_id)

    if edited:
        logger.info("پیام پین‌شده با موفقیت ویرایش شد (message_id=%s).", message_id)
    else:
        new_pinned_id = send_new_message(message)
        if new_pinned_id is not None:
            message_id = new_pinned_id
            state_changed = True
            logger.info(
                "ویرایش پیام قبلی ممکن نبود؛ پیام پین‌شده‌ی جدیدی ارسال شد (message_id=%s). "
                "لطفاً این پیام را در کانال پین کنید.",
                new_pinned_id,
            )
            if first_ever_run:
                # همان لحظه که پیام پین‌شده برای اولین‌بار ساخته می‌شود، شمارش
                # فاصله‌ی ۳۰ دقیقه‌ای هم از همین لحظه شروع شود، تا در همین دور
                # یک پیام اضافه‌ی تکراری هم پست نشود.
                last_new_message_ts = now_ts

    # ۲) جدا از ویرایش بالا، هر NEW_MESSAGE_INTERVAL_SECONDS یک‌بار، یک پیام
    # تازه‌ی اضافه هم ارسال می‌کنیم (بدون این‌که به پیام پین‌شده دست بزنیم)،
    # تا کسانی که کانال را ساب کرده‌اند یک نوتیفیکیشن/پیام تازه بالای چتشان
    # ببینند.
    if (now_ts - last_new_message_ts) >= NEW_MESSAGE_INTERVAL_SECONDS:
        extra_message_id = send_new_message(message)
        if extra_message_id is not None:
            last_new_message_ts = now_ts
            state_changed = True
            logger.info(
                "طبق فاصله‌ی %s ثانیه‌ای، یک پیام تازه‌ی اضافه (غیر از پیام پین‌شده) پست شد (message_id=%s).",
                NEW_MESSAGE_INTERVAL_SECONDS,
                extra_message_id,
            )

    if state_changed:
        save_state(
            {
                "chat_id": CHANNEL_ID,
                "message_id": message_id,
                "last_new_message_ts": last_new_message_ts,
            }
        )


def main() -> None:
    if BOT_TOKEN == "PUT_YOUR_BOT_TOKEN_HERE":
        logger.error(
            "توکن بات تنظیم نشده! لطفاً در config.py مقدار BOT_TOKEN را وارد کنید "
            "یا متغیر محیطی BOT_TOKEN را ست کنید."
        )
        sys.exit(1)

    logger.info(
        "بات شروع به کار کرد. فاصله‌ی ویرایش: %s ثانیه - فاصله‌ی پیام تازه: %s ثانیه",
        POST_INTERVAL_SECONDS,
        NEW_MESSAGE_INTERVAL_SECONDS,
    )

    while True:
        run_once()
        time.sleep(POST_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
