@echo off
chcp 65001 >nul
:: 优先用 PATH 中的 python；找不到再回退到打包时内置的绝对路径，保证换机器也能跑
:: 脚本路径用 %~dp0 指向本 bat 同目录，避免硬编码旧目录导致双击失败
set "PY="
where python >nul 2>nul && set "PY=python"
if not defined PY set "PY=C:\Users\Administrator\.workbuddy\binaries\python\versions\3.14.3\python.exe"
"%PY%" "%~dp0music_prompt_generator.py" -n 5 -e --export txt
pause
