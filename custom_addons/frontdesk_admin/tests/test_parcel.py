import base64
import io
from unittest.mock import patch
from PIL import Image

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged


def _generate_valid_png():
    buf = io.BytesIO()
    img = Image.new('RGB', (20, 20), color='blue')
    img.save(buf, format='PNG')
    return base64.b64encode(buf.getvalue()).decode('ascii')


@tagged('post_install', '-at_install')
class TestFrontdeskParcel(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        # Carrier Partner
        cls.carrier = cls.env['res.partner'].create({
            'name': 'VNPost Logistics',
            'company_id': cls.company.id,
        })

        # Groups
        cls.group_user = cls.env.ref('frontdesk_admin.group_frontdesk_user')
        cls.group_officer = cls.env.ref('frontdesk_admin.group_frontdesk_officer')
        cls.group_manager = cls.env.ref('frontdesk_admin.group_frontdesk_manager')

        # Recipient 1: Has user and work_email
        cls.user_recipient = cls.env['res.users'].create({
            'name': 'Alice Recipient',
            'login': 'alice_recipient',
            'email': 'alice@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, cls.group_user.id])],
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
        })
        cls.employee_recipient = cls.env['hr.employee'].create({
            'name': 'Alice Recipient',
            'user_id': cls.user_recipient.id,
            'work_email': 'alice@example.com',
            'company_id': cls.company.id,
        })

        # Recipient 2: Employee without user, but has email
        cls.employee_no_user = cls.env['hr.employee'].create({
            'name': 'Bob NoUser',
            'work_email': 'bob@example.com',
            'company_id': cls.company.id,
        })

        # Recipient 3: Employee without work email
        cls.employee_no_email = cls.env['hr.employee'].create({
            'name': 'Charlie NoEmail',
            'company_id': cls.company.id,
        })

        # Frontdesk Officer User
        cls.user_officer = cls.env['res.users'].create({
            'name': 'Tom Officer',
            'login': 'tom_officer',
            'email': 'tom@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, cls.group_officer.id])],
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
        })

        # Frontdesk Manager User
        cls.user_manager = cls.env['res.users'].create({
            'name': 'Sarah Manager',
            'login': 'sarah_manager',
            'email': 'sarah@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, cls.group_manager.id])],
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
        })

        cls.sample_photo = _generate_valid_png()

    def test_01_parcel_sequence_and_creation(self):
        """Test parcel sequence numbering format (BP/year/0001)."""
        current_year = str(fields.Date.today().year)
        parcel = self.env['frontdesk.parcel'].create({
            'recipient_id': self.employee_recipient.id,
            'carrier_id': self.carrier.id,
            'tracking_ref': 'VN123456789',
        })
        self.assertTrue(parcel.name.startswith(f"BP/{current_year}/"))

    def test_02_notifications_and_auto_transition(self):
        """Test parcel real-time notification to user inbox + email with photo, and auto-transition to 'notified'."""
        with patch.object(type(self.env['frontdesk.parcel']), 'message_notify') as mock_notify, \
             patch.object(type(self.env['mail.template']), 'send_mail') as mock_send_mail:

            parcel = self.env['frontdesk.parcel'].create({
                'recipient_id': self.employee_recipient.id,
                'carrier_id': self.carrier.id,
                'tracking_ref': 'DHL999888777',
                'photo': self.sample_photo,
            })

            # Must automatically transition to 'notified'
            self.assertEqual(parcel.state, 'notified')

            # User inbox message_notify called
            self.assertTrue(mock_notify.called)
            notify_kwargs = mock_notify.call_args[1]
            self.assertIn(self.user_recipient.partner_id.id, notify_kwargs.get('partner_ids', []))
            self.assertTrue(notify_kwargs.get('attachment_ids'))

            # Email send_mail called with attachment
            self.assertTrue(mock_send_mail.called)
            mail_kwargs = mock_send_mail.call_args[1]
            email_values = mail_kwargs.get('email_values', {})
            self.assertEqual(email_values.get('email_to'), 'alice@example.com')
            self.assertTrue(email_values.get('attachment_ids'))

    def test_03_notification_fallbacks(self):
        """Test fallback behavior when recipient lacks user or work email."""
        # 1. Employee without user: sends email only, no exception
        with patch.object(type(self.env['mail.template']), 'send_mail') as mock_send_mail:
            parcel1 = self.env['frontdesk.parcel'].create({
                'recipient_id': self.employee_no_user.id,
                'carrier_id': self.carrier.id,
            })
            self.assertEqual(parcel1.state, 'notified')
            self.assertTrue(mock_send_mail.called)

        # 2. Employee without work email: logs warning, skips email, no exception
        parcel2 = self.env['frontdesk.parcel'].create({
            'recipient_id': self.employee_no_email.id,
            'carrier_id': self.carrier.id,
        })
        self.assertEqual(parcel2.state, 'notified')

    def test_04_delivery_and_return_lifecycle(self):
        """Test parcel state machine: delivery sets date and delivered_by_id; return works."""
        parcel = self.env['frontdesk.parcel'].create({
            'recipient_id': self.employee_recipient.id,
            'carrier_id': self.carrier.id,
        })
        self.assertEqual(parcel.state, 'notified')

        # Execute delivery as Officer
        parcel.with_user(self.user_officer).action_deliver()
        self.assertEqual(parcel.state, 'delivered')
        self.assertTrue(parcel.delivered_date)
        self.assertEqual(parcel.delivered_by_id, self.user_officer)

        # Cannot deliver again
        with self.assertRaises(UserError):
            parcel.with_user(self.user_officer).action_deliver()

        # Cannot return delivered parcel
        with self.assertRaises(UserError):
            parcel.with_user(self.user_officer).action_return()

        # Test return on another parcel
        parcel_ret = self.env['frontdesk.parcel'].create({
            'recipient_id': self.employee_recipient.id,
            'carrier_id': self.carrier.id,
        })
        parcel_ret.with_user(self.user_officer).action_return()
        self.assertEqual(parcel_ret.state, 'returned')

    def test_05_immutability_delivered_and_returned_parcels(self):
        """Test that delivered/returned parcels are locked from modification/unlink for non-managers."""
        parcel = self.env['frontdesk.parcel'].create({
            'recipient_id': self.employee_recipient.id,
            'carrier_id': self.carrier.id,
            'delivery_notes': 'Initial notes',
        })
        parcel.action_deliver()
        self.assertEqual(parcel.state, 'delivered')

        # Non-manager modifying delivery notes -> blocked
        with self.assertRaises(UserError):
            parcel.with_user(self.user_officer).write({'delivery_notes': 'Modified notes'})

        # Non-manager unlinking delivered parcel -> blocked
        with self.assertRaises(AccessError):
            parcel.with_user(self.user_officer).unlink()

        # Chatter message logging still allowed
        msg = parcel.with_user(self.user_officer).message_post(body="Handover confirmation chatter note")
        self.assertTrue(msg)

        # Manager can modify or reset
        parcel.with_user(self.user_manager).write({'delivery_notes': 'Manager audit note'})
        self.assertEqual(parcel.delivery_notes, 'Manager audit note')

        parcel.with_user(self.user_manager).action_reset_draft()
        self.assertEqual(parcel.state, 'received')
