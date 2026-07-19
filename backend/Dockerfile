FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 启动链：Alembic 迁移 -> 初始化种子数据 -> 启动 uvicorn
# compose 已配置 backend depends_on postgres(healthy)，故此处无需再等待数据库
EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && python scripts/init_db.py && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
