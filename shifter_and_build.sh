#! /bin/bash

MPI=ON 

shifter --image=samwelborn/stempy-mpi:latest-amd64 --volume="/global/homes/s/swelborn/stempy:/source/stempy/" /source/stempy/conf_and_build.sh