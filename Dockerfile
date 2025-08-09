FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.8.3 \
    POETRY_VIRTUALENVS_IN_PROJECT=true

RUN pip install --no-cache-dir poetry==${POETRY_VERSION}

WORKDIR /app

COPY pyproject.toml ./
RUN poetry install --no-interaction --no-ansi

COPY . .

EXPOSE 9000
CMD ["poetry","run","uvicorn","app.main:app","--host","0.0.0.0","--port","8008"]
