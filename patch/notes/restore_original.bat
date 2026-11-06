@echo off
rem Restores the original game files.
cd /d "%~dp0"
copy /y backup\BUNDLE-Z.RSF.orig ..\BUNDLE-Z.RSF >nul
del /q ..\version.dll ..\grimjp.ini ..\grimjp.log 2>nul
if exist ..\grimjp rmdir /s /q ..\grimjp
echo Restored original files.
