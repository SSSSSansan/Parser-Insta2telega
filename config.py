import os
import base64
from dotenv import load_dotenv

load_dotenv()

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHANNEL_ID = os.getenv("TG_CHANNEL_ID")
IG_USERNAME = os.getenv("IG_USERNAME")
IG_LOGIN = os.getenv("IG_LOGIN")
IG_PASSWORD = os.getenv("IG_PASSWORD")

# На сервере (Railway) нет графического браузера, поэтому save_cookies.py
# там не запустить. Вместо этого cookies кодируются в base64 и кладутся
# в переменную окружения IG_COOKIES_B64 — при старте контейнера бот сам
# восстанавливает из неё instagram_cookies.json. Локально эта переменная
# не нужна — файл cookies уже лежит на диске после save_cookies.py.
_cookies_b64 = os.getenv("IG_COOKIES_B64")
if _cookies_b64 and not os.path.exists("instagram_cookies.json"):
    with open("instagram_cookies.json", "wb") as f:
        f.write(base64.b64decode(_cookies_b64))
    print("🍪 instagram_cookies.json восстановлен из IG_COOKIES_B64")