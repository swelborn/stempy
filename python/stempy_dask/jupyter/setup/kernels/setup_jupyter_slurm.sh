#!/bin/bash

mkdir -p ${HOME}/container_proxy
cd ${HOME}/container_proxy
cp /global/common/shared/das/container_proxy/client client
cp /global/common/shared/das/container_proxy/server.py server.py
cp /global/common/shared/das/container_proxy/runner.py runner.py
ln -s ${HOME}/container_proxy/client srun
ln -s ${HOME}/container_proxy/client squeue
ln -s ${HOME}/container_proxy/client sbatch
ln -s ${HOME}/container_proxy/client scontrol