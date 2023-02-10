#!/bin/bash
module load cudatoolkit

# Start proxy to srun within Jupyter
export PROXY_SOCKET=${HOME}/.local/share/jupyter/kernels/stempy-dask/proxy.sock
rm -rf ${PROXY_SOCKET}
${HOME}/.local/share/jupyter/kernels/stempy-dask/server.py &
CPID=$!

exec "$@"

kill $CPID