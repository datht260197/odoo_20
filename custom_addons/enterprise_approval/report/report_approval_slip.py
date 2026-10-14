# -*- coding: utf-8 -*-
from odoo import models, api


class ReportApprovalSlip(models.AbstractModel):
    """QWeb report parser for A4 Approval Slip."""

    _name = 'report.enterprise_approval.report_approval_slip'
    _description = 'A4 Approval Slip Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['approval.request'].browse(docids)
        data = data or {}
        return {
            'doc_ids': docids,
            'doc_model': 'approval.request',
            'docs': docs,
            'data': data,
            'print_watermark': data.get('print_watermark', True),
            'include_digital_signatures': data.get('include_digital_signatures', True),
            'include_approval_comments': data.get('include_approval_comments', True),
            'custom_notes': data.get('custom_notes', ''),
        }
