# Hướng Dẫn Phát Triển & Kiểm Thử Addon Odoo 20

Môi trường kiểm thử Odoo 20 đã được thiết lập hoàn chỉnh trực tiếp trên máy tính Windows của bạn.

---

## 1. Thông Tin Môi Trường Kiểm Thử

- **Python Runtime:** Python 3.12 (Virtual Environment tại `.venv`)
- **Database:** PostgreSQL 16 (Dịch vụ `postgresql-x64-16` đang chạy)
  - **Database dev:** `odoo_test_db`
  - **PG User/Password:** `odoo` / `odoo` (Port 5432)
- **Tài khoản đăng nhập Odoo:**
  - **Tài khoản:** `admin`
  - **Mật khẩu:** `admin`
- **Địa chỉ xem trên máy tính:** `http://localhost:8069`
- **Thư mục chứa addons tự phát triển:** `d:\github\odoo_20\custom_addons`

---

## 2. Cách Khởi Động Odoo Để Xem Trên Máy Tính

Bạn có thể chạy theo một trong hai cách sau:

### Cách 1: Click đúp vào file `start_odoo.bat` (Tiện nhất)
- Trong thư mục `d:\github\odoo_20`, chỉ cần click đúp chuột vào file [`start_odoo.bat`](file:///d:/github/odoo_20/start_odoo.bat).
- Hệ thống sẽ tự động khởi động server và mở trình duyệt web tới `http://localhost:8069`.

### Cách 2: Chạy lệnh từ Terminal / PowerShell
```powershell
.\start_odoo.bat
# hoặc
.\start_odoo.ps1
```

---

## 3. Quy Trình Tạo Module Mới & Xem Ngay Trên Máy Tính

Mỗi khi bạn muốn tạo một module mới:

1. **Tạo thư mục module** bên trong `custom_addons`:
   ```
   d:\github\odoo_20\custom_addons\<ten_module_moi>\
   ├── __init__.py
   ├── __manifest__.py
   ├── models/
   ├── views/
   └── security/
   ```

2. **Cập nhật và nạp module vào Odoo**:
   - Nếu server đang tắt hoặc muốn cài đặt nhanh: chạy lệnh:
     ```cmd
     update_module.bat <ten_module_moi>
     ```
   - Hoặc khi server đang chạy:
     - Mở trình duyệt `http://localhost:8069`
     - Bật chế độ Nhà phát triển (Developer Mode trong Settings)
     - Vào menu **Apps** -> bấm **Update Apps List** -> Tìm tên module mới của bạn và bấm **Activate / Install**.

3. **Live Reload khi chỉnh sửa code:**
   - Trong file [`odoo.conf`](file:///d:/github/odoo_20/odoo.conf), chế độ `dev_mode = qweb,werkzeug,xml` đã được bật sẵn. Khi bạn sửa các file XML/giao diện, chỉ cần F5 lại trình duyệt là thấy ngay thay đổi mà không cần restart server!

---

## 4. Module Mẫu Đã Tạo Sẵn

Một module mẫu chuẩn Odoo 20 đã được tạo và kích hoạt sẵn:
- Đường dẫn: [`d:\github\odoo_20\custom_addons\my_test_module`](file:///d:/github/odoo_20/custom_addons/my_test_module)
- Khi vào `http://localhost:8069`, bạn sẽ thấy ngay App **My Test App** trên menu chính với đầy đủ view danh sách, form tạo mới và trạng thái quy trình.
