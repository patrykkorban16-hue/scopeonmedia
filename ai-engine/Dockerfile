FROM python:3.12.12-slim@sha256:f3fa41d74a768c2fce8016b98c191ae8c1bacd8f1152870a3f9f87d350920b7c
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.lock .
RUN pip install --require-hashes -r requirements.lock
COPY iw_ai ./iw_ai
RUN useradd --create-home --uid 10001 iw
USER iw
EXPOSE 8100
CMD ["uvicorn", "iw_ai.main:app", "--host", "0.0.0.0", "--port", "8100"]
