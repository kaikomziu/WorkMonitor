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
  --add-data "mods\modreadme.txt;mods" --add-data "mods\examples;mods\examples" ^
  app.py || goto :error
copy /y README.txt dist\ >nul
copy /y mods\modreadme.txt dist\ >nul
powershell -NoProfile -Command "Compress-Archive -Path dist\WorkMonitor.exe, dist\README.txt, dist\modreadme.txt -DestinationPath dist\WorkMonitor.zip -Force" || goto :error
echo.
echo 完成: %~dp0dist\WorkMonitor.zip
rem Inno Setup があればインストーラーも作る
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
if exist "%ISCC%" (
  for /f %%v in ('python -c "import core; print(core.APP_VERSION)"') do "%ISCC%" /Q /DMyAppVersion=%%v installer.iss || goto :error
  echo 完成: %~dp0dist\WorkMonitor-Setup.exe
) else (
  echo Inno Setup 6 が見つからないため、インストーラーは作りませんでした。
)
pause
exit /b 0

:error
echo ビルドに失敗しました。
pause
exit /b 1
