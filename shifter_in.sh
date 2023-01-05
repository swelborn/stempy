#! /bin/bash

shifter --image=samwelborn/stempy-mpi:latest-amd64 --volume="/global/homes/s/swelborn/stempy:/source/stempy/" python3 /source/stempy/test_reader.py