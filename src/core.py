#!/usr/bin/env python3
"""
Core Engine - Единый диспетчер загрузки и синхронизации.
Автоматически распознает сервис (VK, Яндекс Музыка, YouTube, SoundCloud)
и управляет последовательным сохранением треков.
"""

import sys
import time
from pathlib import Path

# Подключение встроенного или системного FFmpeg
try:
    import static_ffmpeg
    static_ffmpeg.add_paths()
except ImportError:
    pass

import yt_dlp
import vk_api

from .sync_manager import SyncManager, sanitize_filename
from .vk_engine import (
    extract_vk_cookies,
    CookieVkAudio,
    parse_vk_owner_id,
    download_vk_hls_stream,
)
from .yandex_engine import (
    get_yandex_tracks_iter,
    download_yandex_track,
)


def detect_service(url: str) -> str:
    """Определяет сервис по переданному URL."""
    u = url.lower().strip()
    if "music.yandex." in u or "yandex.ru/album" in u:
        return "yandex"
    elif "youtube.com" in u or "youtu.be" in u or "soundcloud.com" in u:
        return "ytdlp"
    elif "vk.com" in u or "vk.ru" in u:
        return "vk"
    return "unknown"


def download_collection(
    url: str,
    output_dir: Path,
    browser_name: str = "opera-gx",
    limit: int = None,
    yandex_token: str = None,
    log_callback=None,
    stop_event=None,
):
    """
    Универсальная процедура скачивания и умной синхронизации.
    :param url: Ссылка на музыку/плейлист
    :param output_dir: Папка для сохранения треков
    :param browser_name: Браузер для извлечения куки VK
    :param limit: Максимальное количество треков для загрузки
    :param yandex_token: Опциональный токен Яндекс Музыки
    :param log_callback: Функция обратного вызова для логирования: callback(text, level)
    :param stop_event: Объект threading.Event() для отслеживания запроса остановки
    """
    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            print(msg)

    def is_stopped():
        return stop_event and stop_event.is_set()

    service = detect_service(url)
    if service == "unknown":
        # Если ссылка без домена, пробуем распознать как VK ID
        if url.isdigit() or url.startswith("id") or url.startswith("audios"):
            service = "vk"
        else:
            log(f"[✗] Неподдерживаемый сервис или некорректная ссылка: {url}")
            return

    sync = SyncManager(output_dir)
    log(f"[*] Сервис: {service.upper()}")
    log(f"[*] Папка: {output_dir}")
    log(f"[*] Режим: Синхронизация (от новых к старым, пропуск существующих)")

    ordered_saved_files = []
    processed_count = 0
    new_downloaded = 0
    skipped_count = 0
    errors_count = 0

    # ==========================
    # 1. ВКОНТАКТЕ (VK)
    # ==========================
    if service == "vk":
        try:
            owner_id = parse_vk_owner_id(url)
            log(f"[*] Считывание cookies VK из браузера: {browser_name}...")
            cookies = extract_vk_cookies(browser_name)
            if not cookies:
                log("[✗] Cookies VK не найдены! Убедитесь, что выполнен вход в браузере.")
                return

            vk_session = vk_api.VkApi()
            for c in cookies:
                vk_session.http.cookies.set(c.name, c.value, domain='.vk.com')
                vk_session.http.cookies.set(c.name, c.value, domain='.vk.ru')

            vk_session.http.headers.update({
                'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Mobile Safari/537.36',
                'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            })

            vka = CookieVkAudio(vk_session, owner_id)
            log(f"[*] Загрузка списка треков для ID {owner_id}...")

            for track in vka.get_iter(owner_id=owner_id):
                if is_stopped():
                    log("\n[!] Процесс остановлен пользователем.")
                    break

                processed_count += 1
                if limit and processed_count > limit:
                    log(f"\n[!] Достигнут установленный лимит в {limit} треков.")
                    break

                artist = track.get('artist', 'Неизвестный исполнитель').strip()
                title = track.get('title', 'Без названия').strip()
                track_id = f"vk_{track.get('owner_id')}_{track.get('id')}"
                m3u8_url = track.get('url', '')

                # Проверка: скачан ли уже трек?
                if sync.is_already_downloaded(track_id, artist, title):
                    log(f"[{processed_count:04d}] [ПРОПУСК] Уже скачан: {artist} - {title}")
                    skipped_count += 1
                    continue

                if not m3u8_url:
                    log(f"[{processed_count:04d}] [ОШИБКА] Нет ссылки на поток: {artist} - {title}")
                    errors_count += 1
                    continue

                filename = f"{processed_count:04d} - {sanitize_filename(artist)} - {sanitize_filename(title)}.mp3"
                dest_file = output_dir / filename

                log(f"[{processed_count:04d}] Скачивание: {filename}...")
                start_t = time.time()
                ok = download_vk_hls_stream(m3u8_url, dest_file, artist, title, processed_count)

                if is_stopped():
                    if dest_file.exists() and dest_file.stat().st_size < 30000:
                        dest_file.unlink()
                    break

                if ok:
                    elapsed = time.time() - start_t
                    size_mb = dest_file.stat().st_size / (1024 * 1024)
                    log(f"    -> OK! ({size_mb:.1f} MB, {elapsed:.1f} сек)")
                    sync.register_downloaded(track_id, artist, title, filename)
                    ordered_saved_files.append(filename)
                    new_downloaded += 1
                else:
                    log(f"    -> Ошибка скачивания аудиопотока!")
                    errors_count += 1

                time.sleep(0.3)

        except Exception as e:
            log(f"\n[✗] Ошибка загрузки VK: {e}")

    # ==========================
    # 2. ЯНДЕКС МУЗЫКА
    # ==========================
    elif service == "yandex":
        try:
            log("[*] Подключение к Яндекс Музыке...")
            for t in get_yandex_tracks_iter(url, token=yandex_token):
                if is_stopped():
                    log("\n[!] Процесс остановлен пользователем.")
                    break

                processed_count += 1
                if limit and processed_count > limit:
                    log(f"\n[!] Достигнут лимит в {limit} треков.")
                    break

                artist = t['artist']
                title = t['title']
                track_id = t['id']

                if sync.is_already_downloaded(track_id, artist, title):
                    log(f"[{processed_count:04d}] [ПРОПУСК] Уже скачан: {artist} - {title}")
                    skipped_count += 1
                    continue

                filename = f"{processed_count:04d} - {sanitize_filename(artist)} - {sanitize_filename(title)}.mp3"
                dest_file = output_dir / filename

                log(f"[{processed_count:04d}] Скачивание: {filename}...")
                start_t = time.time()
                ok = download_yandex_track(t['track_obj'], dest_file)

                if ok:
                    elapsed = time.time() - start_t
                    size_mb = dest_file.stat().st_size / (1024 * 1024)
                    log(f"    -> OK! ({size_mb:.1f} MB, {elapsed:.1f} сек)")
                    sync.register_downloaded(track_id, artist, title, filename)
                    ordered_saved_files.append(filename)
                    new_downloaded += 1
                else:
                    log(f"    -> Ошибка скачивания!")
                    errors_count += 1

                time.sleep(0.2)

        except Exception as e:
            log(f"\n[✗] Ошибка Яндекс Музыки: {e}")

    # ==========================
    # 3. YOUTUBE / SOUNDCLOUD
    # ==========================
    elif service == "ytdlp":
        try:
            log(f"[*] Скачивание через универсальный экстрактор yt-dlp...")
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': str(output_dir / "%(playlist_index&{:04d} - |)s%(artist,uploader)s - %(title)s.%(ext)s"),
                'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '320'}],
                'ignoreerrors': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
        except Exception as e:
            log(f"\n[✗] Ошибка yt-dlp: {e}")

    # Обновление плейлиста M3U8
    if ordered_saved_files:
        sync.update_m3u8_playlist(ordered_saved_files)

    log("\n" + "=" * 60)
    log(f"Итоги синхронизации:")
    log(f"  Всего обработано: {processed_count}")
    log(f"  Скачано новых треков: {new_downloaded}")
    log(f"  Пропущено (уже были): {skipped_count}")
    log(f"  Ошибок: {errors_count}")
    log("=" * 60)
