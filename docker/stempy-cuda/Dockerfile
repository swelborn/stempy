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
ARG CONDA_VERSION=py310_22.11.1-1

RUN set -x && \
  UNAME_M="$(uname -m)" && \
  if [ "${UNAME_M}" = "x86_64" ]; then \
  MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-${CONDA_VERSION}-Linux-x86_64.sh"; \
  SHA256SUM="00938c3534750a0e4069499baf8f4e6dc1c2e471c86a59caa0dd03f4a9269db6"; \
  elif [ "${UNAME_M}" = "s390x" ]; then \
  MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-${CONDA_VERSION}-Linux-s390x.sh"; \
  SHA256SUM="a150511e7fd19d07b770f278fb5dd2df4bc24a8f55f06d6274774f209a36c766"; \
  elif [ "${UNAME_M}" = "aarch64" ]; then \
  MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-${CONDA_VERSION}-Linux-aarch64.sh"; \
  SHA256SUM="48a96df9ff56f7421b6dd7f9f71d548023847ba918c3826059918c08326c2017"; \
  elif [ "${UNAME_M}" = "ppc64le" ]; then \
  MINICONDA_URL="https://repo.anaconda.com/miniconda/Miniconda3-${CONDA_VERSION}-Linux-ppc64le.sh"; \
  SHA256SUM="4c86c3383bb27b44f7059336c3a46c34922df42824577b93eadecefbf7423836"; \
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
  /opt/conda/bin/conda clean -afy 

RUN /sbin/ldconfig                                       

FROM base AS stempy

ARG DOCKERFILE_SUBDIR=DOCKERFILE_SUBDIR
ARG PYTHON_VERSION=3.10
WORKDIR /source
COPY . /source/stempy/
ARG CONDA_ENV_DIR=/source/stempy/docker/${DOCKERFILE_SUBDIR}/conda

RUN conda install -c conda-forge mamba -y && \
  mamba env update -n base -f ${CONDA_ENV_DIR}/environment_before.yml                       && \
  mkdir -p /build/stempy                                                                    && \
  cd /build/stempy                                                                          && \
  cd /build/stempy                                                                          && \
  cmake -DCMAKE_BUILD_TYPE:STRING=Release \
  -Dstempy_ENABLE_VTKm:BOOL=OFF \
  -Dstempy_ENABLE_MPI:BOOL=OFF \
  /source/stempy .                                                                          && \
  make -j 16                                                                                && \
  cp -r -L /build/stempy/lib/stempy \                                                   
  /opt/conda/lib/python${PYTHON_VERSION}/site-packages                                 && \
  mamba env update -n base -f ${CONDA_ENV_DIR}/environment_after.yml                                 && \
  rm -rf /source/stempy                                                                     && \
  conda clean -a -y -q

RUN /sbin/ldconfig