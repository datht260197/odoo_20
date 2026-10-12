@echo off
chcp 65001 > nul
set MODULE_NAME=%1

if "%MODULE_NAME%"=="" (
    echo ========================================================
    echo Vui lòng truyền tên module cần cài đặt / cập nhật!
    echo Ví dụ: update_module.bat my_test_module
    echo ========================================================
    pause
    exit /b 1
)

echo ========================================================
echo   Đang cài đặt / cập nhật module: %MODULE_NAME% ...
echo ========================================================

"D:\github\odoo_20\.venv\Scripts\python.exe" "D:\github\odoo_20\odoo-bin" -c "D:\github\odoo_20\odoo.conf" -d odoo_test_db -u %MODULE_NAME% -i %MODULE_NAME% --stop-after-init

echo.
echo ========================================================
echo   Hoàn tất cập nhật module %MODULE_NAME%!
echo ========================================================
pause
