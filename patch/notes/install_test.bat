@echo off
rem Installs a test build the same way players install the patch (drop-in, original files untouched):
rem   the Japanese archive is built from backup\BUNDLE-Z.RSF.orig + the patch folder, turned into
rem   grimjp\jp_bundle.pat (difference to the original), and version.dll rebuilds it on launch.
rem Usage: install_test.bat [patch_dir]   (default: patch_test)
cd /d "%~dp0"
set PATCH=%1
if "%PATCH%"=="" set PATCH=patch_test
if not exist dist_work mkdir dist_work
python -I tools\grimtool.py build ..\Grimoire.exe backup\BUNDLE-Z.RSF.orig %PATCH% dist_work\BUNDLE-Z.RSF || exit /b 1
rem the game folder keeps the original archive
fc /b backup\BUNDLE-Z.RSF.orig ..\BUNDLE-Z.RSF >nul 2>&1 || copy /y backup\BUNDLE-Z.RSF.orig ..\BUNDLE-Z.RSF >nul
if not exist ..\grimjp mkdir ..\grimjp
python -I tools\make_dist.py backup\BUNDLE-Z.RSF.orig dist_work\BUNDLE-Z.RSF ..\grimjp\jp_bundle.pat || exit /b 1
copy /y dll\version.dll ..\ >nul
copy /y dll\grimjp.ini ..\ >nul
copy /y dll\fonts\misaki8.bin ..\grimjp\ >nul
copy /y dll\fonts\misaki_LICENSE.txt ..\grimjp\ >nul
copy /y dll\ui_strings.txt ..\grimjp\ >nul
copy /y dll\exe_strings.txt ..\grimjp\ >nul
python -I tools\make_fallback.py extracted %PATCH% ..\grimjp\tiny_fallback.txt || exit /b 1
echo Installed (%PATCH%). The Japanese archive is rebuilt into ..\grimjp\cache on the next launch.
