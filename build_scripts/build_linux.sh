#!/usr/bin/env bash
# Скрипт сборки автономного бинарного файла для Linux
set -e

echo "=== Сборка бинарника Universal Music Saver для Linux ==="
pip install -r requirements.txt pyinstaller

pyinstaller --noconsole \
            --onefile \
            --name "UniversalMusicSaver" \
            --add-data "src:src" \
            app_gui.py

echo "=== Сборка завершена: dist/UniversalMusicSaver ==="
