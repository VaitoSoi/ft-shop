FROM ghcr.io/astral-sh/uv:debian-slim

WORKDIR /app
VOLUME /app/file
EXPOSE 8000

ENV ENV=prod
ENV UVICORN_HOST=0.0.0.0
ENV UVICORN_PORT=8000
ENV DB_URL=sqlite+aiosqlite:///file/db.sqlite

COPY ./ /app

RUN uvx ruff check .

RUN uv sync --locked

CMD ["uv", "run", "uvicorn", "main:app"]
