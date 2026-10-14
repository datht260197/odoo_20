# -*- coding: utf-8 -*-
import hashlib
import secrets
from datetime import timedelta

from odoo import models, fields, exceptions, _


class ApprovalSignatureOtpWizard(models.TransientModel):
    """Wizard for Two-Factor OTP Digital Signature Verification."""

    _name = 'approval.signature.otp.wizard'
    _description = 'Xác thực chữ ký số 2FA OTP'

    request_id = fields.Many2one(
        comodel_name='approval.request',
        string='Phiếu yêu cầu',
        required=True,
        ondelete='cascade',
    )
    approver_id = fields.Many2one(
        comodel_name='approval.approver',
        string='Dòng người duyệt',
        required=True,
        ondelete='cascade',
    )
    otp_input = fields.Char(
        string='Nhập mã OTP 6 chữ số',
        size=6,
        help='Nhập mã xác thực gồm 6 chữ số được gửi tới email công vụ của bạn.',
    )
    approval_comment = fields.Text(
        string='Ý kiến phê duyệt',
        help='Ý kiến đóng góp hoặc ghi chú bổ sung về quyết định phê duyệt.',
    )
    otp_code_hash = fields.Char(
        string='Mã băm OTP',
        readonly=True,
    )
    otp_expiry = fields.Datetime(
        string='Thời hạn OTP',
        readonly=True,
    )

    def action_confirm_signature(self):
        """Verify the entered OTP and execute the digital signature."""
        self.ensure_one()

        now = fields.Datetime.now()
        if not self.otp_expiry or now > self.otp_expiry:
            raise exceptions.UserError(self.env._(
                'Mã OTP đã hết hạn. Vui lòng bấm "Gửi lại mã OTP" để nhận mã xác thực mới.'
            ))

        input_code = (self.otp_input or '').strip()
        if not input_code or len(input_code) != 6:
            raise exceptions.UserError(self.env._('Vui lòng nhập đầy đủ mã xác thực OTP gồm 6 chữ số.'))

        input_hash = hashlib.sha256(input_code.encode('utf-8')).hexdigest()
        if input_hash != self.otp_code_hash:
            raise exceptions.UserError(self.env._(
                'Mã OTP không chính xác. Vui lòng kiểm tra lại mã được gửi vào email hoặc yêu cầu cấp lại mã mới.'
            ))

        # Determine signer email
        signer_user = self.approver_id.user_id
        signer_email = signer_user.email or (signer_user.employee_id and signer_user.employee_id.work_email) or ''

        # Compute cryptographic non-repudiation signature hash
        signed_dt = fields.Datetime.now()
        raw_signature = f"{self.request_id.name}|{signer_user.id}|{signer_email}|{signed_dt.isoformat()}"
        signature_hash = hashlib.sha256(raw_signature.encode('utf-8')).hexdigest()

        # Update approver audit fields
        self.approver_id.write({
            'is_otp_verified': True,
            'otp_verified_email': signer_email,
            'signature_hash': signature_hash,
            'signed_datetime': signed_dt,
        })

        # Progress the approval workflow
        self.request_id._process_approval_after_otp(self.approver_id, comment=self.approval_comment)

        return {'type': 'ir.actions.act_window_close'}

    def action_resend_otp(self):
        """Generate and email a fresh OTP code."""
        self.ensure_one()

        signer_user = self.approver_id.user_id
        reviewer_email = signer_user.email or (signer_user.employee_id and signer_user.employee_id.work_email)
        if not reviewer_email:
            raise exceptions.UserError(self.env._(
                'Người dùng "%(user)s" chưa được cấu hình địa chỉ email công vụ.',
                user=signer_user.name,
            ))

        new_otp = f"{secrets.randbelow(1_000_000):06d}"
        new_hash = hashlib.sha256(new_otp.encode('utf-8')).hexdigest()
        new_expiry = fields.Datetime.now() + timedelta(minutes=10)

        self.write({
            'otp_code_hash': new_hash,
            'otp_expiry': new_expiry,
            'otp_input': False,
        })

        template = self.env.ref('enterprise_approval.mail_template_approval_otp', raise_if_not_found=False)
        if template:
            template.with_context(
                otp_code=new_otp,
                otp_expiry=new_expiry,
                recipient_email=reviewer_email,
                approver_name=signer_user.name,
            ).send_mail(self.request_id.id, force_send=True)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': self.env._('Đã gửi lại mã OTP'),
                'message': self.env._('Mã xác thực OTP mới đã được gửi tới địa chỉ %(email)s.', email=reviewer_email),
                'type': 'info',
                'sticky': False,
                'next': {
                    'type': 'ir.actions.act_window',
                    'res_model': 'approval.signature.otp.wizard',
                    'view_mode': 'form',
                    'res_id': self.id,
                    'target': 'new',
                },
            },
        }
