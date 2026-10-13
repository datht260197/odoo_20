# -*- coding: utf-8 -*-
from odoo import models, fields

class ApprovalWorkflowStage(models.Model):
    """Một bước trong quy trình phê duyệt đa cấp."""

    _name = 'approval.workflow.stage'
    _description = 'Bước phê duyệt'
    _order = 'sequence, id'

    name = fields.Char(
        string='Tên bước duyệt',
        required=True,
        translate=True,
        help='Ví dụ: Bước 1 - Trưởng bộ phận, Bước 2 - Kế toán trưởng, Bước 3 - Ban Giám đốc',
    )
    sequence = fields.Integer(
        string='Thứ tự',
        default=10,
    )
    category_id = fields.Many2one(
        comodel_name='approval.category',
        string='Loại phê duyệt',
        required=True,
        ondelete='cascade',
    )
    approver_id = fields.Many2one(
        comodel_name='res.users',
        string='Người duyệt chỉ định',
        help='Chỉ định người dùng cụ thể phê duyệt ở bước này',
    )
    approver_group_id = fields.Many2one(
        comodel_name='res.groups',
        string='Nhóm người duyệt',
        help='Bất kỳ thành viên nào thuộc nhóm này đều có thể duyệt ở bước này',
    )
    manager_approval = fields.Boolean(
        string='Quản lý trực tiếp',
        default=False,
        help='Tự động gán Quản lý trực tiếp của người tạo yêu cầu làm người duyệt',
    )
