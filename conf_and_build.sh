#! /bin/bash

cd /source/stempy/

rm -rf ./build

cmake -S . -B ./build -DCMAKE_BUILD_TYPE:STRING=Release -Dstempy_ENABLE_VTKm:BOOL=ON -DVTKm_DIR:PATH=/build/vtk-m/lib/cmake/vtkm-1.5 -Dstempy_ENABLE_MPI:BOOL=ON 

cd build
make -j4

