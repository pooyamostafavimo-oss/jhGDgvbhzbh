# -*- coding: utf-8 -*-
"""
نسخه‌ی «تک‌اجرا»ی بات، مخصوص اجرا روی GitHub Actions.

برخلاف bot.py (که یک حلقه‌ی بی‌نهایت دارد و مناسب اجرای دائمی روی سرور/VPS است)،
این فایل فقط یک‌بار قیمت‌ها را می‌خواند و یک پیام به کانال پست می‌کند، بعد خارج
می‌شود. زمان‌بندی تکرار (هر چند دقیقه) به‌عهده‌ی GitHub Actions (فایل
.github/workflows/post-prices.yml) است، نه این اسکریپت.

توکن و آیدی کانال باید از طریق GitHub Secrets به‌صورت متغیر محیطی
(BOT_TOKEN و CHANNEL_ID) در اختیار این اسکریپت قرار بگیرد.
"""

import sys

from bot import run_once, logger
from config import BOT_TOKEN

if __name__ == "__main__":
    if BOT_TOKEN == "PUT_YOUR_BOT_TOKEN_HERE":
        logger.error(
            "توکن بات تنظیم نشده! در GitHub این مقدار باید از طریق "
            "Settings > Secrets and variables > Actions با نام BOT_TOKEN ست شده باشد."
        )
        sys.exit(1)

    run_once()
