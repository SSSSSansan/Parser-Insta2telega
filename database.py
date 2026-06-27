import sqlite3

def init_db():
    conn = sqlite3.connect("posts.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sent_posts (
            post_id TEXT PRIMARY KEY,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def is_sent(post_id):
    conn = sqlite3.connect("posts.db")
    cur = conn.execute("SELECT 1 FROM sent_posts WHERE post_id = ?", (post_id,))
    result = cur.fetchone()
    conn.close()
    return result is not None

def mark_sent(post_id):
    conn = sqlite3.connect("posts.db")
    conn.execute("INSERT OR IGNORE INTO sent_posts (post_id) VALUES (?)", (post_id,))
    conn.commit()
    conn.close()