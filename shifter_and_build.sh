#! /bin/bash

MPI=OFF 

shifter --image=samwelborn/stempy-cuda --volume="/global/homes/s/swelborn/stempy_swelborn:/source/stempy/" /source/stempy/conf_and_build.sh