@echo off
cd /d "%~dp0"
py -3 -m pip install --upgrade pip
if errorlevel 1 goto error
py -3 -m pip install -r requirements.txt
if errorlevel 1 goto error
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name WiltechContaPY app.py
if errorlevel 1 goto error
echo EXE creado en dist\WiltechContaPY.exe
pause
exit /b 0
:error
echo ERROR: revise que Python este instalado y agregado al PATH.
pause
exit /b 1
