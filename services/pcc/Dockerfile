FROM dailyco/pipecat-base:latest

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Install Python 3.13 and create venv
RUN uv python install 3.13 \
    && uv venv --python 3.13 --clear /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV UV_PYTHON=/app/.venv/bin/python

# Install dependencies (no dev deps, no project install)
COPY ./pyproject.toml pyproject.toml
COPY ./uv.lock uv.lock
RUN uv sync --locked --no-install-project --no-dev

# Copy application code
COPY ./bot.py bot.py
COPY ./src/ src/

# Copy data directories (resolved via Path(__file__).parent)
COPY ./process_content/ process_content/
COPY ./kb_content/ kb_content/
