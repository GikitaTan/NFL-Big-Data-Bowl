#!/bin/zsh
cd -- "$(dirname -- "$0")/.."
python3 attention_lab/server.py --open-browser
