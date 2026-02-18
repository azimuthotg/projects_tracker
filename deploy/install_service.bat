@echo off
:: ============================================================
:: ติดตั้ง Project Tracker เป็น Windows Service ด้วย NSSM
:: รันในฐานะ Administrator
:: ============================================================

:: --- ปรับ path ให้ตรงกับ server จริง ---
set PROJECT_DIR=C:\projects\project_tracker
set VENV_PYTHON=%PROJECT_DIR%\venv\Scripts\python.exe
set SERVICE_NAME=ProjectTracker
set SERVICE_DISPLAY=Project Tracker (Waitress)
set NSSM=C:\nssm\nssm.exe

:: ตรวจสอบว่ารัน Admin หรือยัง
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] กรุณารันในฐานะ Administrator
    pause
    exit /b 1
)

:: ตรวจสอบ NSSM
if not exist "%NSSM%" (
    echo [ERROR] ไม่พบ NSSM ที่ %NSSM%
    echo ดาวน์โหลดได้ที่ https://nssm.cc/download แล้ววางไว้ที่ C:\nssm\
    pause
    exit /b 1
)

echo [1/5] ถอนการติดตั้ง service เดิม (ถ้ามี)...
%NSSM% stop %SERVICE_NAME% 2>nul
%NSSM% remove %SERVICE_NAME% confirm 2>nul

echo [2/5] collectstatic...
"%VENV_PYTHON%" "%PROJECT_DIR%\manage.py" collectstatic --noinput --settings=config.settings.production

echo [3/5] migrate...
"%VENV_PYTHON%" "%PROJECT_DIR%\manage.py" migrate --settings=config.settings.production

echo [4/5] ติดตั้ง NSSM service...
%NSSM% install %SERVICE_NAME% "%VENV_PYTHON%" "%PROJECT_DIR%\deploy\waitress_serve.py"

%NSSM% set %SERVICE_NAME% DisplayName "%SERVICE_DISPLAY%"
%NSSM% set %SERVICE_NAME% Description "Project Plan and Budget Tracking System - NPU Academic Resource Center"
%NSSM% set %SERVICE_NAME% AppDirectory "%PROJECT_DIR%"
%NSSM% set %SERVICE_NAME% AppEnvironmentExtra "DJANGO_SETTINGS_MODULE=config.settings.production"
%NSSM% set %SERVICE_NAME% Start SERVICE_AUTO_START
%NSSM% set %SERVICE_NAME% AppStdout "%PROJECT_DIR%\logs\service_stdout.log"
%NSSM% set %SERVICE_NAME% AppStderr "%PROJECT_DIR%\logs\service_stderr.log"
%NSSM% set %SERVICE_NAME% AppRotateFiles 1
%NSSM% set %SERVICE_NAME% AppRotateOnline 1
%NSSM% set %SERVICE_NAME% AppRotateSeconds 86400
%NSSM% set %SERVICE_NAME% AppRotateBytes 10485760

:: สร้างโฟลเดอร์ logs
if not exist "%PROJECT_DIR%\logs" mkdir "%PROJECT_DIR%\logs"

echo [5/5] เริ่มต้น service...
%NSSM% start %SERVICE_NAME%

echo.
echo ============================================================
echo ติดตั้งสำเร็จ! Service "%SERVICE_NAME%" กำลังทำงาน
echo เข้าใช้งานได้ที่ http://localhost:8000
echo ดู logs ได้ที่ %PROJECT_DIR%\logs\
echo ============================================================
pause
