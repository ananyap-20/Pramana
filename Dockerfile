FROM python:3.12-slim-bookworm AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never PATH=/app/.venv/bin:$PATH \
    PYTHONPATH=/app/backend TESSERACT_CMD=/usr/bin/tesseract \
    TESSDATA_DIR=/usr/share/tesseract-ocr/5/tessdata OMP_THREAD_LIMIT=1
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv==0.11.25 \
    && useradd --uid 10001 --create-home pramana
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev
COPY backend/app ./backend/app

FROM base AS verification
RUN uv sync --locked --all-groups
COPY backend/tests ./backend/tests
COPY scripts/verify_intake.py ./scripts/verify_intake.py
USER 10001
ENV PRAMANA_ENABLE_LOCAL_INTAKE=1 REQUIRE_REAL_OCR=1
CMD ["python", "-m", "pytest", "-q"]

FROM base AS runtime
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"
# Enable intake only for a disposable demo until the documented release gates pass.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
