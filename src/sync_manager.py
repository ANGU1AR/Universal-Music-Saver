#!/usr/bin/env python3
"""
Sync Manager - Умный модуль синхронизации аудиотеки.
Предотвращает повторное скачивание и перезапись уже сохраненных треков,
гарантирует сохранение новых треков в правильном хронологическом порядке
и обновляет плейлист M3U8.
"""

import os
import re
import json
from pathlib import Path


def sanitize_filename(name: str) -> str:
    """Удаляет недопустимые для файловых систем символы."""
    cleaned = re.sub(r'[/\\?%*:|"<>]+', '_', str(name))
    cleaned = re.sub(r'\s+', ' ', cleaned).strip('. ')
    return cleaned[:120] or "track"


def normalize_title(text: str) -> str:
    """Нормализует строку для нечувствительного к регистру сравнения."""
    return re.sub(r'[^a-zA-Zа-яА-Я0-9]', '', str(text).lower())


class SyncManager:
    def __init__(self, download_dir: Path):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.download_dir / "history.json"
        self.history = self._load_history()
        self._scan_existing_files()

    def _load_history(self) -> dict:
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_history(self):
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self.history, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _scan_existing_files(self):
        """Сканирует папку и индексирует существующие файлы MP3."""
        if not self.download_dir.exists():
            return

        for p in self.download_dir.glob("*.mp3"):
            if p.name.startswith(".tmp_"):
                continue
            if p.stat().st_size < 10000:
                continue

            # Пытаемся распарсить '0001 - Artist - Title.mp3' или 'Artist - Title.mp3'
            stem = p.stem
            # Убираем префикс цифр '0001 - ' если есть
            cleaned_stem = re.sub(r'^\d+\s*[-_]\s*', '', stem)
            norm_key = normalize_title(cleaned_stem)

            if norm_key and norm_key not in self.history:
                self.history[norm_key] = {
                    "filename": p.name,
                    "size": p.stat().st_size,
                    "path": str(p),
                }

    def is_already_downloaded(self, track_id: str, artist: str, title: str) -> bool:
        """
        Проверяет, скачан ли уже данный трек.
        Проверка ведется как по ID, так и по нормализованному названию трека.
        """
        norm_key = normalize_title(f"{artist}{title}")

        # 1. Проверка по нормализованному имени
        if norm_key in self.history:
            stored = self.history[norm_key]
            fpath = self.download_dir / stored["filename"]
            if fpath.exists() and fpath.stat().st_size > 10000:
                return True

        # 2. Проверка по track_id
        id_key = f"id_{track_id}"
        if id_key in self.history:
            stored = self.history[id_key]
            fpath = self.download_dir / stored["filename"]
            if fpath.exists() and fpath.stat().st_size > 10000:
                return True

        # 3. Физическая проверка в папке (поиск совпадений в именах файлов)
        safe_artist = sanitize_filename(artist)
        safe_title = sanitize_filename(title)
        expected_part = f"{safe_artist} - {safe_title}".lower()

        for f in self.download_dir.glob("*.mp3"):
            if expected_part in f.name.lower() and f.stat().st_size > 10000:
                self.register_downloaded(track_id, artist, title, f.name)
                return True

        return False

    def register_downloaded(self, track_id: str, artist: str, title: str, filename: str):
        """Регистрирует скачанный трек в базе истории."""
        fpath = self.download_dir / filename
        size = fpath.stat().st_size if fpath.exists() else 0

        info = {
            "filename": filename,
            "artist": artist,
            "title": title,
            "track_id": str(track_id),
            "size": size,
        }

        norm_key = normalize_title(f"{artist}{title}")
        self.history[norm_key] = info
        if track_id:
            self.history[f"id_{track_id}"] = info

        self._save_history()

    def update_m3u8_playlist(self, ordered_filenames: list, playlist_name: str = "Плейлист (От новых к старым).m3u8"):
        """
        Создает или обновляет файл плейлиста M3U8 со строгим порядком от новых к старым.
        Любой медиаплеер (VLC, AIMP, Poweramp, телефон) откроет этот плейлист в точном порядке!
        """
        playlist_path = self.download_dir / playlist_name
        lines = ["#EXTM3U\n"]
        for fn in ordered_filenames:
            fpath = self.download_dir / fn
            if fpath.exists():
                lines.append(f"{fn}\n")

        try:
            with open(playlist_path, "w", encoding="utf-8") as f:
                f.writelines(lines)
        except Exception:
            pass
