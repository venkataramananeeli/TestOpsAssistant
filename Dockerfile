FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN useradd --create-home --uid 10001 appuser

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt

RUN mkdir -p /app/.streamlit
COPY .streamlit/config.toml /app/.streamlit/config.toml
COPY app.py /app/app.py
COPY modules /app/modules
COPY pages /app/pages
COPY assets /app/assets

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; assert urllib.request.urlopen('http://127.0.0.1:8080/_stcore/health', timeout=3).read().decode().strip() == 'ok'"

CMD ["streamlit", "run", "app.py", "--server.address", "0.0.0.0", "--server.port", "8080", "--server.headless", "true"]
