@echo off
chcp 65001 > nul
echo ===================================================
echo     Universal Music Saver - Сборка Windows .EXE
echo ===================================================

echo [1/3] Установка необходимых библиотек...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt pyinstaller

echo [2/3] Запуск сборщика PyInstaller...
pyinstaller --noconsole ^
            --onefile ^
            --name "UniversalMusicSaver" ^
            --add-data "src;src" ^
            app_gui.py

echo ===================================================
if exist "dist\UniversalMusicSaver.exe" (
    echo [3/3] Сборка УСПЕШНО завершена!
    echo Готовый файл находится в папке: dist\UniversalMusicSaver.exe
) else (
    echo [!] Во время сборки произошла ошибка.
)
echo ===================================================
pause
