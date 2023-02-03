#! /bin/bash

salloc -N 2 -n 8 --gpus-per-task=1 --time=00:30:00 -C gpu -A nstaff --image=samwelborn/stempy-cuda
