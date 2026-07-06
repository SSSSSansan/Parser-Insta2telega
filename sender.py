import asyncio
import io
from telegram import Bot, InputMediaPhoto
from html import escape
from PIL import Image
import config

bot = Bot(token=config.TG_BOT_TOKEN)

MAX_CAPTION_LENGTH = 1024
MAX_PHOTOS_PER_ALBUM = 10
TARGET_RATIO = 4 / 5  # ширина/высота — стандартный портретный формат ленты IG


def format_caption(caption, shortcode):
    link = f"https://www.instagram.com/p/{shortcode}"
    clean = escape(caption.strip()) if caption else ""
    header = "🌿 <b>KBTU ESG Campus</b>\n"
    divider = "─────────────────\n"
    footer = f"\n─────────────────\n📎 <a href='{link}'>Открыть в Instagram</a>"
    available = MAX_CAPTION_LENGTH - len(header) - len(divider) - len(footer)
    if clean and len(clean) > available:
        clean = clean[:available - 3].rsplit(" ", 1)[0] + "..."
    return header + divider + (clean if clean else "") + footer


def pad_to_ratio(data: bytes, ratio: float = TARGET_RATIO) -> bytes:
    """
    Добавляет белые поля так, чтобы все фото в альбоме имели одинаковые
    пропорции. Telegram обрезает фото в мозаике альбома именно из-за
    разных пропорций у элементов — после выравнивания обрезки не будет.
    """
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:
        return data  # если не смогли открыть — отправляем как есть

    w, h = img.size
    cur_ratio = w / h

    if cur_ratio > ratio:
        # фото шире, чем нужно — добавляем поля сверху/снизу
        new_h = int(w / ratio)
        canvas = Image.new("RGB", (w, new_h), (255, 255, 255))
        canvas.paste(img, (0, (new_h - h) // 2))
    else:
        # фото уже, чем нужно — добавляем поля слева/справа
        new_w = int(h * ratio)
        canvas = Image.new("RGB", (new_w, h), (255, 255, 255))
        canvas.paste(img, ((new_w - w) // 2, 0))

    out = io.BytesIO()
    canvas.save(out, format="JPEG", quality=92)
    return out.getvalue()


async def send_with_retry(coro_fn, retries=3, delay=40):
    for attempt in range(retries):
        try:
            return await coro_fn()
        except Exception as e:
            err = str(e)
            if "Flood control" in err or "Too Many Requests" in err:
                wait = delay * (attempt + 1)
                print(f"  ⏳ Flood control, жду {wait}s...")
                await asyncio.sleep(wait)
            elif "Timed out" in err and attempt < retries - 1:
                print(f"  ⏳ Timeout, повтор через 10s...")
                await asyncio.sleep(10)
            else:
                raise


async def send_post_async(post):
    shortcode = post.get("shortcode") or post.get("id")
    caption_text = format_caption(post.get("caption", ""), shortcode)
    photo_bytes = post.get("photo_bytes", [])
    video_bytes = post.get("video_bytes")
    is_video = post.get("is_video", False)

    # Рилс с видео
    if is_video and video_bytes:
        async def do_send():
            await bot.send_video(
                chat_id=config.TG_CHANNEL_ID,
                video=io.BytesIO(video_bytes),
                caption=caption_text,
                parse_mode="HTML",
                supports_streaming=True,
                write_timeout=120,
                read_timeout=120,
            )
        await send_with_retry(do_send)
        print(f"✅ Рилс {shortcode}: видео")
        return

    # Рилс без видео — обложка
    if is_video and not video_bytes and photo_bytes:
        async def do_send():
            await bot.send_photo(
                chat_id=config.TG_CHANNEL_ID,
                photo=io.BytesIO(photo_bytes[0]),
                caption=caption_text,
                parse_mode="HTML"
            )
        await send_with_retry(do_send)
        print(f"📸 Рилс {shortcode}: только обложка")
        return

    if not photo_bytes:
        async def do_send():
            await bot.send_message(
                chat_id=config.TG_CHANNEL_ID,
                text=caption_text,
                parse_mode="HTML"
            )
        await send_with_retry(do_send)
        print(f"📝 {shortcode}: только текст")
        return

    photos = photo_bytes[:MAX_PHOTOS_PER_ALBUM]

    if len(photos) == 1:
        # Одно фото — отправляем как есть, без обрезки (нет альбома — нет мозаики)
        async def do_send():
            await bot.send_photo(
                chat_id=config.TG_CHANNEL_ID,
                photo=io.BytesIO(photos[0]),
                caption=caption_text,
                parse_mode="HTML"
            )
        await send_with_retry(do_send)
    else:
    
        padded = [pad_to_ratio(data) for data in photos]

        media_group = []
        for i, data in enumerate(padded):
            if i == 0:
                media_group.append(InputMediaPhoto(
                    media=io.BytesIO(data),
                    caption=caption_text,
                    parse_mode="HTML"
                ))
            else:
                media_group.append(InputMediaPhoto(media=io.BytesIO(data)))

        async def do_send():
            await bot.send_media_group(
                chat_id=config.TG_CHANNEL_ID,
                media=media_group
            )
        await send_with_retry(do_send)

    print(f"✅ {shortcode}: {len(photos)} фото")


def send(post):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.run_until_complete(send_post_async(post))
    except Exception as e:
        print(f"❌ {post.get('shortcode')}: {e}")