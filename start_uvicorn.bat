@echo off
REM 舆情系统后端启动脚本（局域网可访问版）
REM 固定使用 --host 0.0.0.0，切勿改为 127.0.0.1（否则局域网 IP 不可达）
setlocal
set PY=C:\Users\Administrator\Desktop\YQ\backend\.venv\Scripts\python.exe
set LOG=C:\Users\Administrator\Desktop\YQ\backend\runtime\uvicorn_manual_%%date:~0,4%%%%date:~5,2%%%%date:~8,2%%_%%time:~0,2%%%%time:~3,2%%_%%time:~6,2%%.log
if not exist "C:\Users\Administrator\Desktop\YQ\backend\runtime" mkdir "C:\Users\Administrator\Desktop\YQ\backend\runtime"

echo 正在以 0.0.0.0:8000 启动 uvicorn ...
start "" "%PY%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers > "%LOG%" 2>&1
echo 已启动（日志见 %LOG%）
echo 访问地址: http://127.0.0.1:8000/  或  http://192.168.10.90:8000/
timeout /t 3 >nul
