#!/usr/bin/env python3
"""
Universal Music Saver - Консольный интерфейс (CLI).
Удобен для серверов, автоматизаций и пользователей терминала.
"""

import sys
import argparse
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from src.core import download_collection

DEFAULT_OUT = Path.home() / "Music"


def main():
    parser = argparse.ArgumentParser(
        description="Universal Music Saver CLI - Скачивание музыки из VK, Яндекс Музыки, YouTube"
    )
    parser.add_argument("url", help="Ссылка на аудиотеку, альбом или плейлист")
    parser.add_argument(
        "-o", "--output", default=str(DEFAULT_OUT), help="Папка для сохранения файлов"
    )
    parser.add_argument(
        "-b", "--browser", default="opera-gx", help="Браузер для извлечения куки VK (opera-gx, chrome, firefox...)"
    )
    parser.add_argument(
        "-l", "--limit", type=int, default=None, help="Максимальное количество треков для загрузки"
    )
    parser.add_argument(
        "-t", "--token", default=None, help="Опциональный токен Яндекс Музыки (для 320 kbps)"
    )

    args = parser.parse_args()

    download_collection(
        url=args.url,
        output_dir=Path(args.output),
        browser_name=args.browser,
        limit=args.limit,
        yandex_token=args.token,
    )


if __name__ == "__main__":
    main()
