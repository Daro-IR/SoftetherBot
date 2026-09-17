#!/bin/bash
set -e
REPO="${SOFTETHERBOT_REPO:-https://github.com/Daro-IR/SoftetherBot.git}"
TARGET="/opt/softetherbot"
if [ "$EUID" -ne 0 ]; then echo "Usa sudo."; exit 1; fi
apt-get update -qq
apt-get install -y -qq git curl ca-certificates
if [ -d "$TARGET/.git" ]; then git -C "$TARGET" pull --ff-only; else git clone "$REPO" "$TARGET"; fi
cd "$TARGET"
exec bash ./install.sh
