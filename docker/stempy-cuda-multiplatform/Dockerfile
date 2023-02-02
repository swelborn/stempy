FROM nvcr.io/nvidia/cuda:11.7.1-devel-ubuntu22.04 AS base

ENV DEBIAN_FRONTEND noninteractive
WORKDIR /source

RUN apt-get update                                      && \
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

ENV PATH /opt/conda/bin:$PATH

CMD [ "/bin/bash" ]

# Leave these args here to better use the Docker build cache
ARG CONDA_VERSION=py39_22.11.1-1

RUN set -x && \
  UNAME_M="$(uname -m)" && \
  if [ "${UNAME_M}" = "x86_64" ]; then \
  MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-${CONDA_VERSION}-Linux-x86_64.sh"; \
  SHA256SUM="e685005710679914a909bfb9c52183b3ccc56ad7bb84acc861d596fcbe5d28bb"; \
  elif [ "${UNAME_M}" = "s390x" ]; then \
  MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-${CONDA_VERSION}-Linux-s390x.sh"; \
  SHA256SUM="ed6176aa6b52e22d939ea5c0c38f9f3cf52d2519a5d0dcb414936287893a31f9"; \
  elif [ "${UNAME_M}" = "aarch64" ]; then \
  MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-${CONDA_VERSION}-Linux-aarch64.sh"; \
  SHA256SUM="031b6c52060bb75e930846c0a66baa91db8196f0d97fd32f3822c54db6b7c76a"; \
  elif [ "${UNAME_M}" = "ppc64le" ]; then \
  MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-${CONDA_VERSION}-Linux-ppc64le.sh"; \
  SHA256SUM="16cc2d74644cf838d2761723c01172e0b704674317630480902ef429af29bd0b"; \
  fi && \
  wget "${MINICONDA_URL}" -O miniconda.sh -q && \
  echo "${SHA256SUM} miniconda.sh" > shasum && \
  if [ "${CONDA_VERSION}" != "latest" ]; then sha256sum --check --status shasum; fi && \
  mkdir -p /opt && \
  bash miniconda.sh -b -p /opt/conda && \
  rm miniconda.sh shasum && \
  ln -s /opt/conda/etc/profile.d/conda.sh /etc/profile.d/conda.sh && \
  echo ". /opt/conda/etc/profile.d/conda.sh" >> ~/.bashrc && \
  echo "conda activate base" >> ~/.bashrc && \
  find /opt/conda/ -follow -type f -name '*.a' -delete && \
  find /opt/conda/ -follow -type f -name '*.js.map' -delete && \
  /opt/conda/bin/conda clean -afy && \
  /opt/conda/bin/conda install -c conda-forge mamba -y 

RUN /sbin/ldconfig                                       

ARG DOCKERFILE_SUBDIR=DOCKERFILE_SUBDIR
ARG PYTHON_VERSION=3.9
WORKDIR /source
COPY . /source/stempy/
ARG CONDA_ENV_DIR=/source/stempy/docker/${DOCKERFILE_SUBDIR}/conda

RUN conda install -c conda-forge mamba -y && \
  mamba env update -n base -f ${CONDA_ENV_DIR}/environment_before.yml                       && \
  mkdir -p /build/stempy                                                                    && \
  cd /build/stempy                                                                          && \
  cmake -DCMAKE_BUILD_TYPE:STRING=Release \
  -Dstempy_ENABLE_VTKm:BOOL=OFF \
  -Dstempy_ENABLE_MPI:BOOL=OFF \
  /source/stempy .                                                                          && \
  make -j 16                                                                                && \
  cp -r -L /build/stempy/lib/stempy \                                                   
  /opt/conda/lib/python${PYTHON_VERSION}/site-packages

FROM base AS stempy

ARG DOCKERFILE_SUBDIR=DOCKERFILE_SUBDIR
ARG CONDA_ENV_DIR=/source/stempy/docker/${DOCKERFILE_SUBDIR}/conda
RUN mamba env update -n base -f ${CONDA_ENV_DIR}/environment_after.yml                      && \
  rm -rf /source/stempy                                                                     && \
  conda clean -a -y -q

RUN /sbin/ldconfig
