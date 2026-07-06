FROM python:3.11-slim

WORKDIR /app

# Системные зависимости, нужные Chromium для запуска в headless-режиме
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    wget \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ставим сам браузер Chromium + системные либы под него.
# Это НЕ ставится через pip — отдельный шаг, без него Playwright
# упадёт на сервере с ошибкой "executable doesn't exist".
RUN playwright install --with-deps chromium

COPY . .

CMD ["python3", "main.py"]