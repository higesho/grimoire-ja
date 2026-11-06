@echo off
rem Builds version.dll (32-bit) for Grimoire Japanese rendering.
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars32.bat" >nul || exit /b 1
cd /d "%~dp0"
cl /nologo /O2 /Oy- /EHa /MT /LD /utf-8 grimjp.cpp /Fe:version.dll /link /DEF:version.def user32.lib gdi32.lib kernel32.lib || exit /b 1
echo BUILD OK
