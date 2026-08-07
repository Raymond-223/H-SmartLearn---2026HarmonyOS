@echo off
setlocal EnableExtensions
cd /d "%~dp0"
call "%~dp0backend\start_backend_windows.bat"
exit /b %errorlevel%
