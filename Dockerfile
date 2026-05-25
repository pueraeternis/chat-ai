ARG TRITON_VERSION=25.03-py3
FROM nvcr.io/nvidia/tritonserver:${TRITON_VERSION}

# Pin backend to r25.03: `main` moves ahead (e.g. expects newer vLLM APIs) while this image uses vllm==0.11.0.
ARG VLLM_BACKEND_BRANCH=r25.03

RUN --mount=type=cache,target=/var/cache/apt \
    apt-get update && \
    apt-get install -y --no-install-recommends \
        git \
        cmake \
        build-essential \
        libopenblas-dev \
        libomp-dev \
        pipx \
    && rm -rf /var/lib/apt/lists/*

RUN pipx ensurepath

WORKDIR /

COPY requirements.txt /tmp/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r /tmp/requirements.txt

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install numpy==1.26.4 vllm==0.11.0

RUN mkdir -p /opt/tritonserver/backends/vllm \
    && git clone --branch "${VLLM_BACKEND_BRANCH}" --single-branch --depth 1 \
        https://github.com/triton-inference-server/vllm_backend.git /tmp/vllm_backend \
    && cp -r /tmp/vllm_backend/src/* /opt/tritonserver/backends/vllm \
    && git -C /tmp/vllm_backend rev-parse HEAD > /opt/tritonserver/backends/vllm/VCS_REVISION \
    && echo "${VLLM_BACKEND_BRANCH}" > /opt/tritonserver/backends/vllm/VCS_BRANCH

RUN rm -rf /tmp/*

WORKDIR /
