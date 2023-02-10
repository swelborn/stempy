#!/bin/bash

PATH=${HOME}/.local/share/jupyter/kernels/stempy-dask/:$PATH
python -m ipykernel_launcher -f $1
exec "$@"