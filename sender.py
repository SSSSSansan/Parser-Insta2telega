import asyncio
from telegram import Bot
import config

bot = Bot(token=config.TG_BOT_TOKEN)

async def send_post(post):
    post_id = post.get("id") or post.get("shortcode")
    image_url = post.get("image_url") or post.get("url")
    post_url = f"https://www.instagram.com/p/{post_id}/"
    caption_text = post.get("caption") or post.get("caption", "")
    
    caption = f"📌 {caption_text[:900]}\n\n🔗 {post_url}" if caption_text else post_url
    
    try:
        await bot.send_photo(
            chat_id=config.TG_CHANNEL_ID,
            photo=image_url,
            caption=caption
        )
    except Exception as e:
        print(f"Ошибка отправки фото: {e}")
        await bot.send_message(chat_id=config.TG_CHANNEL_ID, text=caption)

def send(post):
    asyncio.run(send_post(post))