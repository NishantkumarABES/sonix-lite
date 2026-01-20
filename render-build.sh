#!/usr/bin/env bash
set -o errexit

echo "==== Python Version ===="
python --version

echo "==== Upgrading pip ===="
pip install --upgrade pip

echo "==== Installing Python Dependencies ===="
pip install --no-cache-dir -r requirements.txt

echo "==== Creating Required Directories ===="
mkdir -p storage assets/chunks

echo "==== Build Complete ===="
