#!/usr/bin/env python3
"""
Universal Music Saver - Графический интерфейс (GUI).
Кроссплатформенное приложение на CustomTkinter для Linux и Windows.
Поддерживает ВКонтакте, Яндекс Музыку, YouTube Music и SoundCloud.
"""

import sys
import os
import threading
from pathlib import Path
from tkinter import filedialog, messagebox
import customtkinter as ctk

# Подключаем модули проекта
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

from src.core import download_collection, detect_service
from src.vk_engine import AVAILABLE_BROWSERS

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class UniversalMusicSaverApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Universal Music Saver")
        self.geometry("740x700")
        self.minsize(680, 620)

        self.is_downloading = False
        self.stop_event = threading.Event()
        self.download_thread = None

        self._create_widgets()

    def _create_widgets(self):
        # 1. Заголовок
        self.header_label = ctk.CTkLabel(
            self, text="🎵 Universal Music Saver", font=ctk.CTkFont(size=24, weight="bold")
        )
        self.header_label.pack(padx=20, pady=(15, 2))

        self.subtitle_label = ctk.CTkLabel(
            self,
            text="Универсальное скачивание и синхронизация (VK • Яндекс Музыка • YouTube)",
            font=ctk.CTkFont(size=12),
            text_color="gray",
        )
        self.subtitle_label.pack(padx=20, pady=(0, 15))

        # 2. Основная карточка
        self.card = ctk.CTkFrame(self)
        self.card.pack(fill="x", padx=20, pady=5)

        # Поле ссылки + Бэйдж сервиса
        self.url_header_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        self.url_header_frame.pack(fill="x", padx=15, pady=(10, 2))

        self.url_label = ctk.CTkLabel(
            self.url_header_frame, text="Ссылка на музыку или плейлист:", font=ctk.CTkFont(weight="bold")
        )
        self.url_label.pack(side="left")

        self.service_badge = ctk.CTkLabel(
            self.url_header_frame,
            text="[Ожидание ссылки]",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color="#3498db",
        )
        self.service_badge.pack(side="right")

        self.url_entry = ctk.CTkEntry(
            self.card,
            placeholder_text="Вставьте ссылку на VK, Яндекс Музыку, YouTube или SoundCloud...",
            height=35,
        )
        self.url_entry.pack(fill="x", padx=15, pady=(0, 10))
        self.url_entry.bind("<KeyRelease>", self._on_url_changed)

        # Ряд: Выбор браузера (VK) и Папка сохранения
        self.settings_row = ctk.CTkFrame(self.card, fg_color="transparent")
        self.settings_row.pack(fill="x", padx=15, pady=5)

        # Браузер
        self.browser_frame = ctk.CTkFrame(self.settings_row, fg_color="transparent")
        self.browser_frame.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.browser_label = ctk.CTkLabel(self.browser_frame, text="Браузер (для VK cookies):")
        self.browser_label.pack(anchor="w")

        browser_options = [f"{name} ({key})" for key, name in AVAILABLE_BROWSERS]
        self.browser_combo = ctk.CTkComboBox(
            self.browser_frame, values=browser_options, height=32
        )
        self.browser_combo.set(browser_options[0])
        self.browser_combo.pack(fill="x", pady=(2, 0))

        # Папка сохранения
        self.dir_frame = ctk.CTkFrame(self.settings_row, fg_color="transparent")
        self.dir_frame.pack(side="right", fill="x", expand=True)

        self.dir_label = ctk.CTkLabel(self.dir_frame, text="Папка сохранения:")
        self.dir_label.pack(anchor="w")

        self.dir_subframe = ctk.CTkFrame(self.dir_frame, fg_color="transparent")
        self.dir_subframe.pack(fill="x", pady=(2, 0))

        default_downloads = str(Path.home() / "Music")
        self.dir_entry = ctk.CTkEntry(self.dir_subframe, height=32)
        self.dir_entry.insert(0, default_downloads)
        self.dir_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))

        self.dir_btn = ctk.CTkButton(
            self.dir_subframe, text="📁", width=36, height=32, command=self._choose_directory
        )
        self.dir_btn.pack(side="right")

        # Опции количества
        self.options_frame = ctk.CTkFrame(self.card, fg_color="transparent")
        self.options_frame.pack(fill="x", padx=15, pady=(10, 15))

        self.mode_var = ctk.StringVar(value="all")

        self.radio_all = ctk.CTkRadioButton(
            self.options_frame,
            text="Всю музыку (умная синхронизация)",
            variable=self.mode_var,
            value="all",
            command=self._on_mode_change,
        )
        self.radio_all.pack(side="left", padx=(0, 20))

        self.radio_limit = ctk.CTkRadioButton(
            self.options_frame,
            text="Только первые:",
            variable=self.mode_var,
            value="limit",
            command=self._on_mode_change,
        )
        self.radio_limit.pack(side="left", padx=(0, 5))

        self.limit_entry = ctk.CTkEntry(self.options_frame, width=70, height=28)
        self.limit_entry.insert(0, "50")
        self.limit_entry.configure(state="disabled")
        self.limit_entry.pack(side="left", padx=(0, 8))

        self.limit_hint = ctk.CTkLabel(
            self.options_frame, text="треков от новых к старым", text_color="gray"
        )
        self.limit_hint.pack(side="left")

        # 3. Кнопки управления
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.pack(fill="x", padx=20, pady=10)

        self.start_btn = ctk.CTkButton(
            self.btn_frame,
            text="▶ Начать загрузку",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#2ecc71",
            hover_color="#27ae60",
            height=42,
            command=self._start_download,
        )
        self.start_btn.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.stop_btn = ctk.CTkButton(
            self.btn_frame,
            text="⏹ Остановить",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#e74c3c",
            hover_color="#c0392b",
            height=42,
            state="disabled",
            command=self._stop_download,
        )
        self.stop_btn.pack(side="right", fill="x", expand=True)

        # 4. Статус и Прогресс
        self.status_label = ctk.CTkLabel(
            self, text="Готов к работе", anchor="w", font=ctk.CTkFont(size=13)
        )
        self.status_label.pack(fill="x", padx=25, pady=(5, 2))

        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", padx=20, pady=(0, 10))

        # 5. Окно лога
        self.log_textbox = ctk.CTkTextbox(self, font=ctk.CTkFont(family="monospace", size=11))
        self.log_textbox.pack(fill="both", expand=True, padx=20, pady=(0, 15))
        self._log("Universal Music Saver запущен и готов к работе.")

    def _on_url_changed(self, event=None):
        url = self.url_entry.get().strip()
        srv = detect_service(url)
        badges = {
            "vk": ("ВКонтакте (VK)", "#2ecc71"),
            "yandex": ("Яндекс Музыка", "#f39c12"),
            "ytdlp": ("YouTube / SoundCloud", "#e74c3c"),
            "unknown": ("[Ожидание ссылки]", "#95a5a6"),
        }
        name, color = badges.get(srv, ("[Неизвестно]", "#95a5a6"))
        self.service_badge.configure(text=name, text_color=color)

    def _choose_directory(self):
        chosen = filedialog.askdirectory(initialdir=self.dir_entry.get())
        if chosen:
            self.dir_entry.delete(0, "end")
            self.dir_entry.insert(0, chosen)

    def _on_mode_change(self):
        if self.mode_var.get() == "limit":
            self.limit_entry.configure(state="normal")
        else:
            self.limit_entry.configure(state="disabled")

    def _log(self, text):
        self.log_textbox.insert("end", f"{text}\n")
        self.log_textbox.see("end")

    def _start_download(self):
        if self.is_downloading:
            return

        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("Внимание", "Пожалуйста, вставьте ссылку на музыку или плейлист!")
            return

        out_dir = Path(self.dir_entry.get().strip())
        limit = None
        if self.mode_var.get() == "limit":
            try:
                limit = int(self.limit_entry.get().strip())
                if limit <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Ошибка", "Введите корректное число треков!")
                return

        selected_browser = self.browser_combo.get().split("(")[-1].replace(")", "").strip()

        self.is_downloading = True
        self.stop_event.clear()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status_label.configure(text="Подключение к сервису...")
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start()

        self.download_thread = threading.Thread(
            target=self._worker,
            args=(url, out_dir, selected_browser, limit),
            daemon=True,
        )
        self.download_thread.start()

    def _stop_download(self):
        if self.is_downloading:
            self.stop_event.set()
            self.status_label.configure(text="Остановка процесса...")
            self._log("[!] Отправлен сигнал на остановку...")

    def _worker(self, url, out_dir, browser, limit):
        def log_cb(msg):
            self.after(0, lambda m=msg: self._log(m))
            if "Скачивание:" in msg:
                clean_msg = msg.split("...") [0].strip()
                self.after(0, lambda m=clean_msg: self.status_label.configure(text=m))

        try:
            download_collection(
                url=url,
                output_dir=out_dir,
                browser_name=browser,
                limit=limit,
                log_callback=log_cb,
                stop_event=self.stop_event,
            )
            self.after(0, lambda: self.status_label.configure(text="Синхронизация завершена!"))
        except Exception as e:
            self.after(0, lambda m=str(e): self._log(f"[✗] Ошибка: {m}"))
            self.after(0, lambda err=e: messagebox.showerror("Ошибка", f"Произошла ошибка: {err}"))
        finally:
            self.is_downloading = False
            self.after(0, self._on_finish)

    def _on_finish(self):
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(1.0)
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")


def main():
    app = UniversalMusicSaverApp()
    app.mainloop()


if __name__ == "__main__":
    main()
