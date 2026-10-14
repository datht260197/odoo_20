# -*- coding: utf-8 -*-
from odoo import models, fields


class ApprovalSlipPrintWizard(models.TransientModel):
    """Wizard to configure and render the A4 Approval Slip PDF report."""

    _name = 'approval.slip.print.wizard'
    _description = 'Approval Slip Print Configuration Wizard'

    request_id = fields.Many2one(
        comodel_name='approval.request',
        string='Approval Request',
        required=True,
        ondelete='cascade',
    )
    print_watermark = fields.Boolean(
        string='Print Watermark on Drafts',
        default=True,
        help='Display a diagonal draft watermark if the approval request is not yet approved.',
    )
    include_digital_signatures = fields.Boolean(
        string='Include Digital Signatures / OTP Seal',
        default=True,
        help='Include OTP verification seals with signer hashes, timestamps, and emails.',
    )
    include_approval_comments = fields.Boolean(
        string='Include Reviewer Comments',
        default=True,
        help='Include approver feedback and comments in the audit table.',
    )
    custom_notes = fields.Text(
        string='Additional Print Notes',
        help='Optional custom notes or disclaimers printed in the document footer.',
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

