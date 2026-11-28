FROM python:3.15.1-slim@sha256:533b0b2f9b5d46fd097091cf826f27902f1d6c3bca714b6dc74551356aa97a51
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.lock .
RUN pip install --require-hashes -r requirements.lock
COPY iw_ai ./iw_ai
RUN useradd --create-home --uid 10001 iw
USER iw
EXPOSE 8100
CMD ["uvicorn", "iw_ai.main:app", "--host", "0.0.0.0", "--port", "8100"]
