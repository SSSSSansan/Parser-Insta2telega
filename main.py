import schedule
import time
import logging
from parser import get_latest_posts as get_new_posts
from sender import send
from database import init_db, is_sent, mark_sent

logging.basicConfig(
    filename="bot.log",
    level=logging.INFO,
    format="%(asctime)s — %(message)s"
)

def check_and_send():
    logging.info("Проверяю новые посты...")
    try:
        posts = get_new_posts()
        for post in reversed(posts):
            post_id = post.get("id") or post.get("shortcode")
            if not is_sent(post_id):
                send(post)
                mark_sent(post_id)
                logging.info(f"Отправлен пост {post_id}")
                time.sleep(3)
    except Exception as e:
        logging.error(f"Ошибка: {e}")

if __name__ == "__main__":
    init_db()
    check_and_send()  # сразу при запуске
    
    schedule.every(30).minutes.do(check_and_send)
    
    while True:
        schedule.run_pending()
        time.sleep(60)