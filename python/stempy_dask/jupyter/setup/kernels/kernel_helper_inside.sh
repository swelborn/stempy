#!/bin/bash

PATH=/global/homes/s/swelborn/utility/container_proxy/:$PATH
python -m ipykernel_launcher -f $1
exec "$@"