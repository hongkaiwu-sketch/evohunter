FROM python:3.12-slim

RUN groupadd --system evohunter && \
    useradd --system --no-create-home --gid evohunter evohunter

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir . && \
    mkdir -p /data && \
    chown -R evohunter:evohunter /app /data

USER evohunter

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/')" || exit 1

CMD ["python", "-m", "evohunter", "serve", "--host", "0.0.0.0", "--port", "8000"]
