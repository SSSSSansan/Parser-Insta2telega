# 🤖 ESG Instagram → Telegram Bot

Бот автоматически мониторит Instagram-аккаунт [@kbtu_esgcampus](https://www.instagram.com/kbtu_esgcampus/), находит новые посты и публикует их в Telegram-канале. Работает 24/7 без участия человека.

---

## Стек

- **Python 3.12**
- **Playwright** — парсинг Instagram через реальный браузер
- **python-telegram-bot** — отправка в Telegram
- **SQLite** — хранение уже отправленных постов
- **schedule** — запуск каждые 30 минут
- **Docker** — упаковка для деплоя на хостинг

## Поток данных

```
Instagram (@kbtu_esgcampus)
    → Playwright (парсинг постов)
    → SQLite (проверка дубликатов)
    → Telegram-канал (публикация)
```

---

## Структура проекта

```
Parser-Insta2telega/
├── main.py                  # точка входа, планировщик
├── parser.py                # парсинг Instagram через Playwright
├── sender.py                # отправка постов в Telegram
├── database.py              # работа с SQLite
├── config.py                # переменные окружения, восстановление cookies на сервере
├── Dockerfile                # сборка образа для деплоя (Railway)
├── requirements.txt
├── .gitignore
└── README.md

# создаются автоматически при работе, в репозиторий НЕ попадают:
├── instagram_cookies.json   # cookies для авторизации — СЕКРЕТ
├── posts.db                 # SQLite база
└── bot.log                  # логи
```

---

## Установка и запуск локально

### 1. Клонировать репозиторий

```bash
git clone https://github.com/SSSSSansan/Parser-Insta2telega.git
cd Parser-Insta2telega
```

### 2. Создать виртуальное окружение

```bash
python3 -m venv venv
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows
```

### 3. Установить зависимости

```bash
pip install -r requirements.txt
playwright install --with-deps chromium
```

### 4. Создать файл `.env`

```env
TG_BOT_TOKEN=токен_от_BotFather
TG_CHANNEL_ID=@username_канала
IG_USERNAME=kbtu_esgcampus
IG_LOGIN=логин_instagram
IG_PASSWORD=пароль_instagram
```

### 5. Сохранить cookies Instagram

Запусти скрипт — откроется браузер, залогинься вручную, затем нажми Enter в терминале:

```bash
python3 save_cookies.py
```

### 6. Запустить бота

```bash
python3 main.py             # обычный запуск
python3 main.py --dry-run   # тестовый прогон без реальной отправки в канал
```

Бот сразу проверит новые посты и далее будет делать это каждые 30 минут.

---

## Деплой на Railway (24/7 без своего компьютера)

Локально бот работает, пока запущен на твоём компьютере. Чтобы он работал постоянно — деплой на [Railway](https://railway.app):

1. Закодировать cookies для передачи на сервер (на сервере нет браузера, `save_cookies.py` там не запустить):
   ```bash
   base64 -i instagram_cookies.json | tr -d '\n' > cookies_b64.txt
   ```
2. Railway → **New Project → Deploy from GitHub repo** → выбрать этот репозиторий. Railway сам найдёт `Dockerfile` и соберёт образ.
3. **Settings → Variables** — добавить:
   ```
   TG_BOT_TOKEN
   TG_CHANNEL_ID
   IG_USERNAME
   IG_COOKIES_B64     ← содержимое cookies_b64.txt
   DB_PATH            ← /app/data/posts.db (после настройки volume, см. ниже)
   ```
4. **Settings → Volumes** — подключить volume, примонтировать на `/app/data`. Без этого база `posts.db` будет обнуляться при каждом обновлении кода, и бот может повторно отправить в канал уже опубликованные посты.
5. Когда cookies на сервере протухнут — повторить шаг 1 локально и обновить значение `IG_COOKIES_B64` в Railway.

---

## Переменные окружения

| Переменная | Описание |
|---|---|
| `TG_BOT_TOKEN` | Токен бота от @BotFather |
| `TG_CHANNEL_ID` | Username или ID Telegram-канала |
| `IG_USERNAME` | Instagram аккаунт который парсим |
| `IG_LOGIN` | Логин вспомогательного Instagram аккаунта |
| `IG_PASSWORD` | Пароль вспомогательного аккаунта |
| `IG_COOKIES_B64` | Только для деплоя на сервер — cookies в base64 (см. раздел «Деплой») |
| `DB_PATH` | Только для деплоя — путь к базе внутри volume (по умолчанию `posts.db` рядом с кодом) |

---

## Важные замечания

- Файл `instagram_cookies.json` содержит данные сессии — **не загружать в публичный репозиторий**
- Файл `.env` с паролями — **не загружать в репозиторий** (добавлен в `.gitignore`)
- Cookies нужно обновлять раз в несколько недель, если Instagram их сбросит
- Для обновления cookies — снова запустить `save_cookies.py` (локально), затем обновить `IG_COOKIES_B64` на сервере (если задеплоено)
- Для постов-каруселей (несколько фото) публикуется только заглавное фото + ссылка «Открыть в Instagram» на остальные — осознанное решение ради стабильности, а не баг