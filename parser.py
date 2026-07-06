import json
import re
import subprocess
import tempfile
import os
import time
from playwright.sync_api import sync_playwright
from pathlib import Path
from bs4 import BeautifulSoup

LIMIT = 4


def merge_video_audio(video_bytes: bytes, audio_bytes: bytes) -> bytes:
    with tempfile.TemporaryDirectory() as tmpdir:
        v_path = os.path.join(tmpdir, "video.mp4")
        a_path = os.path.join(tmpdir, "audio.mp4")
        out_path = os.path.join(tmpdir, "output.mp4")
        with open(v_path, "wb") as f:
            f.write(video_bytes)
        with open(a_path, "wb") as f:
            f.write(audio_bytes)
        result = subprocess.run([
            "ffmpeg", "-y", "-i", v_path, "-i", a_path,
            "-c:v", "copy", "-c:a", "aac", "-shortest", out_path
        ], capture_output=True)
        if result.returncode != 0:
            print(f"  ⚠️ ffmpeg: {result.stderr[-300:]}")
            return video_bytes
        with open(out_path, "rb") as f:
            return f.read()


def wait_for_network_quiet(page, size_fn, quiet_ms=1500, max_ms=6000, poll_ms=200):
    """Ждёт не фиксированное время, а пока перестанут прилетать новые байты."""
    start = time.time()
    last_size = -1
    last_change = time.time()
    while True:
        page.wait_for_timeout(poll_ms)
        size = size_fn()
        if size != last_size:
            last_size = size
            last_change = time.time()
        if (time.time() - last_change) * 1000 >= quiet_ms:
            return
        if (time.time() - start) * 1000 >= max_ms:
            return


# Достаём URL текущего показанного фото СТРОГО по видимости на экране.
# Мы никогда не скроллим страницу, поэтому в зоне видимости (viewport)
# может быть только сам пост — блок "Похожие посты"/рекомендации Instagram
# рендерит НИЖЕ по странице, и getBoundingClientRect для них покажет
# координаты за пределами экрана. Это надёжнее, чем искать конкретный
# <article>, потому что Instagram использует article-теги и для карточек
# в рекомендациях тоже — точный querySelector('article') мог зацепить не тот.
GET_VISIBLE_SLIDE_JS = """
() => {
    const imgs = document.querySelectorAll('img');
    let best = '', bestW = 0;
    const vh = window.innerHeight;
    imgs.forEach(img => {
        const rect = img.getBoundingClientRect();
        // изображение должно реально попадать в видимую область экрана
        if (rect.bottom <= 0 || rect.top >= vh) return;
        // отсекаем маленькие иконки/лого/аватарки по фактическому размеру на экране
        // (порог занижен и ослаблен, чтобы не резать реальные фото раньше времени)
        if (rect.width < 150 || rect.height < 150) return;
        if (img.srcset) {
            img.srcset.split(',').forEach(part => {
                const [url, w] = part.trim().split(' ');
                const width = parseInt(w) || 0;
                if (width > bestW && url && !url.includes('t51.2885-19')) {
                    bestW = width; best = url;
                }
            });
        } else if (img.src && bestW === 0) {
            // запасной вариант, если srcset ещё не прогрузился
            best = img.src;
            bestW = rect.width;
        }
    });
    return best;
}
"""

def wait_for_slide_change(page, prev_base, max_ms=3000, poll_ms=150):
    """
    После клика 'Далее' ждём не фиксированное время, а пока видимый слайд
    РЕАЛЬНО не сменится в DOM (сравниваем base URL картинки).
    Это убирает гонку: раньше был фиксированный page.wait_for_timeout(1000),
    из-за которого код либо читал ещё старый слайд (казалось что карусель
    кончилась раньше времени), либо ловил фото в момент полу-отрисовки
    (дублирующиеся/битые кадры). Возвращает новый url слайда (или старый,
    если так и не дождались смены — тогда вызывающий код это обработает
    как конец карусели через сравнение base в seen_bases).
    """
    start = time.time()
    while (time.time() - start) * 1000 < max_ms:
        page.wait_for_timeout(poll_ms)
        url = page.evaluate(GET_VISIBLE_SLIDE_JS)
        base = url.split("?")[0] if url else ""
        if base and base != prev_base:
            return url
    # так и не сменился за max_ms — возвращаем что есть,
    # вызывающий код сам решит что делать (скорее всего это конец карусели)
    return page.evaluate(GET_VISIBLE_SLIDE_JS)


DEBUG_IMAGES_JS = """
() => {
    return Array.from(document.querySelectorAll('img')).map(img => {
        const r = img.getBoundingClientRect();
        return {
            src: (img.src || '').slice(-60),
            hasSrcset: !!img.srcset,
            w: Math.round(r.width), h: Math.round(r.height),
            top: Math.round(r.top), bottom: Math.round(r.bottom)
        };
    });
}
"""


def get_latest_posts(limit=LIMIT):
    cookies_path = Path("instagram_cookies.json")
    if not cookies_path.exists():
        raise Exception("❌ Cookies файл не найден.")

    with cookies_path.open("r", encoding="utf-8") as f:
        cookies = json.load(f)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            posts = _scrape(browser, cookies, limit)
        finally:
            browser.close()  # выполнится даже при ошибке — без этого при
            # сбое процесс Chromium останется висеть в памяти навсегда
        print(f"\n📥 Итого постов: {len(posts)}")
        return posts


def _scrape(browser, cookies, limit):
    context = browser.new_context()
    context.add_cookies(cookies)
    page = context.new_page()

    page.goto("https://www.instagram.com/kbtu_esgcampus/")
    page.wait_for_timeout(6000)
    soup = BeautifulSoup(page.content(), "html.parser")

    shortcodes = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not re.search(r"/(p|reel)/", href):
            continue
        shortcode = href.strip("/").split("/")[-1]
        is_video = "/reel/" in href
        if shortcode not in [s["shortcode"] for s in shortcodes]:
            shortcodes.append({"shortcode": shortcode, "is_video": is_video})
        if len(shortcodes) >= limit:
            break

    posts = []
    for item in shortcodes:
        shortcode = item["shortcode"]
        is_video = item["is_video"]
        print(f"\n{'🎬 Рилс' if is_video else '🖼  Пост'} {shortcode}")

        video_chunks = {}

        def on_video_response(response):
            url = response.url
            if not re.search(r"/o1/v/t2/|/v/t50\.", url):
                return
            if not ("fbcdn.net" in url or "cdninstagram.com" in url):
                return
            try:
                data = response.body()
                if len(data) == 0:
                    return
                key = url.split("?")[0]
                video_chunks.setdefault(key, []).append(data)
                total = sum(len(c) for c in video_chunks[key])
                stype = "video" if "/m86/" in url else ("audio" if "/m78/" in url else "other")
                print(f"  🎬 {stype} {len(data)//1024}KB | total {total//1024}KB")
            except:
                pass

        # Для видео перехват сети оставляем как раньше — это единственный
        # способ достать видео-байты, там проблема была только в тайминге.
        if is_video:
            page.on("response", on_video_response)

        page.goto(f"https://www.instagram.com/p/{shortcode}/")

        if is_video:
            try:
                page.evaluate("""
                    () => {
                        const v = document.querySelector('video');
                        if (v) { v.muted = true; v.play().catch(()=>{}); }
                    }
                """)
            except:
                pass
            wait_for_network_quiet(
                page,
                size_fn=lambda: sum(len(c) for v in video_chunks.values() for c in v),
                quiet_ms=2500,
                max_ms=25000,
            )
            page.remove_listener("response", on_video_response)
        else:
            # Даём странице отрисоваться перед тем как читать DOM.
            # Увеличено с 2.5с — фото/srcset могут догружаться дольше.
            page.wait_for_timeout(4500)

        # Видео/аудио
        video_bytes = None
        if is_video and video_chunks:
            v_streams = {k: v for k, v in video_chunks.items() if "/m86/" in k}
            a_streams = {k: v for k, v in video_chunks.items() if "/m78/" in k}
            if v_streams:
                best_v = max(v_streams, key=lambda k: sum(len(c) for c in v_streams[k]))
                raw_video = b"".join(v_streams[best_v])
                print(f"  🎬 видео: {len(raw_video)//1024}KB")
                if a_streams:
                    best_a = max(a_streams, key=lambda k: sum(len(c) for c in a_streams[k]))
                    raw_audio = b"".join(a_streams[best_a])
                    print(f"  🔊 аудио: {len(raw_audio)//1024}KB — склеиваю...")
                    video_bytes = merge_video_audio(raw_video, raw_audio)
                    print(f"  ✅ итого: {len(video_bytes)//1024}KB")
                else:
                    video_bytes = raw_video
            elif video_chunks:
                best = max(video_chunks, key=lambda k: sum(len(c) for c in video_chunks[k]))
                video_bytes = b"".join(video_chunks[best])

        # Caption
        caption = ""
        first_image_url = ""  # только для ссылки/метаданных, НЕ источник байтов фото
        try:
            post_soup = BeautifulSoup(page.content(), "html.parser")
            meta = post_soup.find("meta", {"property": "og:description"})
            if meta:
                caption = meta.get("content", "")
                caption = re.sub(r"^\d+\s+likes?,\s*\d+\s+comments?\s*-\s*", "", caption)
            meta_img = post_soup.find("meta", {"property": "og:image"})
            if meta_img:
                first_image_url = meta_img.get("content", "")
        except:
            pass

        photo_bytes = []

        if is_video:
            # Для рилсов og:image как обложка — здесь это ок, кроп не критичен,
            # так как основной контент — видео.
            if first_image_url:
                try:
                    resp = page.request.get(first_image_url)
                    if resp.ok:
                        data = resp.body()
                        print(f"  📸 обложка рилса: {len(data)//1024}KB")
                        photo_bytes.append(data)
                except Exception as e:
                    print(f"  ⚠️ обложка рилса: {e}")
        else:
            # --- Карусель: DOM + фильтр по видимой области экрана ---
            seen_bases = set()

            for slide_num in range(10):
                dom_url = page.evaluate(GET_VISIBLE_SLIDE_JS)
                base = dom_url.split("?")[0] if dom_url else ""

                if not dom_url or base in seen_bases:
                    if slide_num == 0:
                        # Ничего не нашли с первой попытки — печатаем что
                        # вообще есть в DOM, чтобы понять причину (для отладки,
                        # можно убрать после того как заработает стабильно).
                        try:
                            debug_imgs = page.evaluate(DEBUG_IMAGES_JS)
                            print(f"  🔍 DEBUG: найдено {len(debug_imgs)} <img> в DOM:")
                            for d in debug_imgs[:15]:
                                print(f"     {d}")
                        except Exception as e:
                            print(f"  🔍 DEBUG ошибка: {e}")
                    print(f"  ➡️ конец карусели")
                    break

                try:
                    resp = page.request.get(dom_url)
                    data = resp.body()
                    if resp.ok and len(data) > 10_000:
                        seen_bases.add(base)
                        photo_bytes.append(data)
                        print(f"  🖼 слайд {len(photo_bytes)}: {len(data)//1024}KB")
                    else:
                        print(f"  ⚠️ слайд {slide_num + 1}: пустой/битый ответ")
                        break
                except Exception as e:
                    print(f"  ⚠️ слайд {slide_num + 1}: {e}")
                    break

                # СТРОГО внутри article поста — иначе, когда карусель
                # реально кончается, находится кнопка "Далее" в блоке
                # рекомендаций внизу страницы, и скрипт продолжает
                # кликать уже по чужим постам (отсюда лишние фото).
                next_btn = (
                    page.query_selector("article button[aria-label='Далее']")
                    or page.query_selector("article button[aria-label='Next']")
                )
                if not next_btn:
                    break
                try:
                    if not next_btn.is_visible():
                        break
                except Exception:
                    break

                next_btn.click()
                # Ждём не фиксированное время, а пока слайд реально сменится
                # в DOM — устраняет гонку, из-за которой карусель либо
                # обрывалась раньше времени, либо ловила дубли/битые кадры.
                wait_for_slide_change(page, prev_base=base)

        print(f"  → итого {len(photo_bytes)} фото" +
              (f" | видео {'✅' if video_bytes else '❌'}" if is_video else ""))

        posts.append({
            "shortcode": shortcode,
            "caption": caption,
            "images": [first_image_url],
            "photo_bytes": photo_bytes,
            "video_bytes": video_bytes,
            "url": first_image_url,
            "is_video": is_video
        })

    context.close()
    return posts