# =============================================================================
# Auth System - Flask Application Dockerfile
# =============================================================================
# Multi-stage build для минимизации размера образа
# =============================================================================

# --- Stage 1: Builder ---
FROM python:3.10-slim AS builder

WORKDIR /app

# Устанавливаем системные зависимости для сборки
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements и устанавливаем зависимости
# ✅ ИСПРАВЛЕНО: убран --user (несовместим с --prefix)
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Stage 2: Runtime ---
FROM python:3.10-slim AS runtime

# Создаём пользователя для безопасности (не root)
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/logs /app/migrations /app/app/static && \
    chown -R appuser:appuser /app

WORKDIR /app

# Копируем установленные зависимости из builder
# ✅ ИСПРАВЛЕНО: --chown для правильных прав доступа
COPY --from=builder --chown=appuser:appuser /install /usr/local

# Копируем исходный код
COPY --chown=appuser:appuser . .

# Переключаемся на не-root пользователя
USER appuser

# Переменные окружения по умолчанию
ENV FLASK_APP=wsgi.py \
    FLASK_ENV=production \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/usr/local/bin:$PATH" \
    RUNNING_IN_DOCKER=true

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8084/api/health/')" || exit 1

# Порт приложения
EXPOSE 8084

# Команда запуска (Gunicorn)
CMD ["gunicorn", "--workers", "3", "--bind", "0.0.0.0:8084", "--access-logfile", "-", "--error-logfile", "-", "wsgi:app"]
