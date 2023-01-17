FROM mambaorg/micromamba:1-jammy-cuda-11.7.1 AS base

ENV DEBIAN_FRONTEND noninteractive
ENV PATH "$MAMBA_ROOT_PREFIX/bin:$PATH"
USER root
WORKDIR /source

RUN apt-get update                                    && \
  apt-get upgrade --yes                               && \
  apt-get install --yes    \
  wget \          
  libeigen3-dev \
  git \
  autoconf \
  automake \
  gcc \
  g++ \
  make \
  gfortran \
  zlib1g-dev \
  libffi-dev \
  apt-transport-https \
  ca-certificates \
  gnupg \
  software-properties-common \
  libhdf5-dev \
  build-essential                                     && \
  apt-get clean all                                   && \
  apt-get clean all                                   && \
  rm -rf /var/lib/apt/lists/*                         && \
  mkdir /build/                                       

FROM base AS stempy

ARG PYTHON_VERSION=3.9
COPY --chown=$MAMBA_USER:$MAMBA_USER ./conda/** ./

# Build stempy
RUN micromamba install -y -n base -f /source/environment_before.yml                         && \
  cd /source                                                                                && \
  git clone --recursive -b dask-cupy https://github.com/swelborn/stempy.git                 && \
  mkdir -p /build/stempy                                                                    && \
  cd /build/stempy                                                                          && \
  cmake -DCMAKE_BUILD_TYPE:STRING=Release \
  -Dstempy_ENABLE_VTKm:BOOL=OFF \
  -Dstempy_ENABLE_MPI:BOOL=OFF \
  /source/stempy .                                                                          && \
  make -j 16                                                                                && \
  cp -r -L /build/stempy/lib/stempy \                                                   
  $MAMBA_ROOT_PREFIX/lib/python${PYTHON_VERSION}/site-packages                                 && \
  rm -rf /source/stempy                                                                     && \
  micromamba install -y -n base -f /source/environment_after.yml                            && \
  micromamba clean -a -y

RUN /sbin/ldconfig