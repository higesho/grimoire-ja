@echo off
rem Builds version.dll (32-bit) for Grimoire Japanese rendering.
rem   build.bat       release build -> version.dll
rem   build.bat test  test build (/DGRIMJP_TEST) -> test\version.dll (not for distribution)
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars32.bat" >nul || exit /b 1
cd /d "%~dp0"
set O=obj\release
set OUT=version.dll
set DEF=
if "%1"=="test" (
  set O=obj\test
  set OUT=test\version.dll
  set DEF=/DGRIMJP_TEST
  if not exist test mkdir test
)
if not exist %O% mkdir %O%
rc /nologo /fo %O%\grimjp.res grimjp.rc || exit /b 1
cl /nologo /O2 /Oy- /EHa /MT /LD /utf-8 %DEF% /Fo%O%\ grimjp.cpp %O%\grimjp.res /Fe:%OUT% /link /DEF:version.def /IMPLIB:%O%\version.lib user32.lib gdi32.lib kernel32.lib || exit /b 1
echo BUILD OK %OUT%
