@echo off
title Khoi dong Odoo 20 Dev Server
chcp 65001 > nul
echo ======================================================================
echo   Đang khởi động Odoo 20 Dev Server...
echo   - Thư mục Custom Addons: D:\github\odoo_20\custom_addons
echo   - Database: odoo_test_db
echo   - Địa chỉ truy cập: http://localhost:8069
echo   - Tài khoản mặc định: admin / admin
echo ======================================================================

REM Tự động mở trình duyệt sau 3 giây
start "" cmd /c "timeout /t 3 /nobreak > nul & start http://localhost:8069"

REM Chạy Odoo với Python virtual environment và file cấu hình odoo.conf
"D:\github\odoo_20\.venv\Scripts\python.exe" "D:\github\odoo_20\odoo-bin" -c "D:\github\odoo_20\odoo.conf" -d odoo_test_db

pause
