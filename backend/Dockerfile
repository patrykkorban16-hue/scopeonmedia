FROM python:3.12.12-slim@sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
WORKDIR /app
COPY requirements.lock .
RUN pip install --require-hashes -r requirements.lock \
 && python -m playwright install --with-deps chromium \
 && rm -rf /var/lib/apt/lists/*
COPY iw_backend ./iw_backend
COPY seeds.json seeds.docker.json ./
RUN python -m iw_backend.demo.make_demo \
 && useradd --create-home --uid 10001 iw && mkdir -p /app/data && chown -R iw /app
USER iw
EXPOSE 8000
CMD ["uvicorn", "iw_backend.api:asgi", "--host", "0.0.0.0", "--port", "8000"]
