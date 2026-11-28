FROM python:3.15.1-slim@sha256:533b0b2f9b5d46fd097091cf826f27902f1d6c3bca714b6dc74551356aa97a51
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
