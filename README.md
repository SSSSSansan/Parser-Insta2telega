# 🤖 ESG Instagram → Telegram Bot

Бот автоматически мониторит Instagram-аккаунт [@kbtu_esgcampus](https://www.instagram.com/kbtu_esgcampus/), находит новые посты и публикует их в Telegram-канале. Работает 24/7 без участия человека.


---

## Стек

- **Python 3.12**
- **Playwright** — парсинг Instagram через реальный браузер
- **python-telegram-bot** — отправка в Telegram
- **SQLite** — хранение уже отправленных постов
- **schedule** — запуск каждые 30 минут

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
├── config.py                # переменные окружения
├── instagram_cookies.json   # cookies для авторизации 
├── posts.db                 # SQLite база 
├── bot.log                  # логи
├── requirements.txt
└── README.md
```

---

## Установка и запуск

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
playwright install chromium
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
python3 main.py
```

Бот сразу проверит новые посты и далее будет делать это каждые 30 минут.

---

## Переменные окружения

| Переменная | Описание |
|---|---|
| `TG_BOT_TOKEN` | Токен бота от @BotFather |
| `TG_CHANNEL_ID` | Username или ID Telegram-канала |
| `IG_USERNAME` | Instagram аккаунт который парсим |
| `IG_LOGIN` | Логин вспомогательного Instagram аккаунта |
| `IG_PASSWORD` | Пароль вспомогательного аккаунта |

---

## Важные замечания

- Файл `instagram_cookies.json` содержит данные сессии — **не загружать в публичный репозиторий**
- Файл `.env` с паролями — **не загружать в репозиторий** (добавлен в `.gitignore`)
- Cookies нужно обновлять раз в несколько недель если Instagram их сбросит
- Для обновления cookies — снова запустить `save_cookies.py`
