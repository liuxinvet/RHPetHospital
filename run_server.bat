@echo off
title RHPetHospital - Local Server
cd /d %~dp0
echo Starting local server...
echo Visit http://127.0.0.1:8080
python app.py
pause
