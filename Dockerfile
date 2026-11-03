# Keep the Python version in step with flake.nix and pyproject.toml.
FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.13 /uv /bin/

# A compiler and CMake: llama-cpp-python builds llama.cpp from source.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential cmake \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Dependencies first, in their own layer: code changes don't reinstall them.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-install-project

# The model (~1.1 GB) before the code, for the same reason.
COPY download_model.py ./
RUN python download_model.py

COPY bot/ bot/

VOLUME ["/app/data"]

CMD ["python", "-m", "bot"]
