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
    """
    Ждёт не фиксированное время, а пока перестанут прилетать новые байты.
    size_fn() должна возвращать текущий суммарный размер скачанного (int).
    Останавливается, если quiet_ms прошло без изменений, либо истёк max_ms.
    """
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


def _is_full_size_photo_url(url: str) -> bool:
    """Полноразмерное фото Instagram (t51.82787-15 / t51.71878-15), а не превьюшка."""
    if not re.search(r"t51\.(82787|71878)-15", url):
        return False
    if any(s in url for s in ["s150x150", "s320x320", "s480x480"]):
        return False
    return True


def make_image_listener(image_chunks: dict, image_order: list):
    """
    Слушатель network-ответов, который перехватывает ПОЛНОРАЗМЕРНЫЕ фото-байты
    прямо из сети — то есть ровно то, что реально отрисовано на странице,
    а не обрезанный вариант из og:image.

    image_chunks: base_url -> bytes
    image_order:  порядок появления base_url (== порядок слайдов карусели)
    """
    def on_image_response(response):
        url = response.url
        if not _is_full_size_photo_url(url):
            return
        base = url.split("?")[0]
        if base in image_chunks:
            return
        try:
            data = response.body()
            if len(data) > 10_000:
                image_chunks[base] = data
                image_order.append(base)
                print(f"  🖼 фото перехвачено (слайд {len(image_order)}): {len(data)//1024}KB")
        except Exception:
            pass
    return on_image_response


def get_latest_posts(limit=LIMIT):
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

            # --- Фото-карусель: перехватчик вешаем ДО перехода на страницу поста ---
            # Это критично: Instagram часто преднагружает 2-й слайд карусели ещё
            # во время самой первой загрузки страницы. Если слушатель ставится
            # только внутри цикла кликов (как было раньше), этот преднагруженный
            # запрос уже прошёл мимо и 2-й слайд просто теряется.
            image_chunks = {}
            image_order = []
            on_image_response = make_image_listener(image_chunks, image_order)

            if is_video:
                page.on("response", on_video_response)
            else:
                page.on("response", on_image_response)

            page.goto(f"https://www.instagram.com/p/{shortcode}/")

            if is_video:
                # форсируем проигрывание, чтобы плеер начал качать сегменты
                try:
                    page.evaluate("""
                        () => {
                            const v = document.querySelector('video');
                            if (v) { v.muted = true; v.play().catch(()=>{}); }
                        }
                    """)
                except:
                    pass

                # ждём не 8 секунд "на глазок", а пока сеть реально не затихнет
                wait_for_network_quiet(
                    page,
                    size_fn=lambda: sum(len(c) for v in video_chunks.values() for c in v),
                    quiet_ms=2500,
                    max_ms=25000,
                )
                page.remove_listener("response", on_video_response)
            else:
                # ждём, пока подтянутся все фото, которые Instagram решил
                # преднагрузить сразу (слайд 1, часто и слайд 2)
                wait_for_network_quiet(
                    page,
                    size_fn=lambda: sum(len(v) for v in image_chunks.values()),
                    quiet_ms=2000,
                    max_ms=10000,
                )
                # ВАЖНО: сразу снимаем слушатель. Если держать его открытым
                # и дальше (на всё время цикла кликов по карусели), в него
                # начинают залетать фото из блока "похожие посты"/рекомендаций
                # ниже на странице — они того же полноразмерного формата
                # (t51.82787-15) и никак не отличимы по URL от настоящих
                # слайдов карусели. Поэтому слушатель включаем только на
                # короткие окна вокруг конкретных действий (см. цикл ниже),
                # а не постоянно.
                page.remove_listener("response", on_image_response)

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
            first_image_url = ""  # только для метаданных (ссылка), НЕ источник байтов фото
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
                # Для рилсов фото не критично (есть видео), но если нужен превью-кадр —
                # это единственный доступный источник, поэтому оставляем как fallback.
                if first_image_url:
                    try:
                        resp = page.request.get(first_image_url)
                        if resp.ok:
                            data = resp.body()
                            print(f"  📸 превью рилса (og:image, может быть кроп): {len(data)//1024}KB")
                            photo_bytes.append(data)
                    except Exception as e:
                        print(f"  ⚠️ превью рилса: {e}")
            else:
                # --- Карусель ---
                # 1) Всё, что успело прилететь пассивно (слайд 1, часто и слайд 2 —
                #    Instagram предзагружает его сам) уже лежит в image_order.
                if image_order:
                    print(f"  → уже перехвачено при загрузке страницы: {len(image_order)} фото")

                seen_count = len(image_order)

                for slide_num in range(10):
                    # ВАЖНО: ищем кнопку СТРОГО внутри <article> самого поста,
                    # а не по всей странице. Раньше селектор был глобальным
                    # (page.query_selector(...)), и когда карусель поста
                    # реально заканчивалась (кнопки "Далее" внутри поста уже
                    # нет), он находил ПЕРВУЮ попавшуюся кнопку с тем же
                    # aria-label дальше на странице — а это кнопка "Далее" в
                    # блоке рекомендаций/похожих постов внизу страницы.
                    # Скрипт продолжал кликать по ней, и слушатель фото
                    # исправно тянул полноразмерные картинки уже ИЗ ЧУЖИХ
                    # постов — отсюда 9-10 фото вместо 3. article — это DOM-
                    # контейнер именно текущего поста, блок рекомендаций в
                    # него не входит.
                    next_btn = (
                        page.query_selector("article button[aria-label='Далее']")
                        or page.query_selector("article button[aria-label='Next']")
                    )
                    if not next_btn:
                        break

                    # Доп. страховка: кнопка должна быть реально видима на
                    # экране (не скрыта, не detached от DOM). Если Instagram
                    # что-то переверстал и кнопка формально есть в DOM, но не
                    # видна — тоже останавливаемся, а не кликаем вслепую.
                    try:
                        if not next_btn.is_visible():
                            break
                    except Exception:
                        break

                    # Слушатель включаем ТОЛЬКО на время самого клика и короткого
                    # ожидания после него — не раньше и не дольше. Это узкое окно
                    # (обычно 1-6 сек) резко снижает шанс поймать что-то из
                    # ленивой подгрузки рекомендаций, которая может сработать
                    # в произвольный момент пока страница просто открыта.
                    page.on("response", on_image_response)
                    next_btn.click()
                    # ждём не фиксированные 3 сек, а пока сеть по этому слайду не затихнет
                    wait_for_network_quiet(
                        page,
                        size_fn=lambda: sum(len(v) for v in image_chunks.values()),
                        quiet_ms=1200,
                        max_ms=6000,
                    )
                    page.remove_listener("response", on_image_response)

                    if len(image_order) > seen_count:
                        for base in image_order[seen_count:]:
                            print(f"  ➡️ слайд {len(image_chunks)} получен из сети после клика "
                                  f"({len(image_chunks[base])//1024}KB)")
                        seen_count = len(image_order)
                    else:
                        # Нет нового сетевого запроса (фото было в кэше браузера) —
                        # достаём URL из DOM и докачиваем его напрямую.
                        dom_url = page.evaluate("""
                            () => {
                                const imgs = document.querySelectorAll('article img[srcset]');
                                let best = '', bestW = 0;
                                imgs.forEach(img => {
                                    (img.srcset || '').split(',').forEach(part => {
                                        const [url, w] = part.trim().split(' ');
                                        const width = parseInt(w) || 0;
                                        if (width > bestW && url && !url.includes('t51.2885-19')) {
                                            bestW = width; best = url;
                                        }
                                    });
                                });
                                return best;
                            }
                        """)
                        dom_base = dom_url.split("?")[0] if dom_url else ""
                        if dom_url and dom_base not in image_chunks:
                            try:
                                resp = page.request.get(dom_url)
                                data = resp.body()
                                if resp.ok and len(data) > 10_000:
                                    image_chunks[dom_base] = data
                                    image_order.append(dom_base)
                                    seen_count = len(image_order)
                                    print(f"  ➡️ слайд {len(image_chunks)} получен из DOM (кэш): {len(data)//1024}KB")
                                else:
                                    print(f"  ➡️ конец карусели")
                                    break
                            except:
                                print(f"  ➡️ конец карусели")
                                break
                        else:
                            print(f"  ➡️ конец карусели")
                            break

                # Собираем итоговые байты фото строго в порядке слайдов
                photo_bytes = [image_chunks[base] for base in image_order]

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
        print(f"\n📥 Итого постов: {len(posts)}")
        return posts