ARG BASE_IMAGE=public.ecr.aws/docker/library/debian:bookworm-slim@sha256:3783cc01769c7b2b1b83a5c5ad96c815348e28ed7da68e2e3687004faa906251
FROM ${BASE_IMAGE} AS runtime-base
RUN apt-get -o Acquire::Retries=5 update && apt-get -o Acquire::Retries=5 install -y --no-install-recommends \
    ca-certificates libgl1 libegl1 libopengl0 libosmesa6 libxrender1 libxt6 \
    libxext6 libsm6 libice6 libgomp1 libnuma1 \
    && rm -rf /var/lib/apt/lists/*
FROM runtime-base AS paraview
RUN --mount=type=bind,source=paraview.tar.gz,target=/tmp/paraview.tar.gz \
    echo '9979bd1d9794666a6059f5fa5df352eb92ada58d0bd6b3a8a1ba443939293d2b  /tmp/paraview.tar.gz' | sha256sum -c - \
    && mkdir -p /opt/paraview && tar -xzf /tmp/paraview.tar.gz \
    --strip-components=1 -C /opt/paraview
ENV PATH=/opt/paraview/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ENV OMP_NUM_THREADS=2
ENV LP_NUM_THREADS=2
WORKDIR /tmp
CMD ["pvserver", "--bind-address=127.0.0.1", "--timeout=15", "--force-offscreen-rendering", "--opengl-window-backend=OSMesa"]
