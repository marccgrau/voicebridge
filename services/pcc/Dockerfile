FROM dailyco/pipecat-base:latest

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Install Python 3.13 and create venv
RUN uv python install 3.13 \
    && uv venv --python 3.13 --clear /app/.venv
ENV PATH="/app/.venv/bin:$PATH"
ENV UV_PYTHON=/app/.venv/bin/python


COPY ./requirements.txt requirements.txt

# 2) Install deps into the 3.13 venv using uv’s fast pip
RUN uv pip install --python /app/.venv/bin/python -r requirements.txt

# 3) (Optional) If you need the Krisp shim like in the base image, link it into this venv
#    Safe to keep; no-op if /krisp isn't present
RUN VENV_SITE_PACKAGES=$(/app/.venv/bin/python -c "import site; print(site.getsitepackages()[0])") && \
    [ -d /krisp/python/pipecat_ai_krisp ] && ln -sf /krisp/python/pipecat_ai_krisp "${VENV_SITE_PACKAGES}/pipecat_ai_krisp" || true

# Copy application code
COPY ./bot.py bot.py
COPY ./src/ src/

# Copy data directories (resolved via Path(__file__).parent)
COPY ./process_content/ process_content/
COPY ./kb_content/ kb_content/
