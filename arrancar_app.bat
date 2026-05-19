@echo off
cd /d "%~dp0"
echo ⚡ Arrancando BIA Energy — Inteligencia de Compra...
"C:\Users\User\AppData\Local\Programs\Python\Python313\python.exe" -m streamlit run app/main.py --server.port 8501 --server.headless false --browser.gatherUsageStats false
pause
