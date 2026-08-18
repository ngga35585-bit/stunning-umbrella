#!/usr/bin/env bash
set -o errexit
apt-get update && apt-get install -y ffmpeg
python -m pip install --upgrade pip
python -m pip install --retries 10 --timeout 120 -r requirements.txt
