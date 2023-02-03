# How to set up kernels

These files should go under a folder in `${HOME}/.local/share/jupyter/<YOUR KERNEL NAME>/`

We need a kernel.json to specify kernel. 

`kernel_helper_inside.sh` will run the shifter image and start up iPython.

`kernel_helper_outside.sh` starts a proxy server so that srun can be run from within a jupyter notebook.

The server is built using [this repo](https://github.com/swelborn/container_proxy). As of this writing, this is not up-to-date. 

A utility script to set up this server in your home directory can be found in `setup_jupyter_slurm.sh`.