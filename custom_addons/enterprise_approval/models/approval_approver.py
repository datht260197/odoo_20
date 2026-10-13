# -*- coding: utf-8 -*-
from odoo import models, fields

class ApprovalApprover(models.Model):
    """Dòng người duyệt liên kết với yêu cầu phê duyệt."""

    _name = 'approval.approver'
    _description = 'Người phê duyệt'
    _order = 'sequence, id'

    request_id = fields.Many2one(
        comodel_name='approval.request',
        string='Yêu cầu phê duyệt',
        ondelete='cascade',
        required=True,
        index=True,
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Người duyệt',
        required=True,
    )
    status = fields.Selection(
        selection=[
            ('new', 'Chờ duyệt'),
            ('approved', 'Đã duyệt'),
            ('refused', 'Từ chối'),
            ('cancel', 'Đã hủy'),
        ],
        string='Trạng thái',
        default='new',
        readonly=True,
    )
    sequence = fields.Integer(
        string='Thứ tự',
        default=10,
    )
