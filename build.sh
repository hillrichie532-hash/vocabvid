#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "==> Activating venv"
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate

echo "==> Installing build deps"
pip install --upgrade pip > /dev/null
pip install pillow pyinstaller > /dev/null

echo "==> Building VocabVid"
pyinstaller \
    --onefile \
    --windowed \
    --name VocabVid \
    --hidden-import PIL._tkinter_finder \
    vocabvid.py

echo ""
echo "Done. Executable: dist/VocabVid"
echo "Run with: ./dist/VocabVid"
