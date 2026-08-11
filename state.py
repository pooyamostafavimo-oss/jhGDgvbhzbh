# -*- coding: utf-8 -*-
"""
این ماژول مسئول ذخیره و بازخوانی «آخرین پیام ارسال‌شده» است.

چرا لازم است؟
    چون می‌خواهیم به‌جای ارسال یک پیام جدید در هر دور، همان پیام قبلی را
    ویرایش (edit) کنیم. برای این کار باید آیدی پیام قبلی و آیدی کانالی که
    در آن ارسال شده را جایی نگه داریم.

    در حالت اجرای دائمی (bot.py روی یک سرور/VPS) این مقدار به‌سادگی در
    حافظه (RAM) نگه داشته می‌شود و مشکلی نیست، چون پردازش هیچ‌وقت متوقف
    نمی‌شود.

    اما در حالت GitHub Actions (post_once.py) هر اجرا در یک ماشین کاملاً
    تازه انجام می‌شود و هیچ حافظه‌ی مشترکی بین اجراها وجود ندارد. به همین
    خاطر این مقدار در یک فایل JSON (پیش‌فرض: last_message.json) ذخیره
    می‌شود و باید توسط ورک‌فلو گیت‌هاب اکشن، بعد از هر اجرا، دوباره به
    داخل ریپازیتوری کامیت/پوش شود تا در اجرای بعدی همچنان در دسترس باشد.
    این کار در فایل .github/workflows/post-prices.yml انجام شده است.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)

# مسیر فایلی که آیدی آخرین پیام در آن ذخیره می‌شود.
# می‌توانید با متغیر محیطی STATE_FILE مسیر دیگری تعیین کنید.
STATE_FILE = os.getenv("STATE_FILE", "last_message.json")


def load_state() -> dict:
    """
    آخرین وضعیت ذخیره‌شده را می‌خواند.
    اگر فایل وجود نداشته باشد یا خراب باشد، دیکشنری خالی برمی‌گرداند
    (یعنی: «پیام قبلی‌ای در دسترس نیست، باید یک پیام جدید ارسال شود»).
    """
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("فایل وضعیت (%s) قابل خواندن نبود، از صفر شروع می‌شود: %s", STATE_FILE, e)
    return {}


def save_state(data: dict) -> None:
    """وضعیت جدید (آیدی پیام و آیدی کانال) را در فایل ذخیره می‌کند."""
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.error("ذخیره‌ی فایل وضعیت (%s) با خطا مواجه شد: %s", STATE_FILE, e)


def clear_state() -> None:
    """وضعیت را پاک می‌کند (مثلاً وقتی ویرایش پیام دیگر ممکن نیست)."""
    save_state({})
