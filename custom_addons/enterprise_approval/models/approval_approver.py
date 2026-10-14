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
    is_otp_verified = fields.Boolean(
        string='Đã xác thực OTP',
        default=False,
        copy=False,
        help='Đánh dấu dòng phê duyệt đã được xác thực ký số 2FA OTP.',
    )
    otp_verified_email = fields.Char(
        string='Email xác thực',
        readonly=True,
        copy=False,
        help='Địa chỉ email công vụ nhận mã xác thực OTP.',
    )
    signature_hash = fields.Char(
        string='Mã băm chữ ký số',
        readonly=True,
        copy=False,
        help='Mã băm mã hóa SHA-256 đảm bảo tính bất khả chối bỏ của chữ ký.',
    )
    signed_datetime = fields.Datetime(
        string='Thời gian ký số',
        readonly=True,
        copy=False,
        help='Thời điểm thực hiện ký số điện tử (UTC).',
    )


