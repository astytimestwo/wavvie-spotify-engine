@echo off
setlocal enabledelayedexpansion

echo ==========================================
echo    Spotify Playlist Creator Automator
echo ==========================================

:: Check if .env exists, if not, create it
if not exist .env (
    echo [!] .env file not found. Let's set up your API keys.
    set /p cid="Enter your Spotify Client ID: "
    set /p csec="Enter your Spotify Client Secret: "
    echo SPOTIPY_CLIENT_ID='!cid!' > .env
    echo SPOTIPY_CLIENT_SECRET='!csec!' >> .env
    echo SPOTIPY_REDIRECT_URI='http://127.0.0.1:8888/callback' >> .env
    echo.
    echo [+] .env file created successfully!
)

:: Ask for run parameters
echo.
echo [ Run Configuration ]
set /p start="Start Index (default 1): "
if "!start!"=="" set start=1

set /p end="End Index (default all): "
if "!end!"=="" set end=9999

set /p cutoff="Cutoff Date (YYYY-MM-DD, press Enter for last 30 days): "
if "!cutoff!"=="" (
    :: We leave it empty so Python uses its internal dynamic default
    python main.py --start !start! --end !end!
) else (
    python main.py --start !start! --end !end! --cutoff !cutoff!
)

echo.
echo ==========================================
echo    Task Complete!
pause
