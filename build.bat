@echo off
chcp 65001 >nul
rem 配布用の WorkMonitor.exe を dist フォルダに作る
cd /d "%~dp0"
python -m pip install --upgrade -r requirements.txt pyinstaller || goto :error
python -c "import app_icon; app_icon.save_ico('icon.ico')" || goto :error
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name WorkMonitor --icon icon.ico ^
  --hidden-import pystray._win32 ^
  --collect-data sv_ttk ^
  app.py || goto :error
copy /y README.txt dist\ >nul
powershell -NoProfile -Command "Compress-Archive -Path dist\WorkMonitor.exe, dist\README.txt -DestinationPath dist\WorkMonitor.zip -Force" || goto :error
echo.
echo 完成: %~dp0dist\WorkMonitor.zip
pause
exit /b 0

:error
echo ビルドに失敗しました。
pause
exit /b 1
