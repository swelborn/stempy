#!/bin/bash
module load cudatoolkit
export PROXY_SOCKET=/global/homes/s/swelborn/.local/share/jupyter/kernels/stempy-cuda-dask/proxy.sock

/global/homes/s/swelborn/utility/container_proxy/server.py &
CPID=$!

exec "$@"

kill $CPID