#!/usr/bin/env python3
"""
Yandex Engine - Модуль взаимодействия с сервисом Яндекс Музыка.
Поддерживает современные плейлисты по UUID, альбомы и отдельные треки.
"""

import re
import requests
from pathlib import Path
from yandex_music import Client

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36"
)


def resolve_yandex_url(url: str):
    """Определяет тип контента Яндекс Музыки по URL."""
    clean_url = url.split("?")[0].strip()

    uuid_match = re.search(r'/playlists/([0-9a-fA-F-]+)', clean_url)
    if uuid_match:
        return "playlist_uuid", uuid_match.group(1)

    canon_match = re.search(r'/users/([^/]+)/playlists/(\d+)', clean_url)
    if canon_match:
        return "playlist_canonical", (canon_match.group(1), int(canon_match.group(2)))

    track_match = re.search(r'/album/(\d+)/track/(\d+)', clean_url)
    if track_match:
        return "track", int(track_match.group(2))

    album_match = re.search(r'/album/(\d+)', clean_url)
    if album_match:
        return "album", int(album_match.group(1))

    return None, None


def fetch_playlist_params_by_uuid(uuid_str: str):
    """Извлекает реальный UID владельца и kind плейлиста по UUID."""
    page_url = f"https://music.yandex.ru/playlists/{uuid_str}"
    headers = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    r = requests.get(page_url, headers=headers, timeout=10)
    uid_match = re.search(r'\"owner\":\{\"uid\":(\d+)', r.text)
    kind_match = re.search(r'\"kind\":(\d+)', r.text)

    if uid_match and kind_match:
        return int(uid_match.group(1)), int(kind_match.group(1))

    raise ValueError(f"Не удалось определить параметры плейлиста по UUID: {uuid_str}")


def get_yandex_tracks_iter(url: str, token: str = None):
    """Генератор треков Яндекс Музыки."""
    client = Client(token=token).init() if token else Client().init()
    content_type, data = resolve_yandex_url(url)

    if not content_type:
        raise ValueError(f"Неподдерживаемый формат ссылки Яндекс Музыки: {url}")

    tracks_list = []

    if content_type == "playlist_uuid":
        owner_id, kind = fetch_playlist_params_by_uuid(data)
        pl = client.users_playlists(kind, owner_id)
        if pl and pl.tracks:
            tracks_list = [t.track for t in pl.tracks if t.track]
    elif content_type == "playlist_canonical":
        owner_id, kind = data
        pl = client.users_playlists(kind, owner_id)
        if pl and pl.tracks:
            tracks_list = [t.track for t in pl.tracks if t.track]
    elif content_type == "album":
        album = client.albums_with_tracks(data)
        if album and album.volumes:
            for vol in album.volumes:
                tracks_list.extend(vol)
    elif content_type == "track":
        res = client.tracks([data])
        if res:
            tracks_list = res

    for idx, t in enumerate(tracks_list, 1):
        artist_name = t.artists[0].name if t.artists else "Неизвестный исполнитель"
        title = t.title or "Без названия"
        if t.version:
            title = f"{title} ({t.version})"
        yield {
            "id": f"ya_{t.id}",
            "artist": artist_name,
            "title": title,
            "track_obj": t,
            "index": idx,
            "duration": t.duration_ms // 1000 if t.duration_ms else 0,
        }


def download_yandex_track(track_obj, output_path: Path) -> bool:
    """Скачивает трек Яндекс Музыки с наилучшим доступным битрейтом."""
    temp_path = output_path.with_name(f".tmp_{output_path.name}")
    try:
        infos = track_obj.get_download_info()
        if not infos:
            return False
        best_info = max(infos, key=lambda x: x.bitrate_in_kbps)
        bitrate = best_info.bitrate_in_kbps

        track_obj.download(str(temp_path), bitrate_in_kbps=bitrate)
        if temp_path.exists() and temp_path.stat().st_size > 10000:
            temp_path.replace(output_path)
            return True
        return False
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        return False
