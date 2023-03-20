cmake -B build -DCMAKE_BUILD_TYPE:STRING=Release -Dstempy_ENABLE_VTKm:BOOL=OFF -Dstempy_ENABLE_MPI:BOOL=ON
cmake --build build -j16