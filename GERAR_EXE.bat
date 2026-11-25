@echo off
title GERAR BLACK MACRO MENU EXE
cd /d "%~dp0"

echo ==========================================
echo        BLACK MACRO MENU - GERADOR EXE
echo ==========================================
echo.

where py >nul 2>nul
if errorlevel 1 (
    echo Python nao foi encontrado.
    echo Instale o Python 3 em https://www.python.org/downloads/
    echo Marque a opcao "Add Python to PATH" durante a instalacao.
    pause
    exit /b 1
)

echo [1/3] Instalando dependencias...
py -m pip install --upgrade pip
py -m pip install -r requirements.txt pyinstaller
if errorlevel 1 (
    echo Falha ao instalar dependencias.
    pause
    exit /b 1
)

echo.
echo [2/3] Gerando o executavel...
py -m PyInstaller --noconfirm --clean --onefile --windowed --name BLACK_MACRO_MENU main.py
if errorlevel 1 (
    echo Falha ao gerar o EXE.
    pause
    exit /b 1
)

echo.
echo [3/3] Finalizado!
echo Seu EXE esta na pasta dist:
echo %CD%\dist\BLACK_MACRO_MENU.exe
echo.
pause
