#!/bin/sh
set -e

cd "$( dirname "$0" )"/test

for dir in */ ; do
    echo "test dir ${dir}"
    cd ${dir}
    python3 ../../fnfig.py main.fig
    sh test.sh
    cat ../.gitignore | xargs rm -rf
    cd ..
done
