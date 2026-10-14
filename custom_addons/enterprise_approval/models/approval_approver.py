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
        string='OTP Verified',
        default=False,
        copy=False,
        help='Indicates whether this approval line was verified and signed via 2FA OTP.',
    )
    otp_verified_email = fields.Char(
        string='Verified Email',
        readonly=True,
        copy=False,
        help='Corporate email address to which the verification OTP was sent.',
    )
    signature_hash = fields.Char(
        string='Digital Signature Hash',
        readonly=True,
        copy=False,
        help='Cryptographic SHA-256 hash ensuring non-repudiation of the approval signature.',
    )
    signed_datetime = fields.Datetime(
        string='Signature Timestamp',
        readonly=True,
        copy=False,
        help='Exact UTC timestamp when the digital signature was executed.',
    )

