# -*- coding: utf-8 -*-
from odoo import models, fields


class ApprovalSlipPrintWizard(models.TransientModel):
    """Wizard to configure and render the A4 Approval Slip PDF report."""

    _name = 'approval.slip.print.wizard'
    _description = 'Approval Slip Print Configuration Wizard'

    request_id = fields.Many2one(
        comodel_name='approval.request',
        string='Phiếu yêu cầu',
        required=True,
        ondelete='cascade',
    )
    print_watermark = fields.Boolean(
        string='In mờ Bản dự thảo trên phiếu chưa duyệt',
        default=True,
        help='Hiển thị dòng chữ mờ chéo Bản dự thảo nếu yêu cầu chưa được duyệt hoàn tất.',
    )
    include_digital_signatures = fields.Boolean(
        string='Kèm chữ ký số / Con dấu OTP',
        default=True,
        help='In kèm con dấu xác thực chữ ký OTP cùng mã băm, thời gian và email người ký.',
    )
    include_approval_comments = fields.Boolean(
        string='Kèm ý kiến người phê duyệt',
        default=True,
        help='Bao gồm ý kiến phản hồi của người duyệt trong bảng tiến trình.',
    )
    custom_notes = fields.Text(
        string='Ghi chú in bổ sung',
        help='Nhập các ghi chú hoặc điều khoản bổ sung để in ở chân trang tài liệu.',
    )

    def action_print_slip(self):
        """Pass wizard options to the QWeb report engine and generate the PDF slip."""
        self.ensure_one()
        data = {
            'print_watermark': self.print_watermark,
            'include_digital_signatures': self.include_digital_signatures,
            'include_approval_comments': self.include_approval_comments,
            'custom_notes': self.custom_notes or '',
        }
        return self.env.ref('enterprise_approval.action_report_approval_slip').report_action(
            self.request_id,
            data=data,
            config=False,
        )

