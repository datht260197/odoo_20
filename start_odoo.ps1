# Script khởi động Odoo 20 Dev Server trên Windows PowerShell
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  Đang khởi động Odoo 20 Dev Server..." -ForegroundColor Green
Write-Host "  - Thư mục Custom Addons: D:\github\odoo_20\custom_addons" -ForegroundColor Yellow
Write-Host "  - Database: odoo_test_db" -ForegroundColor Yellow
Write-Host "  - Địa chỉ truy cập: http://localhost:8069" -ForegroundColor Yellow
Write-Host "  - Tài khoản mặc định: admin / admin" -ForegroundColor Yellow
Write-Host "======================================================================" -ForegroundColor Cyan

# Tự động mở trình duyệt sau 3 giây
Start-Job -ScriptBlock {
    Start-Sleep -Seconds 3
    Start-Process "http://localhost:8069"
} | Out-Null

& "D:\github\odoo_20\.venv\Scripts\python.exe" "D:\github\odoo_20\odoo-bin" -c "D:\github\odoo_20\odoo.conf" -d odoo_test_db
