Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "C:\Users\Administrator\Desktop\YQ\frontend"
sh.Run "node node_modules\vite\bin\vite.js --port 5173 --host 127.0.0.1", 0, False
