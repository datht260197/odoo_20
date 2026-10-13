# -*- coding: utf-8 -*-
from odoo import models, fields, api, _

class ApprovalCategory(models.Model):
    """Mô hình danh mục phê duyệt (Ví dụ: Chi phí, Nghỉ phép, Mua sắm, Thuê xe)."""

    _name = 'approval.category'
    _description = 'Loại phê duyệt'
    _order = 'sequence, name'

    name = fields.Char(
        string='Tên loại phê duyệt',
        required=True,
        translate=True,
        help='Tên của danh mục yêu cầu / phê duyệt',
    )
    code = fields.Char(
        string='Mã loại',
        required=True,
        index=True,
        help='Mã viết tắt nhận diện loại phê duyệt (Ví dụ: PAYMENT, LEAVE, PROCUREMENT)',
    )
    sequence = fields.Integer(
        string='Thứ tự hiển thị',
        default=10,
    )
    active = fields.Boolean(
        string='Đang hoạt động',
        default=True,
        help='Bỏ chọn để ẩn danh mục này khỏi danh sách tạo yêu cầu',
    )
    icon = fields.Char(
        string='Biểu tượng (FontAwesome)',
        default='fa-check-square-o',
        help='Tên class FontAwesome (ví dụ: fa-money, fa-car, fa-plane)',
    )
    color = fields.Integer(
        string='Chỉ số màu',
        default=0,
    )
    image = fields.Binary(
        string='Hình ảnh danh mục',
        attachment=True,
        help='Ảnh minh họa cho loại phê duyệt này',
    )
    description = fields.Text(
        string='Mô tả & Hướng dẫn',
        translate=True,
        help='Hướng dẫn cho nhân viên về điều kiện và giấy tờ cần thiết khi tạo loại yêu cầu này',
    )

    # Cấu hình người duyệt
    approver_id = fields.Many2one(
        comodel_name='res.users',
        string='Người duyệt mặc định',
        help='Người dùng được chỉ định phê duyệt khi không có cấu hình đặc thù',
    )
    manager_approval = fields.Boolean(
        string='Quản lý trực tiếp duyệt',
        default=False,
        help='Nếu bật, hệ thống sẽ tự động gán Quản lý trực tiếp của nhân viên làm người duyệt',
    )

    # Cấu hình các trường dữ liệu
    has_amount = fields.Selection(
        selection=[
            ('no', 'Không sử dụng'),
            ('optional', 'Tùy chọn'),
            ('required', 'Bắt buộc'),
        ],
        string='Trường Số tiền / Chi phí',
        default='no',
        required=True,
    )
    has_date = fields.Selection(
        selection=[
            ('no', 'Không sử dụng'),
            ('optional', 'Tùy chọn'),
            ('required', 'Bắt buộc'),
        ],
        string='Trường Thời gian / Khoảng ngày',
        default='optional',
        required=True,
    )
    has_location = fields.Selection(
        selection=[
            ('no', 'Không sử dụng'),
            ('optional', 'Tùy chọn'),
            ('required', 'Bắt buộc'),
        ],
        string='Trường Địa điểm / Lộ trình',
        default='no',
        required=True,
    )

    # Các bước phê duyệt
    stage_ids = fields.One2many(
        comodel_name='approval.workflow.stage',
        inverse_name='category_id',
        string='Các bước phê duyệt',
    )

    # Thống kê
    request_count = fields.Integer(
        string='Số yêu cầu',
        compute='_compute_request_count',
    )

    def _compute_request_count(self):
        request_data = self.env['approval.request']._read_group(
            domain=[('category_id', 'in', self.ids)],
            groupby=['category_id'],
            aggregates=['__count'],
        )
        data_map = {category.id: count for category, count in request_data}
        for rec in self:
            rec.request_count = data_map.get(rec.id, 0)

    def action_view_requests(self):
        """Mở danh sách các phiếu yêu cầu thuộc danh mục này."""
        self.ensure_one()
        return {
            'name': _('Yêu cầu phê duyệt: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'approval.request',
            'view_mode': 'list,kanban,form',
            'domain': [('category_id', '=', self.id)],
            'context': {'default_category_id': self.id},
        }

    def action_create_request(self):
        """Tạo yêu cầu mới trực tiếp từ thẻ danh mục trên Tổng quan."""
        self.ensure_one()
        return {
            'name': _('Tạo yêu cầu phê duyệt mới: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'approval.request',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'context': {
                'default_category_id': self.id,
                'default_title': self.name,
            },
        }
