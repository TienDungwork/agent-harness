@echo off
setlocal

echo =====================================================================
echo  HUNG PHU INDUSTRIAL PARK - VMS MULTI-AGENT DEMO
echo  NGROK SECURE INTERNET TUNNEL LAUNCHER
echo =====================================================================
echo.

rem Mac dinh su dung cong 8000 (FastAPI Backend + Web Chat)
rem Hoac truyen cong tuy y qua tham so (vi du: run_ngrok_demo.bat 8080)
set PORT=8000
if not "%~1"=="" set PORT=%~1

rem Kiem tra xem ngrok da duoc cai dat hay chua
where ngrok >nul 2>nul
if errorlevel 1 goto :ngrok_missing

echo [1/3] Kiem tra ket noi ngrok CLI...
ngrok version
if errorlevel 1 goto :ngrok_error

echo [2/3] Dang chuan bi mo tunnel toi cong %PORT%...
echo       - Cong dich vu: http://localhost:%PORT%
echo       - Host Header: localhost:%PORT%
echo       - Dashboard giam sat ngrok local: http://127.0.0.1:4040
echo.
echo [3/3] Dang khoi dong ngrok tunnel...
echo (Nhan Ctrl+C de dung tunnel khi ket thuc demo)
echo =====================================================================
echo.

ngrok http %PORT% --host-header="localhost:%PORT%"
exit /b 0

:ngrok_missing
echo [CANH BAO] Khong tim thay lenh 'ngrok' trong PATH he thong!
echo.
echo Huong dan cai dat ngrok tren Windows:
echo   1. Cai dat qua Windows Package Manager:
echo      winget install ngrok/ngrok
echo   2. Hoac cai dat qua Chocolatey:
echo      choco install ngrok
echo   3. Hoac tai file zip tu: https://ngrok.com/download
echo      giai nen file ngrok.exe vao thu muc nay hoac C:\Windows\System32
echo.
echo Sau khi cai dat, lay authtoken mien phi tai https://dashboard.ngrok.com/get-started/your-authtoken
echo va chay lenh cau hinh:
echo   ngrok config add-authtoken ^<YOUR_AUTHTOKEN^>
echo.
exit /b 1

:ngrok_error
echo [LOI] Khong the thuc thi ngrok CLI!
exit /b 1
