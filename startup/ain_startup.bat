@echo off
:: AIN Second Brain - Startup Daemon Integrator
:: Recommended placement: C:\Users\%USERNAME%\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\ain_startup.bat

echo [AIN] Autonomous Intelligence Network - Boot Sequence
cd /d "%~dp0\.."

:: Process daytime queue immediately if there are pending manual inputs
python ain.py queue list
python infinite_research_daemon.py --force-queue-only

:: Determine if we are within the overnight window (22:00 to 07:00)
set HOUR=%time:~0,2%
if "%time:~0,1%"==" " set HOUR=0%time:~1,1%

if %HOUR% GEQ 22 goto overnight
if %HOUR% LSS 7 goto overnight

echo [AIN] Outside overnight crawling window. Exiting boot sequence.
exit /b 0

:overnight
echo [AIN] System rebooted inside overnight window. Resuming crawler...
python infinite_research_daemon.py
exit /b 0
