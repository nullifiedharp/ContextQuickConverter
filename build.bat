@echo off
REM Builds dist\QuickConvert\QuickConvert.exe and dist\QuickConvert-win64.zip
REM Needs Python 3.10+ from python.org (tick "Add python.exe to PATH").
setlocal
cd /d "%~dp0"

if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv || goto :fail
)
call .venv\Scripts\activate.bat

echo Installing dependencies...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt pyinstaller || goto :fail

echo Running tests...
python tests\test_convert.py || echo (some tests failed - see above)

echo Building exe...
pyinstaller QuickConvert.spec --noconfirm --clean || goto :fail

echo Zipping...
powershell -NoProfile -Command "Compress-Archive -Path 'dist\QuickConvert' -DestinationPath 'dist\QuickConvert-win64.zip' -Force" || goto :fail

echo.
echo Done:  dist\QuickConvert\QuickConvert.exe
echo        dist\QuickConvert-win64.zip
echo Run QuickConvert.exe and click Install.
pause
exit /b 0

:fail
echo.
echo BUILD FAILED
pause
exit /b 1
