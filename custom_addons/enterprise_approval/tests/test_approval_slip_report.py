# -*- coding: utf-8 -*-
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestApprovalSlipReport(TransactionCase):
    """Automated tests for A4 Approval Slip Print Wizard and QWeb PDF Report."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        cls.user_requester = cls.env['res.users'].create({
            'name': 'Requester Diana',
            'login': 'diana_req',
            'email': 'diana@company.com',
            'group_ids': [(6, 0, [cls.env.ref('enterprise_approval.group_approval_user').id])],
        })
        cls.user_approver = cls.env['res.users'].create({
            'name': 'Approver Edward',
            'login': 'edward_app',
            'email': 'edward@company.com',
            'group_ids': [(6, 0, [cls.env.ref('enterprise_approval.group_approval_approver').id])],
        })

        cls.category = cls.env['approval.category'].create({
            'name': 'Asset Disposal',
            'code': 'ASSET_DISP',
            'has_amount': 'optional',
            'has_date': 'no',
            'has_location': 'no',
            'approver_id': cls.user_approver.id,
        })

        cls.request = cls.env['approval.request'].with_user(cls.user_requester).create({
            'title': 'Server Decommission Request',
            'description': '<p>Decommissioning obsolete web server rack #4.</p>',
            'category_id': cls.category.id,
            'approver_id': cls.user_approver.id,
            'amount': 0.0,
            'priority': '2',
        })

    def test_01_action_print_slip_opens_wizard(self):
        """action_print_slip on approval.request returns approval.slip.print.wizard action."""
        action = self.request.action_print_slip()
        self.assertEqual(action.get('res_model'), 'approval.slip.print.wizard')
        self.assertEqual(action.get('context', {}).get('default_request_id'), self.request.id)

    def test_02_print_wizard_generates_report_action_with_data(self):
        """Wizard action_print_slip passes configuration data to ir.actions.report."""
        wizard = self.env['approval.slip.print.wizard'].create({
            'request_id': self.request.id,
            'print_watermark': True,
            'include_digital_signatures': True,
            'include_approval_comments': True,
            'custom_notes': 'Document verified by internal compliance.',
        })

        report_action = wizard.action_print_slip()
        self.assertEqual(report_action.get('type'), 'ir.actions.report')
        self.assertEqual(report_action.get('report_name'), 'enterprise_approval.report_approval_slip_template')

        data = report_action.get('data', {})
        self.assertTrue(data.get('print_watermark'))
        self.assertTrue(data.get('include_digital_signatures'))
        self.assertTrue(data.get('include_approval_comments'))
        self.assertEqual(data.get('custom_notes'), 'Document verified by internal compliance.')

    def test_03_report_parser_values(self):
        """Report parser correctly extracts documents and wizard options."""
        parser = self.env['report.enterprise_approval.report_approval_slip']
        test_data = {
            'print_watermark': False,
            'include_digital_signatures': True,
            'include_approval_comments': False,
            'custom_notes': 'Test notes',
        }
        values = parser._get_report_values(self.request.ids, data=test_data)

        self.assertIn('docs', values)
        self.assertEqual(values['docs'], self.request)
        self.assertFalse(values['print_watermark'])
        self.assertTrue(values['include_digital_signatures'])
        self.assertFalse(values['include_approval_comments'])
        self.assertEqual(values['custom_notes'], 'Test notes')

    def test_04_qweb_pdf_render(self):
        """QWeb PDF report renders successfully for the request."""
        report = self.env.ref('enterprise_approval.action_report_approval_slip')
        test_data = {
            'print_watermark': True,
            'include_digital_signatures': True,
            'include_approval_comments': True,
            'custom_notes': 'Verified A4 layout',
        }
        # Render PDF content
        pdf_content, _ = report._render_qweb_pdf(report.id, res_ids=[self.request.id], data=test_data)
        self.assertTrue(pdf_content)
        self.assertTrue(len(pdf_content) > 100)

