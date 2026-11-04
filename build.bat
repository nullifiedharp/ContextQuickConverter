@echo off
REM Builds installer\QuickConvert-Setup-<version>.exe
REM Needs Python 3.10+ from python.org (tick "Add python.exe to PATH").
setlocal
cd /d "%~dp0"

echo [1/5] Setting up Python environment...
if not exist .venv (
    python -m venv .venv || goto :err
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip >nul
pip install -r requirements.txt pyinstaller || goto :err
for /f "delims=" %%v in ('python -c "from quickconvert.formats import APP_VERSION as v; print(v)"') do set "VER=%%v"

echo [2/5] Running tests...
python tests\test_convert.py || echo (some tests failed - see above)

echo [3/5] Building QuickConvert.exe (v%VER%)...
pyinstaller QuickConvert.spec --noconfirm --clean || goto :err

echo [4/5] Generating right-click menu entries...
python tools\make_installer_menus.py || goto :err

echo [5/5] Building installer...
call :findiscc
if not defined ISCC (
  echo Inno Setup not found - installing it with winget...
  winget install -e --id JRSoftware.InnoSetup --accept-package-agreements --accept-source-agreements
  call :findiscc
)
if not defined ISCC (
  echo Could not find Inno Setup 6. Install it from jrsoftware.org and run build.bat again.
  goto :err
)
"%ISCC%" /Q /DAppVersion=%VER% installer\QuickConvert.iss || goto :err

echo.
echo Done: installer\QuickConvert-Setup-%VER%.exe
start "" explorer "%~dp0installer"
pause
exit /b 0

:findiscc
set "ISCC="
for %%p in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe") do (
  if exist "%%~p" set "ISCC=%%~p"
)
exit /b 0

:err
echo.
echo Build failed.
pause
exit /b 1
