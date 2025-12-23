
FROM python:3.11.5-slim-bookworm

# Add curl for healthcheck
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

ARG YOUR_ENV

ENV YOUR_ENV=${YOUR_ENV} \
  PYTHONFAULTHANDLER=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONHASHSEED=random \
  PIP_NO_CACHE_DIR=off \
  PIP_DISABLE_PIP_VERSION_CHECK=on \
  PIP_DEFAULT_TIMEOUT=100 \
  # Poetry's configuration:
  POETRY_NO_INTERACTION=1 \
  POETRY_VIRTUALENVS_CREATE=false \
  POETRY_CACHE_DIR='/var/cache/pypoetry' \
  POETRY_HOME='/usr/local'\
  POETRY_VERSION=1.7.1
  # ^^^
  # Make sure to update it!

# System deps:
RUN curl -sSL https://install.python-poetry.org | python3 -

# Copy only requirements to cache them in docker layer
WORKDIR /code
COPY poetry.lock pyproject.toml /code/

# Project initialization:
RUN poetry install $(test "$YOUR_ENV" == production && echo "--only=main") --no-interaction --no-ansi

# Creating folders, and files for a project:
COPY . /code


EXPOSE 8090
# RUN chmod +x /code/startup.sh

# normalize line endings + exec bit
RUN sed -i 's/\r$//' /code/startup.sh && \
    awk 'NR==1{sub(/^\xef\xbb\xbf/,"")}1' /code/startup.sh > /tmp/s.sh && mv /tmp/s.sh /code/startup.sh && \
    chmod +x /code/startup.sh

# call the interpreter explicitly
CMD ["/bin/sh", "/code/startup.sh"]