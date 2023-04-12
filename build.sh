cmake -DCMAKE_BUILD_TYPE:STRING=Release -B build  -Dstempy_ENABLE_VTKm:BOOL=OFF -Dstempy_ENABLE_MPI:BOOL=ON -Dstempy_ENABLE_ZMQ:BOOl=ON
cmake --build build -j16