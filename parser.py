import json
import re
from playwright.sync_api import sync_playwright
from pathlib import Path
from bs4 import BeautifulSoup

def get_latest_posts(limit=3):
    cookies_path = Path("instagram_cookies.json")
    if not cookies_path.exists():
        raise Exception("❌ Cookies файл не найден.")

    with cookies_path.open("r", encoding="utf-8") as f:
        cookies = json.load(f)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        context.add_cookies(cookies)

        page = context.new_page()
        page.goto("https://www.instagram.com/kbtu_esgcampus/")
        page.wait_for_timeout(6000)

        html = page.content()
        context.close()

        soup = BeautifulSoup(html, "html.parser")
        posts = []
        scripts = soup.find_all("script", text=re.compile("window._sharedData"))

        for a in soup.find_all("a", href=True):
            href = a["href"]

            # Поддержка и /p/ и /reel/
            if not re.search(r"/(p|reel)/", href):
                continue
            
            shortcode = href.strip("/").split("/")[-1]
            
            img_tag = a.find("img")
            image_url = img_tag.get("src", "") if img_tag else ""
            fallback_caption = img_tag.get("alt", "") if img_tag else ""

            # Определение is_video по alt или href
            is_video = href.split("/")[2] == "reel"
            
            # Парсим <script> с JSON, если есть
            real_caption = ""
            for script in scripts:
                json_text = script.string
                match = re.search(r"window\._sharedData = (.*);", json_text)
                if match:
                    data = json.loads(match.group(1))
                    try:
                        edges = data["entry_data"]["ProfilePage"][0]["graphql"]["user"]["edge_owner_to_timeline_media"]["edges"]
                        for edge in edges:
                            node = edge["node"]
                            if node["shortcode"] == shortcode:
                                real_caption = node["edge_media_to_caption"]["edges"][0]["node"]["text"]
                                break
                    except Exception:
                        pass
                if real_caption:
                    break

            posts.append({
                "shortcode": shortcode,
                "caption": real_caption or fallback_caption,
                "url": image_url,
                "is_video": is_video
            })

            if len(posts) >= limit:
                break

        print(f"📥 Получено постов: {len(posts)}")
        return posts
