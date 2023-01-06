#! /bin/bash

docker buildx build --platform linux/amd64 --load --tag samwelborn/stempy-swelborn:latest-amd64 -f ./docker/Dockerfile.swelborn-full-amd ./docker

docker buildx build --platform linux/arm64 --load --tag samwelborn/stempy-swelborn:latest-arm64 -f ./docker/Dockerfile.swelborn-full-arm ./docker

docker push samwelborn/stempy-swelborn:latest-arm64

docker push samwelborn/stempy-swelborn:latest-amd64
