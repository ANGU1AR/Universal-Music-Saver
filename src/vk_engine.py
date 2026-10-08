#!/usr/bin/env python3
"""
VK Engine - Модуль взаимодействия с аудиозаписями ВКонтакте.
Поддерживает извлечение сессии из браузеров, скачивание HLS и потоков.
"""

import sys
import re
import time
import shutil
import subprocess
from pathlib import Path

# Подключение встроенного или системного FFmpeg
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except ImportError:
    pass

import vk_api
from vk_api.audio import VkAudio, set_cookies_from_list
from yt_dlp.cookies import extract_cookies_from_browser

from .sync_manager import sanitize_filename

AVAILABLE_BROWSERS = [
    ("opera-gx", "Opera GX (Snap / Standard)"),
    ("firefox", "Mozilla Firefox"),
    ("chrome", "Google Chrome"),
    ("chromium", "Chromium"),
    ("brave", "Brave Browser"),
    ("edge", "Microsoft Edge"),
    ("yandex", "Yandex Browser"),
    ("none", "Без куки (только общедоступные)")
]


def resolve_browser_cookie_spec(browser_name: str):
    """Определяет параметры и пути профилей браузеров для Linux и Windows."""
    b = browser_name.lower().strip()
    home = Path.home()

    # Специфика Linux Snap
    if sys.platform.startswith("linux"):
        if b in ("opera-gx", "operagx", "opera_gx", "opera"):
            snap_opera_gx = home / "snap/opera-gx/current/.config/opera-gx"
            if snap_opera_gx.exists():
                return ("opera", str(snap_opera_gx))
            snap_opera = home / "snap/opera/current/.config/opera"
            if snap_opera.exists():
                return ("opera", str(snap_opera))
            return ("opera",)

        if b == "firefox":
            snap_ff = home / "snap/firefox/common/.mozilla/firefox"
            if snap_ff.exists() and not (home / ".mozilla/firefox").exists():
                return ("firefox", str(snap_ff))
            return ("firefox",)

    return (b,)


def extract_vk_cookies(browser_name: str = "opera-gx"):
    """Извлекает cookies ВКонтакте из профиля браузера."""
    cookie_spec = resolve_browser_cookie_spec(browser_name)
    b_name = cookie_spec[0]
    profile = cookie_spec[1] if len(cookie_spec) > 1 else None

    jar = extract_cookies_from_browser(b_name, profile=profile)
    return [c for c in jar if "vk." in c.domain]


class CookieVkAudio(VkAudio):
    """Кастомный класс VkAudio, авторизующийся напрямую через cookies браузера."""
    def __init__(self, vk_session, user_id: int):
        self.user_id = user_id
        self._vk = vk_session
        self.convert_m3u8_links = False
        set_cookies_from_list(self._vk.http.cookies, self.DEFAULT_COOKIES)


def parse_vk_owner_id(url: str) -> int:
    """Извлекает ID владельца из URL (например, audios123456 или vk.com/id123456)."""
    match = re.search(r'audios(-?\d+)', url)
    if match:
        return int(match.group(1))
    digits = re.search(r'(\d+)', url)
    if digits:
        return int(digits.group(1))
    raise ValueError(f"Не удалось определить ID пользователя или группы из ссылки: {url}")


def download_vk_hls_stream(m3u8_url: str, output_path: Path, artist: str, title: str, track_num: int = None) -> bool:
    """Скачивает HLS-поток VK и перекодирует в MP3 (320kbps) с вшитыми тегами."""
    ffmpeg_bin = shutil.which('ffmpeg')
    if not ffmpeg_bin:
        raise RuntimeError("Утилита FFmpeg не найдена!")

    temp_path = output_path.with_name(f".tmp_{output_path.name}")

    cmd = [
        ffmpeg_bin,
        '-y',
        '-loglevel', 'error',
        '-i', m3u8_url,
        '-c:a', 'libmp3lame',
        '-q:a', '0',               # Максимальное качество VBR
        '-id3v2_version', '3',
        '-metadata', f'artist={artist}',
        '-metadata', f'title={title}',
        '-f', 'mp3',
        str(temp_path)
    ]
    if track_num is not None:
        cmd.extend(['-metadata', f'track={track_num}'])

    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode == 0 and temp_path.exists() and temp_path.stat().st_size > 30000:
            temp_path.replace(output_path)
            return True
        else:
            if temp_path.exists():
                temp_path.unlink()
            return False
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        return False
