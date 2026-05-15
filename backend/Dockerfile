# ──────────────────────────────────────────────────────────────
# Stage 1 — builder: gets the toolchain to compile any wheels
#                    that lack manylinux releases (uvloop,
#                    pyarrow transitives, etc).
# ──────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /build/requirements.txt

# Install into a relocatable prefix we can copy into the runtime
# stage. The prefix is just a staging area, not the final PATH.
RUN pip install --no-cache-dir --prefix=/install -r /build/requirements.txt

# Strip dead weight from the installed tree before it crosses
# into the runtime image. Numbers measured on this exact tree:
#   pandas/numpy/scipy/matplotlib bundled tests …………… ~70 MB
#   googleapiclient discovery_cache/documents ……………… ~96 MB
#     (offline discovery JSON for google-api-python-client;
#      google-generativeai talks to Gemini via grpc, never
#      calls discovery.build(), so the documents cache is
#      unused. If a future dep does use discovery, drop this
#      line.)
#   bytecode caches and *.pyi stubs ……………………………………… small
RUN find /install -type d \( -name tests -o -name test -o -name testing \) -exec rm -rf {} + 2>/dev/null || true \
 && rm -rf /install/lib/python3.11/site-packages/googleapiclient/discovery_cache/documents \
 && find /install -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true \
 && find /install -type f \( -name '*.pyc' -o -name '*.pyi' \) -delete

# ──────────────────────────────────────────────────────────────
# Stage 2 — runtime: slim image with only the installed site-
#                    packages and the source tree. No gcc, no
#                    apt cache, no pip cache.
# ──────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/backend

WORKDIR /app

COPY --from=builder /install /usr/local

COPY backend /app/backend

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
