"""
Скрипт для получения свежих cookies Instagram.

Запускается ТОЛЬКО локально (нужен графический браузер) — на сервере
(Railway и т.п.) этот скрипт не работает, там браузера нет.

Использование:
    python3 save_cookies.py

Откроется окно браузера на странице логина Instagram. Залогинься вручную
под служебным аккаунтом (IG_LOGIN / IG_PASSWORD), дождись, пока полностью
загрузится лента, затем вернись в терминал и нажми Enter.
Cookies сохранятся в instagram_cookies.json — именно этот файл потом
использует parser.py (через context.add_cookies).
"""

import json
from pathlib import Path
from playwright.sync_api import sync_playwright

COOKIES_PATH = Path("instagram_cookies.json")


def save_cookies():
    with sync_playwright() as p:
        # headless=False — обязательно, иначе логин-форму просто некому
        # будет заполнить вручную.
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        page.goto("https://www.instagram.com/accounts/login/")

        print("\n🔐 Залогинься в открывшемся окне браузера под служебным аккаунтом.")
        print("   Дождись, пока полностью загрузится лента (главная страница).")
        input("   Когда будешь готова — нажми Enter здесь, в терминале... ")

        cookies = context.cookies()

        if not cookies:
            print("❌ Cookies пустые — похоже, логин не прошёл. Попробуй ещё раз.")
            browser.close()
            return

        with COOKIES_PATH.open("w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)

        print(f"✅ Сохранено {len(cookies)} cookies в {COOKIES_PATH.resolve()}")
        browser.close()


if __name__ == "__main__":
    save_cookies()