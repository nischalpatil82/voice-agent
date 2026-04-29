@echo off
echo Installing Voice Agent dependencies from requirements.txt...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
	echo.
	echo Dependency installation failed.
	pause
	exit /b 1
)
echo.
echo Done! Run with:
echo   python main.py --project cravehub
echo   python main.py --project ecommerce
echo   python main.py --project hospital
echo   python main.py --project hotel
echo   python main.py --project justbill
pause
