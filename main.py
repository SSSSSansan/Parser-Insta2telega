import schedule
import time
import logging
import sys
from parser import get_latest_posts as get_new_posts
from sender import send
from database import init_db, is_sent, mark_sent

logging.basicConfig(
    filename="bot.log",
    level=logging.INFO,
    format="%(asctime)s — %(message)s"
)

# python3 main.py --dry-run  →  парсит и показывает что нашёл, но НЕ отправляет и НЕ пишет в БД
# python3 main.py --once     →  одна проверка и выход (для GitHub Actions/cron)
DRY_RUN = "--dry-run" in sys.argv
ONCE = "--once" in sys.argv

def check_and_send():
    logging.info("Проверяю новые посты...")
    try:
        posts = get_new_posts()
        new_count = 0
        for post in reversed(posts):
            post_id = post.get("id") or post.get("shortcode")
            if is_sent(post_id):
                print(f"⏭️  {post_id} — уже отправлен, пропускаю")
                continue

            new_count += 1
            photos = len(post.get("photo_bytes", []))
            has_video = bool(post.get("video_bytes"))
            print(f"🆕 {post_id} — {photos} фото{'  🎬 + видео' if has_video else ''}")
            print(f"   caption: {post.get('caption','')[:80]}...")

            if DRY_RUN:
                print(f"   [dry-run] НЕ отправляю")
                continue

            send(post)
            mark_sent(post_id)
            logging.info(f"Отправлен пост {post_id}")
            time.sleep(10)

        if new_count == 0:
            print("✅ Новых постов нет")

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        print(f"❌ {e}")

if __name__ == "__main__":
    if DRY_RUN:
        print("🔍 DRY-RUN режим — отправки не будет")

    init_db()
    check_and_send()

    if not DRY_RUN and not ONCE:
        schedule.every(30).minutes.do(check_and_send)
        while True:
            schedule.run_pending()
            time.sleep(60)