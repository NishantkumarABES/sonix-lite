#!/usr/bin/env bash
# Render build script for sonix-lite

set -o errexit  # Exit on error

echo "==== Installing System Dependencies ===="
apt-get update
apt-get install -y ffmpeg

echo "==== Upgrading pip ===="
pip install --upgrade pip

echo "==== Installing Python Dependencies ===="
pip install --no-cache-dir -r requirements.txt

echo "==== Creating Required Directories ===="
mkdir -p storage assets/chunks

echo "==== Build Complete ===="