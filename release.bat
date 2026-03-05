@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================================
echo   Qwen-ASR-GUI Manager - Build ^& Release Script
echo ============================================================
echo.

:: 讀取版本號
set /p VERSION="請輸入版本號 (例如 v1.0.7): "
if "%VERSION%"=="" (
    echo 錯誤：版本號不能為空！
    pause
    exit /b 1
)

:: 讀取 Release 說明
set /p NOTES="請輸入 Release 說明 (可留空): "
if "%NOTES%"=="" set NOTES=Release %VERSION%

echo.
echo   版本號: %VERSION%
echo   說明:   %NOTES%
echo.
set /p CONFIRM="確定要建置並發布嗎？ (y/N): "
if /i not "%CONFIRM%"=="y" (
    echo 已取消。
    pause
    exit /b 0
)

echo.
echo [1/4] 正在使用 PyInstaller 建置...
.venv\Scripts\pyinstaller --noconfirm --onedir --windowed --name "Qwen-ASR-Manager" --add-data "manager;manager" launch.py
if errorlevel 1 (
    echo ❌ PyInstaller 建置失敗！
    pause
    exit /b 1
)
echo ✅ PyInstaller 建置完成

echo.
echo [2/4] 正在壓縮為 zip...
if exist dist\Qwen-ASR-Manager.zip del /f dist\Qwen-ASR-Manager.zip
powershell -Command "Compress-Archive -Path 'dist\Qwen-ASR-Manager' -DestinationPath 'dist\Qwen-ASR-Manager.zip' -Force"
if errorlevel 1 (
    echo ❌ 壓縮失敗！
    pause
    exit /b 1
)
echo ✅ 壓縮完成

echo.
echo [3/4] 正在推送 Git 變更...
git add -A
git commit -m "Release %VERSION%"
git push
echo ✅ Git 推送完成

echo.
echo [4/4] 正在發布 GitHub Release...
gh release create %VERSION% dist\Qwen-ASR-Manager.zip -t "Qwen-ASR-GUI Manager %VERSION%" -n "%NOTES%"
if errorlevel 1 (
    echo ❌ GitHub Release 發布失敗！
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   ✅ Release %VERSION% 發布成功！
echo ============================================================
pause
