#!/bin/bash

cd "$(dirname "$0")"

if [ ! -f "./venv" ]; then
	echo "./venv directory not found. Creating new one and installing dependencies"
	/usr/bin/env python3 -m venv venv
	venv/bin/pip install -r requirements.txt
fi

control_c() {
    exit
}

trap control_c SIGINT

while true; do
    venv/bin/python src/main.py
    echo "Crash found."
    for i in {5..1}; do
        echo  "Restarting in $i"
        sleep 1
    done
done
