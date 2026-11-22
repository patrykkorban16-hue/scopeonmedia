FROM python:3.15.2-slim@sha256:65a65fc7b30b06cb6df4930fd4650697cb23f4c2698ab81fc87e4b031bc36928
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.lock .
RUN pip install --require-hashes -r requirements.lock
COPY iw_ai ./iw_ai
RUN useradd --create-home --uid 10001 iw
USER iw
EXPOSE 8100
CMD ["uvicorn", "iw_ai.main:app", "--host", "0.0.0.0", "--port", "8100"]
