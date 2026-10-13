# -*- coding: utf-8 -*-
from odoo import models, fields


class ItTicketTemplate(models.Model):
    """Model quản lý các mẫu công việc (template) dựng sẵn cho phiếu hỗ trợ IT."""

    _name = 'it.ticket.template'
    _description = 'IT Ticket Template'
    _order = 'name asc'

    name = fields.Char(
        string='Tên mẫu',
        required=True,
        help='Tên định danh cho mẫu công việc này',
    )
    subject = fields.Char(
        string='Tiêu đề mặc định',
        help='Tiêu đề sẽ được điền tự động vào phiếu khi chọn mẫu này',
    )
    description = fields.Html(
        string='Mô tả chi tiết',
        help='Nội dung mô tả chi tiết công việc, hỗ trợ định dạng HTML',
    )
    priority = fields.Selection(
        selection=[
            ('0', 'Thấp'),
            ('1', 'Bình thường'),
            ('2', 'Cao'),
            ('3', 'Khẩn cấp'),
        ],
        string='Mức độ ưu tiên',
        default='1',
        help='Mức độ ưu tiên mặc định khi áp dụng mẫu này',
    )
    estimated_hours = fields.Float(
        string='Thời gian dự kiến (giờ)',
        digits=(6, 2),
        help='Số giờ dự kiến cần để hoàn thành công việc theo mẫu này',
    )
    active = fields.Boolean(
        string='Đang hoạt động',
        default=True,
        help='Bỏ chọn để ẩn mẫu này khỏi danh sách lựa chọn',
    )
