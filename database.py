import os
import sqlite3

# Локально работает как раньше — просто posts.db рядом с кодом.
# На Railway задашь переменную DB_PATH=/app/data/posts.db (путь внутри
# подключённого volume), и база переживёт передеплой вместо того,
# чтобы обнуляться каждый раз, когда обновляешь код.
DB_PATH = os.getenv("DB_PATH", "posts.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sent_posts (
            post_id TEXT PRIMARY KEY,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def is_sent(post_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute("SELECT 1 FROM sent_posts WHERE post_id = ?", (post_id,))
    result = cur.fetchone()
    conn.close()
    return result is not None

def mark_sent(post_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR IGNORE INTO sent_posts (post_id) VALUES (?)", (post_id,))
    conn.commit()
    conn.close()