import os
from dotenv import load_dotenv

load_dotenv()

TG_BOT_TOKEN = os.getenv("TG_BOT_TOKEN")
TG_CHANNEL_ID = os.getenv("TG_CHANNEL_ID")
IG_USERNAME = os.getenv("IG_USERNAME")
IG_LOGIN = os.getenv("IG_LOGIN")
IG_PASSWORD = os.getenv("IG_PASSWORD")