@ECHO OFF
SETLOCAL

REM ==================================================
REM Run Auto Action GUI with console visible
REM ==================================================

REM Change to the folder where this CMD file is located
cd /d "%~dp0"

REM Optional: activate virtual environment
REM call venv\Scripts\activate

:main
	call :check_tini
	if errorlevel 1 (
		echo [W] Tool tini not found. Check python directly
		call :check_python
		if errorlevel 1 exit /b 1
		pythonw auto_action.py
	) else (
		tini python=latest && pythonw auto_action.py exit /b 0
	)
	

:check_python
	where python >nul 2>&1
	if errorlevel 1 (
		echo [E] Python not found.
		echo     Install python from https://www.python.org/downloads/
		pause
		exit /b 1
	)
	echo [I] Python found
	exit /b 0

:check_tini
	where tini >nul 2>&1
	exit /b errorlevel
