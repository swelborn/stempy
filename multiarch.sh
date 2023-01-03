#! /bin/bash

docker buildx build --platform linux/arm64,linux/amd64 ./docker/

docker buildx build --platform linux/amd64 --load --tag samwelborn/stempy-mpi:latest-amd64 ./docker/

docker buildx build --platform linux/arm64 --load --tag samwelborn/stempy-mpi:latest-arm64 ./docker/

docker push samwelborn/stempy-mpi:latest-arm64

docker push samwelborn/stempy-mpi:latest-amd64
