#!/usr/bin/env bash
echo "Building manylinux1 wheels..."
# Build manylinux1 versions via a Docker CentOS5 image
# See https://github.com/pypa/python-manylinux-demo/blob/master/.travis.yml
mkdir -p /tmp/io
chmod 777 /tmp/io
chgrp docker /tmp/io
rm -rf /tmp/io/*
mkdir -p /tmp/io/src
mkdir -p /tmp/io/test
mkdir -p /tmp/io/wheelhouse
chmod 777 /tmp/io/wheelhouse
chgrp docker /tmp/io/wheelhouse
# Fresh copy everything to the /tmp/io temporary subdirectory,
# expanding symlinks
cp -L ./* /tmp/io
cp -L -r ./src/* /tmp/io/src
cp -L -r ./test/* /tmp/io/test
# Run the Docker image
docker run --rm -it -v /tmp/io:/io quay.io/pypa/manylinux1_x86_64 bash /io/build_wheels.sh
# Copy the finished wheels
mkdir -p ./dist
mv /tmp/io/wheelhouse/reynir* ./dist
