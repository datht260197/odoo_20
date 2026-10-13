# -*- coding: utf-8 -*-
from odoo import models, fields

class ApprovalHistory(models.Model):
    """Ghi nhận nhật ký toàn bộ hành động trên yêu cầu phê duyệt (Audit Trail)."""

    _name = 'approval.history'
    _description = 'Nhật ký phê duyệt'
    _order = 'timestamp desc, id desc'

    request_id = fields.Many2one(
        comodel_name='approval.request',
        string='Yêu cầu phê duyệt',
        required=True,
        ondelete='cascade',
        index=True,
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Người thực hiện',
        default=lambda self: self.env.user,
        required=True,
    )
    action = fields.Selection(
        selection=[
            ('draft', 'Tạo mới'),
            ('submit', 'Gửi duyệt'),
            ('approve', 'Phê duyệt'),
            ('reject', 'Từ chối'),
            ('reset', 'Đặt về nháp'),
            ('cancel', 'Hủy đơn'),
        ],
        string='Hành động',
        required=True,
    )
    timestamp = fields.Datetime(
        string='Thời gian',
        default=fields.Datetime.now,
        required=True,
    )
    comment = fields.Text(
        string='Ghi chú / Phản hồi',
    )
