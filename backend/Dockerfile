FROM python:3.12-alpine3.24
COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /usr/local/bin/uv
RUN apk upgrade --no-cache && apk add --no-cache ffmpeg ca-certificates clamav-scanner freshclam libstdc++ \
    && python -m pip install --no-cache-dir --upgrade 'pip>=26.2,<27'
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project \
    && /usr/local/bin/python -m pip uninstall --yes pip \
    && rm -rf /root/.cache/uv /usr/local/bin/uv /usr/local/lib/python3.12/ensurepip
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini ./
RUN addgroup -g 10001 -S shiftproof && adduser -u 10001 -S -G shiftproof shiftproof && mkdir -p /app/data/evidence /app/data/outbox && chown -R shiftproof:shiftproof /app/data
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER shiftproof
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
