#!/usr/bin/env bash
set -euo pipefail

WAN_DIR="${WAN_HOME:-$HOME/Wan2.2}"
MODEL_DIR="${WAN_CHECKPOINT:-$WAN_DIR/Wan2.2-TI2V-5B}"

if [[ ! -d "$WAN_DIR/.git" ]]; then
  git clone https://github.com/Wan-Video/Wan2.2.git "$WAN_DIR"
fi

python3 -m pip install --upgrade pip
python3 -m pip install -r "$WAN_DIR/requirements.txt"
python3 -m pip install "huggingface_hub[cli]"

if [[ ! -f "$MODEL_DIR/.cache_complete" ]]; then
  huggingface-cli download Wan-AI/Wan2.2-TI2V-5B --local-dir "$MODEL_DIR"
  touch "$MODEL_DIR/.cache_complete"
fi

echo "Wan 2.2 TI2V-5B is ready at $MODEL_DIR"
echo "Enable it with WAN_ENABLED=true and set WAN_HOME=$WAN_DIR"
