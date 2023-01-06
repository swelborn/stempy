#! /bin/bash

docker buildx build --platform linux/arm64,linux/amd64 -t samwelborn/stempy-reqsonly-cuda:latest -f ./docker/Dockerfile.prereqs-cuda --push ./docker 

# docker buildx build --platform linux/amd64 --load --tag samwelborn/stempy-reqsonly-cuda:latest-amd64 -f ./docker/Dockerfile.prereqs-cuda ./docker

# docker buildx build --platform linux/arm64 --load --tag samwelborn/stempy-reqsonly-cuda:latest-arm64 -f ./docker/Dockerfile.prereqs-cuda ./docker

# docker push samwelborn/stempy-reqsonly-cuda:latest-arm64

# docker push samwelborn/stempy-reqsonly-cuda:latest-amd64
