@echo off
cd /d "C:\Users\Administrator\Desktop\YQ\frontend"
start "Vite-Server" /MIN cmd /c "node node_modules\vite\bin\vite.js --port 5173 --host 0.0.0.0"
echo Vite started.
