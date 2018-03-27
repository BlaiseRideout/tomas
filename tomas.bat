@echo off
reg Query "HKLM\Hardware\Description\System\CentralProcessor\0" | find /i "x86" > NUL && set OS=32bit || set OS=64bit
if %OS%==32bit set path=%path%;%PROGRAMFILES%\tomas;%PROGRAMFILES%\tomas\lib;%USERPROFILE%\Documents\tomas
if %OS%==64bit set path=%path%;%PROGRAMFILES(X86)%\tomas;%PROGRAMFILES(x86)%\tomas\lib;%USERPROFILE%\Documents\tomas
start tomas.exe 5050
timeout /t 3
start "" http://localhost:5050
