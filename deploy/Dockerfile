# Единый Python-образ для ETL, Streamlit и Telegram-бота.
FROM python:3.12-slim

# Отключаем создание .pyc и буферизацию вывода Python.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Устанавливаем приложение и его зависимости.
# Исходный код размещён в src и описан в pyproject.toml.
COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN python -m pip install --no-cache-dir .

# Файлы, необходимые для ETL, Alembic и интерфейса.
COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY sql/ ./sql/
COPY data/capitals.csv ./data/capitals.csv
COPY data/translations/ ./data/translations/
COPY main.py dashboard.py ./

# Запускаем приложение от непривилегированного пользователя.
RUN useradd --create-home --uid 10001 stormy \
    && mkdir -p /app/data \
    && chown -R stormy:stormy /app

USER stormy

# Команда по умолчанию — Streamlit.
# В Compose переопределим её для ETL и бота.
CMD ["streamlit", "run", "dashboard.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.headless=true"]
