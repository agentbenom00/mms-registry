@echo off
rem MMS Registry - Windows build. Needs zig 0.13 (https://ziglang.org): on PATH, or set ZIG to its zig.exe.
rem Output: MidnightSuns\Binaries\Win64\version.dll   (copy the MidnightSuns folder into the game folder)
setlocal
set ROOT=%~dp0
if not defined ZIG set ZIG=zig
set OUT=%ROOT%MidnightSuns\Binaries\Win64
if not exist "%OUT%" mkdir "%OUT%"
pushd "%ROOT%src\proxy"
"%ZIG%" cc -target x86_64-windows-gnu -shared -O2 -s -Wall -Wno-unused-function -Wl,--image-base=0x180000000 -o "%OUT%\version.dll" version.c util.c zlib.c pak.c oodle.c json.c registry.c sync.c version.def
if errorlevel 1 (popd & echo BUILD FAILED & exit /b 1)
popd
if exist "%OUT%\version.lib" del "%OUT%\version.lib"
echo Built %OUT%\version.dll
pause
