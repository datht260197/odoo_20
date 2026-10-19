# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrContractWordTemplate(models.Model):
    """Word Template for Dynamic Contract Generation using docxtpl."""

    _name = 'hr.contract.word.template'
    _description = 'Contract Word Template'
    _order = 'name, id'

    name = fields.Char(
        string='Template Name',
        required=True,
        help='Descriptive name for this Word contract template (e.g., Probation Contract, Official Labor Contract).',
    )
    template_file = fields.Binary(
        string='Word Template (.docx)',
        required=True,
        attachment=True,
        help='Raw Microsoft Word .docx template with Jinja2 placeholders (e.g. {{ employee_name }}).',
    )
    filename = fields.Char(
        string='File Name',
        help='Original filename of the uploaded .docx template.',
    )
    description = fields.Text(
        string='Usage & Placeholders',
        help='Guidance on available placeholders and template usage.',
        default="""Danh sách các trường merge khả dụng trong file mẫu .docx:
--------------------------------------------------------------
* Thông tin Nhân viên (Employee Info):
  - {{ employee_name }}: Họ và tên người lao động
  - {{ birthday }}: Ngày tháng năm sinh
  - {{ gender }}: Giới tính (Nam / Nữ)
  - {{ id_card_number }}: Số CCCD / Hộ chiếu
  - {{ id_card_issue_date }}: Ngày cấp CCCD
  - {{ id_card_place }}: Nơi cấp CCCD
  - {{ permanent_address }}: Địa chỉ thường trú
  - {{ current_address }}: Chỗ ở hiện nay / Tạm trú
  - {{ phone }}: Số điện thoại liên hệ
  - {{ email }}: Email cá nhân / công việc

* Thông tin Hợp đồng (Contract Info):
  - {{ contract_name }}: Mã / Số hợp đồng
  - {{ job_title }}: Chức danh / Vị trí công việc
  - {{ department_name }}: Phòng ban / Bộ phận làm việc
  - {{ date_start }}: Ngày bắt đầu hợp đồng
  - {{ date_end }}: Ngày kết thúc hợp đồng
  - {{ trial_period_months }}: Thời gian thử việc (tháng)

* Mức lương & Phụ cấp (Compensation):
  - {{ wage }}: Mức lương chính (định dạng số)
  - {{ wage_in_words }}: Mức lương bằng chữ tiếng Việt
  - {{ allowance_meal }}: Phụ cấp ăn trưa
  - {{ allowance_transport }}: Phụ cấp đi lại
  - {{ allowance_phone }}: Phụ cấp điện thoại
  - {{ allowance_housing }}: Phụ cấp nhà ở
  - {{ allowance_responsibility }}: Phụ cấp trách nhiệm

* Thông tin Doanh nghiệp (Company Info):
  - {{ company_name }}: Tên công ty sử dụng lao động
  - {{ company_address }}: Địa chỉ trụ sở công ty
  - {{ company_tax_id }}: Mã số thuế công ty
  - {{ company_representative }}: Người đại diện theo pháp luật
  - {{ representative_job_title }}: Chức danh người đại diện
""",
    )
    active = fields.Boolean(
        string='Active',
        default=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
        index=True,
    )
