# Scripts to run a dask cluster

These files will start up a dask cluster on your allocation. 

Instructions for use:
1. Open jupyterlab
2. Open a terminal
3. Input the following commands:
```sh
chmod +x start_dask.sh start_dask_workers.sh # only once
./start_dask.sh
```
4. This will create a dask cluster. You should see a bunch of output. You can change the settings to make more sense.

`preload_serializers.py` needs to be in the same folder as `start_dask.sh`, owing to some weirdness with serializing data from pybind11.

This should eventually all be taken care of with sensible default configuration in stempy.

`allocate_interactive` is just a utility script for starting up an interactive allocation.