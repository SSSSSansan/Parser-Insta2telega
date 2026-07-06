FROM python:3.11-slim

WORKDIR /app

# Отключаем буферизацию вывода Python — без этого print() в main.py/parser.py
# копится во внутреннем буфере контейнера и не долетает до логов Railway
# в реальном времени (иногда вообще не долетает, пока процесс не упадёт).
ENV PYTHONUNBUFFERED=1

# Системные зависимости, нужные Chromium для запуска в headless-режиме
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    wget \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Ставим сам браузер Chromium + системные либы под него.
# Явно указываем оба варианта: обычный chromium и chromium-headless-shell —
# в headless=True режиме (как у нас в parser.py) Playwright использует
# именно headless-shell, и его не всегда докачивает автоматически при
# запросе просто "chromium". Без этого шага получаем ошибку на сервере:
# "BrowserType.launch: Executable doesn't exist ... chrome-headless-shell".
RUN playwright install --with-deps chromium chromium-headless-shell

COPY . .

CMD ["python3", "-u", "main.py"]