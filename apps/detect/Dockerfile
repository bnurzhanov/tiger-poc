FROM python:3.14-slim

ARG UV_DEFAULT_INDEX=https://packagefeedproxy.microsoft.io/pypi/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NATIVE_TLS=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/local/bin/python \
    UV_CACHE_DIR=/tmp/uv-cache \
    YOLO_CONFIG_DIR=/tmp/ultralytics \
    HOME=/tmp

WORKDIR /workspace/apps/detect

COPY --from=ghcr.io/astral-sh/uv:0.12.7 /uv /uvx /bin/

RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN --mount=type=cache,target=/tmp/uv-cache \
    uv sync --no-dev --no-install-project --extra fabric --default-index "$UV_DEFAULT_INDEX"

COPY tiger_perception ./tiger_perception
COPY manifests ./manifests
COPY rtsp_yolo.py yolo26n.pt ./

ARG LOCAL_UID=1000
ARG LOCAL_GID=1000

RUN mkdir -p /workspace/data /var/lib/tiger-publisher \
    && chown "${LOCAL_UID}:${LOCAL_GID}" /workspace/data /var/lib/tiger-publisher

USER ${LOCAL_UID}:${LOCAL_GID}

CMD ["uv", "run", "--no-sync", "python", "rtsp_yolo.py", "--manifest", "manifests/cell-a-jeep.yaml"]