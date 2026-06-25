FROM mcr.microsoft.com/playwright/python:v1.60.0-noble

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 预装 Chromium，便于后续爬虫/截图任务直接复用同一镜像。
RUN playwright install chromium

COPY . .

EXPOSE 8000

CMD ["sh", "-c", "python -c 'from app.config import assert_production_security; assert_production_security()' && python -m alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
