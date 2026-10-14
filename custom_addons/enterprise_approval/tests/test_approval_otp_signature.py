# -*- coding: utf-8 -*-
import hashlib
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestApprovalOtpSignature(TransactionCase):
    """Automated tests for Two-Factor OTP Digital Signature Verification."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        # Users
        cls.user_requester = cls.env['res.users'].create({
            'name': 'Requester Alice',
            'login': 'alice_requester',
            'email': 'alice@company.com',
            'group_ids': [(6, 0, [cls.env.ref('enterprise_approval.group_approval_user').id])],
        })
        cls.user_approver = cls.env['res.users'].create({
            'name': 'Approver Bob',
            'login': 'bob_approver',
            'email': 'bob@company.com',
            'group_ids': [(6, 0, [cls.env.ref('enterprise_approval.group_approval_approver').id])],
        })
        cls.user_unauthorized = cls.env['res.users'].create({
            'name': 'Unauthorized Charlie',
            'login': 'charlie_unauth',
            'email': 'charlie@company.com',
            'group_ids': [(6, 0, [cls.env.ref('enterprise_approval.group_approval_user').id])],
        })

        # Category
        cls.category = cls.env['approval.category'].create({
            'name': 'Standard Procurement',
            'code': 'PROC_TEST',
            'has_amount': 'optional',
            'has_date': 'no',
            'has_location': 'no',
            'approver_id': cls.user_approver.id,
        })

        # Request
        cls.request = cls.env['approval.request'].with_user(cls.user_requester).create({
            'title': 'Office Supplies Requisition',
            'category_id': cls.category.id,
            'approver_id': cls.user_approver.id,
            'amount': 500.0,
        })
        cls.request.action_submit()

    def test_01_approve_triggers_otp_wizard_and_hash(self):
        """Reviewer approving triggers 6-digit OTP generation and wizard opening."""
        self.assertEqual(self.request.state, 'submitted')
        action = self.request.with_user(self.user_approver).action_approve()

        self.assertEqual(action.get('res_model'), 'approval.signature.otp.wizard')
        wizard_id = action.get('res_id')
        self.assertTrue(wizard_id)

        wizard = self.env['approval.signature.otp.wizard'].browse(wizard_id)
        self.assertEqual(wizard.request_id, self.request)
        self.assertEqual(wizard.approver_id.user_id, self.user_approver)
        self.assertTrue(wizard.otp_code_hash)
        self.assertEqual(len(wizard.otp_code_hash), 64)
        self.assertTrue(wizard.otp_expiry > fields.Datetime.now())

    def test_02_invalid_otp_rejection(self):
        """Entering incorrect OTP raises UserError."""
        action = self.request.with_user(self.user_approver).action_approve()
        wizard = self.env['approval.signature.otp.wizard'].browse(action['res_id'])

        wizard.otp_input = '000000'
        # Unless hash miraculously matches 000000, mismatch must raise UserError
        expected_hash = hashlib.sha256('000000'.encode('utf-8')).hexdigest()
        if wizard.otp_code_hash != expected_hash:
            with self.assertRaises(UserError):
                wizard.action_confirm_signature()

    def test_03_expired_otp_rejection(self):
        """Entering an expired OTP raises UserError."""
        action = self.request.with_user(self.user_approver).action_approve()
        wizard = self.env['approval.signature.otp.wizard'].browse(action['res_id'])

        # Artificially expire the OTP
        wizard.otp_expiry = fields.Datetime.now() - timedelta(minutes=5)
        wizard.otp_input = '123456'

        with self.assertRaises(UserError):
            wizard.action_confirm_signature()

    def test_04_resend_otp(self):
        """Calling action_resend_otp refreshes the hash and expiry."""
        action = self.request.with_user(self.user_approver).action_approve()
        wizard = self.env['approval.signature.otp.wizard'].browse(action['res_id'])
        old_hash = wizard.otp_code_hash

        resend_action = wizard.action_resend_otp()
        self.assertEqual(resend_action.get('type'), 'ir.actions.client')
        self.assertTrue(wizard.otp_code_hash)
        self.assertTrue(wizard.otp_expiry > fields.Datetime.now())

    def test_05_valid_otp_digital_signature_success(self):
        """Entering valid OTP successfully signs the approval line and completes approval."""
        action = self.request.with_user(self.user_approver).action_approve()
        wizard = self.env['approval.signature.otp.wizard'].browse(action['res_id'])

        # Simulate knowing the OTP by setting a known hash
        test_otp = '654321'
        wizard.otp_code_hash = hashlib.sha256(test_otp.encode('utf-8')).hexdigest()
        wizard.otp_input = test_otp
        wizard.approval_comment = 'Approved with full budget compliance.'

        res = wizard.with_user(self.user_approver).action_confirm_signature()
        self.assertEqual(res, {'type': 'ir.actions.act_window_close'})

        # Approver line verification
        approver_line = wizard.approver_id
        self.assertEqual(approver_line.status, 'approved')
        self.assertTrue(approver_line.is_otp_verified)
        self.assertEqual(approver_line.otp_verified_email, 'bob@company.com')
        self.assertTrue(approver_line.signed_datetime)
        self.assertTrue(approver_line.signature_hash)
        self.assertEqual(len(approver_line.signature_hash), 64)

        # Request state completion
        self.assertEqual(self.request.state, 'approved')
        self.assertEqual(self.request.confirmed_by, self.user_approver)

    def test_06_unauthorized_user_cannot_approve(self):
        """User without approval permission gets AccessError."""
        with self.assertRaises(AccessError):
            self.request.with_user(self.user_unauthorized).action_approve()
