@echo off
rem RHPetHospital - One-click web version start (Windows)
cd /d %~dp0
echo ==^> Checking dependencies...
pip install -r requirements.txt -q 2>nul
echo ==^> Starting system, visit http://127.0.0.1:8080
python app.py
pause
