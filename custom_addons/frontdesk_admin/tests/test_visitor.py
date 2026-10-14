from unittest.mock import patch

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestFrontdeskVisitor(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env['res.company'].create({'name': 'Subsidiary Company B'})

        # Groups
        cls.group_user = cls.env.ref('frontdesk_admin.group_frontdesk_user')
        cls.group_officer = cls.env.ref('frontdesk_admin.group_frontdesk_officer')
        cls.group_manager = cls.env.ref('frontdesk_admin.group_frontdesk_manager')

        # Host User & Employee (Company A)
        cls.user_host = cls.env['res.users'].create({
            'name': 'Host User',
            'login': 'host_user_visitor',
            'email': 'host@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, cls.group_user.id])],
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
        })
        cls.employee_host = cls.env['hr.employee'].create({
            'name': 'Host Employee',
            'user_id': cls.user_host.id,
            'work_email': 'host@example.com',
            'company_id': cls.company_a.id,
        })

        # Other User & Employee (Company A)
        cls.user_other = cls.env['res.users'].create({
            'name': 'Other User',
            'login': 'other_user_visitor',
            'email': 'other@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, cls.group_user.id])],
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
        })
        cls.employee_other = cls.env['hr.employee'].create({
            'name': 'Other Employee',
            'user_id': cls.user_other.id,
            'work_email': 'other@example.com',
            'company_id': cls.company_a.id,
        })

        # Frontdesk Officer User (Company A)
        cls.user_officer = cls.env['res.users'].create({
            'name': 'Frontdesk Officer',
            'login': 'officer_user_visitor',
            'email': 'officer@example.com',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.group_user.id,
                cls.group_officer.id,
            ])],
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
        })

        # Frontdesk Manager User (Company A)
        cls.user_manager = cls.env['res.users'].create({
            'name': 'Frontdesk Manager',
            'login': 'manager_user_visitor',
            'email': 'manager@example.com',
            'group_ids': [(6, 0, [
                cls.env.ref('base.group_user').id,
                cls.group_user.id,
                cls.group_officer.id,
                cls.group_manager.id,
            ])],
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
        })

        # Employee with no user account
        cls.employee_no_user = cls.env['hr.employee'].create({
            'name': 'No User Employee',
            'work_email': 'nouser@example.com',
            'company_id': cls.company_a.id,
        })

        # User & Employee with no work email
        cls.user_no_email = cls.env['res.users'].create({
            'name': 'No Email User',
            'login': 'no_email_user_visitor',
            'email': 'noemail@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, cls.group_user.id])],
            'company_id': cls.company_a.id,
            'company_ids': [(6, 0, [cls.company_a.id])],
        })
        cls.employee_no_email = cls.env['hr.employee'].create({
            'name': 'No Email Employee',
            'user_id': cls.user_no_email.id,
            'work_email': False,
            'company_id': cls.company_a.id,
        })

    def test_01_visitor_lifecycle_and_timestamps(self):
        """Test full visitor state machine: draft -> arrived -> departed -> cancelled."""
        visitor = self.env['frontdesk.visitor'].with_user(self.user_officer).create({
            'name': 'John Doe',
            'company_name': 'Acme Corp',
            'phone': '+123456789',
            'email': 'john@acme.com',
            'purpose': 'Quarterly Business Review',
            'host_id': self.employee_host.id,
            'room_name': 'Meeting Room 1',
        })

        self.assertEqual(visitor.state, 'draft')
        self.assertFalse(visitor.checkin_time)
        self.assertFalse(visitor.checkout_time)

        # Check-in
        with patch.object(type(visitor), 'message_notify') as mock_notify, \
             patch.object(type(self.env['mail.template']), 'send_mail') as mock_send_mail:
            visitor.action_checkin()

        self.assertEqual(visitor.state, 'arrived')
        self.assertTrue(visitor.checkin_time)
        self.assertFalse(visitor.checkout_time)
        self.assertTrue(mock_notify.called)
        self.assertTrue(mock_send_mail.called)

        # Cannot check-in again
        with self.assertRaises(UserError):
            visitor.action_checkin()

        # Check-out
        visitor.action_checkout()
        self.assertEqual(visitor.state, 'departed')
        self.assertTrue(visitor.checkout_time)
        self.assertGreaterEqual(visitor.checkout_time, visitor.checkin_time)

        # Cannot check-out again
        with self.assertRaises(UserError):
            visitor.action_checkout()

        # Cannot cancel departed visitor
        with self.assertRaises(UserError):
            visitor.action_cancel()

    def test_02_cancel_and_reset(self):
        """Test cancellation and reset by Manager."""
        # Cancel from draft
        visitor_draft = self.env['frontdesk.visitor'].create({
            'name': 'Jane Smith',
            'purpose': 'Job Interview',
            'host_id': self.employee_host.id,
        })
        visitor_draft.action_cancel()
        self.assertEqual(visitor_draft.state, 'cancelled')

        # Cancel from arrived
        visitor_arrived = self.env['frontdesk.visitor'].create({
            'name': 'Bob Ross',
            'purpose': 'Art Consultation',
            'host_id': self.employee_host.id,
        })
        visitor_arrived.action_checkin()
        visitor_arrived.action_cancel()
        self.assertEqual(visitor_arrived.state, 'cancelled')

        # Reset by Officer should raise AccessError
        with self.assertRaises(AccessError):
            visitor_arrived.with_user(self.user_officer).action_reset_draft()

        # Reset by Manager should succeed and clear timestamps
        visitor_arrived.with_user(self.user_manager).action_reset_draft()
        self.assertEqual(visitor_arrived.state, 'draft')
        self.assertFalse(visitor_arrived.checkin_time)
        self.assertFalse(visitor_arrived.checkout_time)

    def test_03_dual_notifications_and_fallbacks(self):
        """Test inbox and email notification logic under various conditions."""
        # Case A: Host has both user and work_email
        visitor_full = self.env['frontdesk.visitor'].create({
            'name': 'Client A',
            'company_name': 'Tech Global',
            'purpose': 'Demo Meeting',
            'host_id': self.employee_host.id,
            'room_name': 'Boardroom A',
        })
        with patch.object(type(visitor_full), 'message_notify') as mock_notify, \
             patch.object(type(self.env['mail.template']), 'send_mail') as mock_mail:
            visitor_full.action_checkin()
            self.assertTrue(mock_notify.called)
            self.assertTrue(mock_mail.called)
            notify_kwargs = mock_notify.call_args[1]
            self.assertIn(self.user_host.partner_id.id, notify_kwargs['partner_ids'])
            self.assertIn('Client A', notify_kwargs['body'])
            self.assertIn('Tech Global', notify_kwargs['body'])
            self.assertIn('Boardroom A', notify_kwargs['body'])

        # Case B: Host has no user account (email only)
        visitor_no_user = self.env['frontdesk.visitor'].create({
            'name': 'Client B',
            'purpose': 'Audit',
            'host_id': self.employee_no_user.id,
        })
        with patch.object(type(visitor_no_user), 'message_notify') as mock_notify, \
             patch.object(type(self.env['mail.template']), 'send_mail') as mock_mail:
            visitor_no_user.action_checkin()
            self.assertFalse(mock_notify.called)
            self.assertTrue(mock_mail.called)

        # Case C: Host has no work email (inbox only + chatter warning)
        visitor_no_email = self.env['frontdesk.visitor'].create({
            'name': 'Client C',
            'purpose': 'Consulting',
            'host_id': self.employee_no_email.id,
        })
        with patch.object(type(visitor_no_email), 'message_notify') as mock_notify, \
             patch.object(type(self.env['mail.template']), 'send_mail') as mock_mail:
            visitor_no_email.action_checkin()
            self.assertTrue(mock_notify.called)
            self.assertFalse(mock_mail.called)

        # Case D: Exception during mail sending should NOT fail check-in
        visitor_err = self.env['frontdesk.visitor'].create({
            'name': 'Client D',
            'purpose': 'Testing Error Resilience',
            'host_id': self.employee_host.id,
        })
        with patch.object(type(self.env['mail.template']), 'send_mail', side_effect=Exception("SMTP Down")):
            visitor_err.action_checkin()
            self.assertEqual(visitor_err.state, 'arrived')
            self.assertTrue(visitor_err.checkin_time)

    def test_04_immutability_on_departed(self):
        """Test write and unlink restrictions on departed records for non-managers."""
        visitor = self.env['frontdesk.visitor'].with_user(self.user_officer).create({
            'name': 'Departing Guest',
            'purpose': 'Partnership Discussion',
            'host_id': self.employee_host.id,
        })
        visitor.action_checkin()
        visitor.action_checkout()
        self.assertEqual(visitor.state, 'departed')

        # Officer trying to edit fields on departed visitor should raise UserError
        with self.assertRaises(UserError):
            visitor.with_user(self.user_officer).write({'phone': '+987654321'})

        # Officer posting message to chatter should SUCCEED
        visitor.with_user(self.user_officer).message_post(body="Visitor forgot their notebook.")

        # Manager CAN edit departed visitor
        visitor.with_user(self.user_manager).write({'phone': '+987654321'})
        self.assertEqual(visitor.phone, '+987654321')

        # Officer cannot unlink
        with self.assertRaises(AccessError):
            visitor.with_user(self.user_officer).unlink()

        # Manager CAN unlink
        visitor.with_user(self.user_manager).unlink()

    def test_05_security_and_user_access(self):
        """Test Frontdesk User role restrictions per ir.access."""
        # Host creates / has assigned visitor
        visitor_host = self.env['frontdesk.visitor'].with_user(self.user_officer).create({
            'name': 'Guest for Host',
            'purpose': 'Project Sync',
            'host_id': self.employee_host.id,
        })

        # Other user's visitor
        visitor_other = self.env['frontdesk.visitor'].with_user(self.user_officer).create({
            'name': 'Guest for Other',
            'purpose': 'Code Review',
            'host_id': self.employee_other.id,
        })

        # Host user can read their own assigned visitor
        self.assertTrue(visitor_host.with_user(self.user_host).read(['name']))

        # Host user CANNOT read other employee's visitor
        with self.assertRaises(AccessError):
            visitor_other.with_user(self.user_host).read(['name'])

        # Regular user cannot create visitors directly
        with self.assertRaises(AccessError):
            self.env['frontdesk.visitor'].with_user(self.user_host).create({
                'name': 'Unauthorized Creation',
                'purpose': 'Breach',
                'host_id': self.employee_host.id,
            })

    def test_06_multi_company_isolation(self):
        """Test multi-company security isolation for visitors."""
        # Employee in Company B
        employee_comp_b = self.env['hr.employee'].create({
            'name': 'Employee Comp B',
            'company_id': self.company_b.id,
        })

        # Visitor in Company B
        visitor_b = self.env['frontdesk.visitor'].create({
            'name': 'Guest in Company B',
            'purpose': 'Company B Business',
            'host_id': employee_comp_b.id,
            'company_id': self.company_b.id,
        })

        # Officer in Company A (without Company B in allowed company_ids) cannot read visitor_b
        with self.assertRaises(AccessError):
            visitor_b.with_user(self.user_officer).read(['name'])

    def test_07_search_filter_in_office(self):
        """Test quick filter for 'Currently in Office' (state == 'arrived')."""
        v_draft = self.env['frontdesk.visitor'].create({
            'name': 'Filter Draft',
            'purpose': 'Draft Test',
            'host_id': self.employee_host.id,
        })
        v_arrived = self.env['frontdesk.visitor'].create({
            'name': 'Filter Arrived',
            'purpose': 'In Building Test',
            'host_id': self.employee_host.id,
        })
        v_arrived.action_checkin()

        v_departed = self.env['frontdesk.visitor'].create({
            'name': 'Filter Departed',
            'purpose': 'Departed Test',
            'host_id': self.employee_host.id,
        })
        v_departed.action_checkin()
        v_departed.action_checkout()

        # Search with state = 'arrived'
        in_office_records = self.env['frontdesk.visitor'].search([('state', '=', 'arrived')])
        self.assertIn(v_arrived, in_office_records)
        self.assertNotIn(v_draft, in_office_records)
        self.assertNotIn(v_departed, in_office_records)

    def test_08_visitor_vietnamese_localization(self):
        """Test Vietnamese translations for visitor model and selection labels."""
        visitor = self.env['frontdesk.visitor'].create({
            'name': 'Visitor Test Lang',
            'purpose': 'Testing Vietnamese Localization',
            'host_id': self.employee_host.id,
            'state': 'arrived',
        })
        v_vi = visitor.with_context(lang='vi_VN')
        fields_info = v_vi.fields_get(['state', 'name', 'purpose', 'host_id', 'room_name'])
        state_dict_vi = dict(fields_info['state']['selection'])
        self.assertEqual(state_dict_vi.get('arrived'), 'Đang ở văn phòng')
        self.assertEqual(state_dict_vi.get('draft'), 'Đã lên lịch')
        self.assertEqual(state_dict_vi.get('departed'), 'Đã rời đi')
        self.assertEqual(state_dict_vi.get('cancelled'), 'Đã huỷ')
        self.assertEqual(fields_info['name']['string'], 'Tên khách đến làm việc')
        self.assertEqual(fields_info['host_id']['string'], 'Người tiếp đón')

