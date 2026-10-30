FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

ARG REQUIREMENTS=requirements.txt
COPY requirements.txt requirements-dev.txt ./
RUN pip install -r ${REQUIREMENTS}

COPY . .

RUN useradd --create-home app \
    && mkdir -p /app/staticfiles /data/media \
    && chown -R app:app /app /data
USER app

# collectstatic needs settings to import, but not a real secret or database.
RUN SECRET_KEY=build DATABASE_URL=sqlite:////tmp/build.db \
    DJANGO_SETTINGS_MODULE=config.settings.prod \
    python manage.py collectstatic --noinput -v0

ENV MEDIA_ROOT=/data/media
EXPOSE 8000
ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-"]
