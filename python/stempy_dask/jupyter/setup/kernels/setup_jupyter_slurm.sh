#!/bin/bash

# Making proxy client available
KERNEL_DIRECTORY=${HOME}/.local/share/jupyter/kernels/stempy-dask/
mkdir -p ${KERNEL_DIRECTORY}
rm -rf ${KERNEL_DIRECTORY}*
cd ${KERNEL_DIRECTORY}
cp /global/common/shared/das/container_proxy/client client
cp /global/common/shared/das/container_proxy/server.py server.py
cp /global/common/shared/das/container_proxy/runner.py runner.py
ln -s ${KERNEL_DIRECTORY}/client srun
ln -s ${KERNEL_DIRECTORY}/client squeue
ln -s ${KERNEL_DIRECTORY}/client sbatch
ln -s ${KERNEL_DIRECTORY}/client scontrol
chmod +x server.py
chmod +x runner.py
chmod +x client

# Making stempy kernel/kernel helpers available

SCRIPT_DIRECTORY=/global/homes/s/swelborn/stempy_swelborn/stempy/python/stempy_dask/jupyter/setup/kernels/
cp ${SCRIPT_DIRECTORY}/kernel_helper_outside.sh kernel_helper_outside.sh
cp ${SCRIPT_DIRECTORY}/kernel_helper_inside.sh kernel_helper_inside.sh
cp ${SCRIPT_DIRECTORY}/kernel.json kernel.json
chmod +x kernel_helper_inside.sh
chmod +x kernel_helper_outside.sh