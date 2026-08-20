@echo off
setlocal
cd /d "%~dp0"

where pyinstaller >nul 2>nul
if errorlevel 1 (
    echo 正在安装打包工具，请稍候……
    python -m pip install pyinstaller
    if errorlevel 1 (
        echo.
        echo 安装 PyInstaller 失败，请确认本机已安装 Python 3.10 或更高版本。
        pause
        exit /b 1
    )
)

echo 正在生成单文件程序……
pyinstaller --noconfirm --clean --onefile --windowed --name 八爪鱼Token工具 bazhuayu_token_tool.py
if errorlevel 1 (
    echo.
    echo 打包失败。
    pause
    exit /b 1
)

echo.
echo 已生成：%~dp0dist\八爪鱼Token工具.exe
pause
