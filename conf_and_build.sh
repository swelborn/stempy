#! /bin/bash

cd /source/stempy/

rm -rf ./build

cmake -S . -B ./build -DCMAKE_BUILD_TYPE:STRING=Release -Dstempy_ENABLE_VTKm:BOOL=OFF Dstempy_ENABLE_MPI:BOOL=OFF 

cd build
make -j4

