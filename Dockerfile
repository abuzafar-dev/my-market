# syntax=docker/dockerfile:1

FROM python:3.14-slim AS builder

WORKDIR /app

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


FROM python:3.14-slim AS runtime

RUN groupadd -r app && useradd -r -g app -m -d /home/app app

WORKDIR /app
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    HOME=/home/app

COPY --from=builder /opt/venv /opt/venv
COPY . .

# collectstatic only reads settings/imports Django apps — it never touches
# the database — so these build-time placeholders just need to satisfy
# decouple's config() calls; the real values come from the container's
# env at runtime (docker-compose.yml / your deploy platform's env vars).
RUN SECRET_KEY=build-time-placeholder \
    DATABASE_URL=postgresql://user:pass@localhost:5432/db \
    ALLOWED_HOSTS=localhost \
    python manage.py collectstatic --noinput

RUN chown -R app:app /home/app && chmod +x docker-entrypoint.sh
USER app

EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
