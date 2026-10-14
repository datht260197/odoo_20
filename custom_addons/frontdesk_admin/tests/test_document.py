import base64
from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestFrontdeskDocument(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        # Partner
        cls.partner = cls.env['res.partner'].create({
            'name': 'Ministry of Justice',
            'company_id': cls.company.id,
        })

        # Groups
        cls.group_user = cls.env.ref('frontdesk_admin.group_frontdesk_user')
        cls.group_officer = cls.env.ref('frontdesk_admin.group_frontdesk_officer')
        cls.group_manager = cls.env.ref('frontdesk_admin.group_frontdesk_manager')

        # Employee 1 and User 1 (Recipient)
        cls.user_recipient = cls.env['res.users'].create({
            'name': 'Jane Recipient',
            'login': 'jane_recipient',
            'email': 'jane@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, cls.group_user.id])],
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
        })
        cls.employee_recipient = cls.env['hr.employee'].create({
            'name': 'Jane Recipient',
            'user_id': cls.user_recipient.id,
            'work_email': 'jane@example.com',
            'company_id': cls.company.id,
        })

        # Frontdesk Officer User
        cls.user_officer = cls.env['res.users'].create({
            'name': 'John Officer',
            'login': 'john_officer',
            'email': 'officer@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, cls.group_officer.id])],
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
        })

        # Frontdesk Manager User
        cls.user_manager = cls.env['res.users'].create({
            'name': 'Boss Manager',
            'login': 'boss_manager',
            'email': 'boss@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, cls.group_manager.id])],
            'company_id': cls.company.id,
            'company_ids': [(6, 0, [cls.company.id])],
        })

    def test_01_sequence_generation(self):
        """Test document sequence prefixes and date range format."""
        current_year = str(fields.Date.today().year)

        # Inbound document
        doc_in = self.env['frontdesk.document'].create({
            'doc_type': 'inbound',
            'partner_id': self.partner.id,
            'recipient_id': self.employee_recipient.id,
        })
        self.assertTrue(doc_in.internal_ref.startswith(f"CVD/{current_year}/"))

        # Outbound document
        doc_out = self.env['frontdesk.document'].create({
            'doc_type': 'outbound',
            'partner_id': self.partner.id,
            'recipient_id': self.employee_recipient.id,
        })
        self.assertTrue(doc_out.internal_ref.startswith(f"CVI/{current_year}/"))

        # Contract document (uses CVD sequence)
        doc_contract = self.env['frontdesk.document'].create({
            'doc_type': 'contract',
            'partner_id': self.partner.id,
            'recipient_id': self.employee_recipient.id,
        })
        self.assertTrue(doc_contract.internal_ref.startswith(f"CVD/{current_year}/"))

    def test_02_state_transitions(self):
        """Test document workflow received -> processing -> archived and invalid transitions."""
        doc = self.env['frontdesk.document'].create({
            'doc_type': 'inbound',
            'partner_id': self.partner.id,
            'recipient_id': self.employee_recipient.id,
        })
        self.assertEqual(doc.state, 'received')

        # Invalid: cannot archive directly from received
        with self.assertRaises(UserError):
            doc.action_archive()

        # Valid: received -> processing
        doc.action_process()
        self.assertEqual(doc.state, 'processing')

        # Invalid: cannot process again
        with self.assertRaises(UserError):
            doc.action_process()

        # Valid: processing -> archived
        doc.action_archive()
        self.assertEqual(doc.state, 'archived')

    def test_03_immutability_archived_records(self):
        """Test that archived documents cannot be modified or deleted by non-managers, but chatter works."""
        doc = self.env['frontdesk.document'].create({
            'doc_type': 'inbound',
            'partner_id': self.partner.id,
            'recipient_id': self.employee_recipient.id,
            'summary': 'Initial summary',
        })
        doc.action_process()
        doc.action_archive()
        self.assertEqual(doc.state, 'archived')

        # Officer attempts to modify business fields on archived doc -> blocked
        with self.assertRaises(UserError):
            doc.with_user(self.user_officer).write({'summary': 'Hacked summary'})

        # Officer attempts to delete archived doc -> blocked
        with self.assertRaises(AccessError):
            doc.with_user(self.user_officer).unlink()

        # Chatter internal updates (logging messages / activities) must succeed
        msg = doc.with_user(self.user_officer).message_post(body="Officer note on archived file")
        self.assertTrue(msg)

        # Manager can modify or reset archived doc
        doc.with_user(self.user_manager).write({'summary': 'Updated by Manager'})
        self.assertEqual(doc.summary, 'Updated by Manager')

        doc.with_user(self.user_manager).action_reset_to_received()
        self.assertEqual(doc.state, 'received')

    def test_04_confidentiality_metadata_and_content_isolation(self):
        """Test that non-manager officer can view metadata but is blocked from reading confidential summary and files."""
        # Create an attachment
        att = self.env['ir.attachment'].create({
            'name': 'secret_contract.pdf',
            'type': 'binary',
            'raw': b'%PDF-1.4 secret content',
        })

        conf_doc = self.env['frontdesk.document'].create({
            'doc_type': 'inbound',
            'partner_id': self.partner.id,
            'recipient_id': self.employee_recipient.id,
            'is_confidential': True,
            'summary': 'Extremely confidential strategic merger terms',
            'attachment_ids': [(6, 0, [att.id])],
        })

        # 1. Officer can read routing metadata
        metadata = conf_doc.with_user(self.user_officer).read([
            'internal_ref', 'external_ref', 'partner_id', 'recipient_id', 'issue_date', 'state'
        ])
        self.assertTrue(metadata)
        self.assertEqual(metadata[0]['internal_ref'], conf_doc.internal_ref)

        # 2. Officer is strictly blocked from reading confidential summary via read()
        with self.assertRaises(AccessError):
            conf_doc.with_user(self.user_officer).read(['summary'])

        # 3. Officer is strictly blocked from reading confidential attachment_ids via read()
        with self.assertRaises(AccessError):
            conf_doc.with_user(self.user_officer).read(['attachment_ids'])

        # 4. Officer is blocked from reading summary via direct attribute access
        with self.assertRaises(AccessError):
            _ = conf_doc.with_user(self.user_officer).summary

        # 5. Designated Recipient CAN read summary and attachment_ids
        recip_data = conf_doc.with_user(self.user_recipient).read(['summary', 'attachment_ids'])
        self.assertEqual(recip_data[0]['summary'], 'Extremely confidential strategic merger terms')
        self.assertEqual(conf_doc.with_user(self.user_recipient).summary, 'Extremely confidential strategic merger terms')

        # 6. Manager CAN read summary and attachment_ids
        mgr_data = conf_doc.with_user(self.user_manager).read(['summary', 'attachment_ids'])
        self.assertEqual(mgr_data[0]['summary'], 'Extremely confidential strategic merger terms')

    def test_05_attachment_security(self):
        """Test ir.attachment access control directly rejecting read for confidential document attachments."""
        att = self.env['ir.attachment'].create({
            'name': 'classified_doc.pdf',
            'type': 'binary',
            'raw': b'%PDF-1.4 top secret',
            'res_model': 'frontdesk.document',
        })

        conf_doc = self.env['frontdesk.document'].create({
            'doc_type': 'inbound',
            'partner_id': self.partner.id,
            'recipient_id': self.employee_recipient.id,
            'is_confidential': True,
            'attachment_ids': [(6, 0, [att.id])],
        })
        att.write({'res_id': conf_doc.id})

        # Officer reading confidential attachment directly via ORM -> blocked
        with self.assertRaises(AccessError):
            att.with_user(self.user_officer).read(['name', 'raw'])

        with self.assertRaises(AccessError):
            att.with_user(self.user_officer).check_access('read')

        # Recipient reading confidential attachment -> allowed
        res = att.with_user(self.user_recipient).read(['name'])
        self.assertEqual(res[0]['name'], 'classified_doc.pdf')

        # Manager reading confidential attachment -> allowed
        mgr_res = att.with_user(self.user_manager).read(['name'])
        self.assertEqual(mgr_res[0]['name'], 'classified_doc.pdf')
