# Part of custom_hr_contract. See LICENSE file for full copyright and licensing details.

from datetime import date
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged('post_install', '-at_install')
class TestHrContractVietnamese(TransactionCase):
    """Integration tests for custom_hr_contract module."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.hr_manager = cls.env['res.users'].create({
            'name': 'HR Manager User',
            'login': 'hr_mgr_test',
            'email': 'hr_mgr@example.com',
            'group_ids': [
                (4, cls.env.ref('base.group_user').id),
                (4, cls.env.ref('hr.group_hr_manager').id),
            ],
        })

        cls.employee = cls.env['hr.employee'].with_user(cls.hr_manager).create({
            'name': 'Nguyễn Văn An',
            'identification_id': '001099012345',
            'id_card_date': date(2021, 5, 10),
            'id_card_place': 'Cục Cảnh sát QLHC về TTXH',
            'permanent_street': '123 Đường Lê Lợi',
            'permanent_ward': 'Phường Bến Nghé',
            'permanent_district': 'Quận 1',
            'permanent_city': 'TP. Hồ Chí Minh',
            'temporary_street': '456 Đường Nguyễn Huệ',
            'temporary_ward': 'Phường Bến Thành',
            'temporary_district': 'Quận 1',
            'temporary_city': 'TP. Hồ Chí Minh',
            'tax_id_number': '8012345678',
            'social_insurance_number': '7912345678',
            'contract_category': 'definite',
            'payment_method': 'bank',
            'work_hours_per_day': 8.0,
            'work_days_per_week': 5.0,
            'wage': 20000000.0,
            'allowance_meal': 1000000.0,
            'allowance_transport': 500000.0,
            'allowance_phone': 300000.0,
            'allowance_housing': 2000000.0,
            'allowance_responsibility': 1200000.0,
            'allowance_other': 0.0,
        })

    def test_address_computation(self):
        """Test computed full permanent and temporary addresses."""
        expected_perm = '123 Đường Lê Lợi, Phường Bến Nghé, Quận 1, TP. Hồ Chí Minh'
        self.assertEqual(self.employee.permanent_address, expected_perm)

        expected_temp = '456 Đường Nguyễn Huệ, Phường Bến Thành, Quận 1, TP. Hồ Chí Minh'
        self.assertEqual(self.employee.temporary_address, expected_temp)

    def test_allowances_and_compensation_computation(self):
        """Test total_allowance and total_compensation calculations."""
        # Total allowance = 1000000 + 500000 + 300000 + 2000000 + 1200000 = 5,000,000
        self.assertEqual(self.employee.total_allowance, 5000000.0)
        # Total compensation = 20,000,000 + 5,000,000 = 25,000,000
        self.assertEqual(self.employee.total_compensation, 25000000.0)

    def test_labor_contract_report_values(self):
        """Verify the report parser injects num_to_words_vi and returns correct docs."""
        report_parser = self.env['report.custom_hr_contract.report_labor_contract']
        values = report_parser._get_report_values([self.employee.id])
        self.assertIn('docs', values)
        self.assertIn('num_to_words_vi', values)
        converter = values['num_to_words_vi']
        self.assertEqual(converter(25000000), 'Hai mươi lăm triệu đồng chẵn')

    def test_labor_contract_qweb_rendering(self):
        """Verify that the QWeb template renders without raising any error."""
        report_action = self.env.ref('custom_hr_contract.action_report_hr_labor_contract')
        content, content_type = self.env['ir.actions.report']._render_qweb_html(
            report_action.id, [self.employee.id]
        )
        self.assertTrue(len(content) > 0)
        self.assertEqual(content_type, 'html')
        content_str = content.decode('utf-8')
        self.assertIn('Nguyễn Văn An', content_str)
        self.assertIn('001099012345', content_str)
        self.assertIn('Hai mươi lăm triệu đồng chẵn', content_str)
