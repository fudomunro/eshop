FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv pip install --system --no-cache .

COPY . .

ENV ESHOP_DB_PATH=/data/eshop.db
EXPOSE 8080

CMD ["python", "-c", "from web import app; app.run(host='0.0.0.0', port=8080)"]
