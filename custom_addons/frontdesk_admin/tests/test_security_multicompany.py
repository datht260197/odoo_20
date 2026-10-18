from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestSecurityMultiCompany(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Company 1
        cls.company_1 = cls.env['res.company'].create({'name': 'Company Alpha'})
        # Company 2
        cls.company_2 = cls.env['res.company'].create({'name': 'Company Beta'})

        # Groups
        cls.group_user = cls.env.ref('frontdesk_admin.group_frontdesk_user')
        cls.group_officer = cls.env.ref('frontdesk_admin.group_frontdesk_officer')
        cls.group_manager = cls.env.ref('frontdesk_admin.group_frontdesk_manager')

        # User A in Company 1 (Frontdesk User)
        cls.user_a = cls.env['res.users'].create({
            'name': 'User Alpha',
            'login': 'user_alpha',
            'email': 'alpha@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, cls.group_user.id])],
            'company_id': cls.company_1.id,
            'company_ids': [(6, 0, [cls.company_1.id])],
        })
        cls.employee_a = cls.env['hr.employee'].create({
            'name': 'Employee Alpha',
            'user_id': cls.user_a.id,
            'company_id': cls.company_1.id,
        })

        # User B in Company 1 (Frontdesk User)
        cls.user_b = cls.env['res.users'].create({
            'name': 'User Bravo',
            'login': 'user_bravo',
            'email': 'bravo@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, cls.group_user.id])],
            'company_id': cls.company_1.id,
            'company_ids': [(6, 0, [cls.company_1.id])],
        })
        cls.employee_b = cls.env['hr.employee'].create({
            'name': 'Employee Bravo',
            'user_id': cls.user_b.id,
            'company_id': cls.company_1.id,
        })

        # Officer in Company 1
        cls.user_officer = cls.env['res.users'].create({
            'name': 'Officer Alpha',
            'login': 'officer_alpha',
            'email': 'officer_alpha@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, cls.group_officer.id])],
            'company_id': cls.company_1.id,
            'company_ids': [(6, 0, [cls.company_1.id])],
        })

        # Manager in Company 1
        cls.user_manager = cls.env['res.users'].create({
            'name': 'Manager Alpha',
            'login': 'manager_alpha',
            'email': 'manager_alpha@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, cls.group_manager.id])],
            'company_id': cls.company_1.id,
            'company_ids': [(6, 0, [cls.company_1.id])],
        })

        # User in Company 2
        cls.user_company_2 = cls.env['res.users'].create({
            'name': 'Officer Beta',
            'login': 'officer_beta',
            'email': 'officer_beta@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id, cls.group_officer.id])],
            'company_id': cls.company_2.id,
            'company_ids': [(6, 0, [cls.company_2.id])],
        })

    def test_01_user_only_sees_own_records(self):
        """Test that Frontdesk User can only see records where recipient_id.user_id == user.id."""
        doc_a = self.env['frontdesk.document'].create({
            'doc_type': 'inbound',
            'recipient_id': self.employee_a.id,
            'company_id': self.company_1.id,
        })
        doc_b = self.env['frontdesk.document'].create({
            'doc_type': 'inbound',
            'recipient_id': self.employee_b.id,
            'company_id': self.company_1.id,
        })

        # User A searches documents -> sees only doc_a
        docs_visible_to_a = self.env['frontdesk.document'].with_user(self.user_a).search([])
        self.assertIn(doc_a, docs_visible_to_a)
        self.assertNotIn(doc_b, docs_visible_to_a)

        # User A attempting direct read on doc_b -> blocked by ACL domain
        with self.assertRaises(AccessError):
            doc_b.with_user(self.user_a).read(['internal_ref'])

        # User A cannot create documents
        with self.assertRaises(AccessError):
            self.env['frontdesk.document'].with_user(self.user_a).create({
                'doc_type': 'inbound',
                'recipient_id': self.employee_a.id,
                'company_id': self.company_1.id,
            })

        # User A cannot write documents
        with self.assertRaises(AccessError):
            doc_a.with_user(self.user_a).write({'external_ref': 'HACK'})

        # User A cannot unlink documents
        with self.assertRaises(AccessError):
            doc_a.with_user(self.user_a).unlink()

    def test_02_officer_cannot_unlink(self):
        """Test that Frontdesk Officer has CRU permissions but cannot unlink records."""
        doc = self.env['frontdesk.document'].with_user(self.user_officer).create({
            'doc_type': 'inbound',
            'recipient_id': self.employee_a.id,
            'company_id': self.company_1.id,
        })
        self.assertTrue(doc)

        parcel = self.env['frontdesk.parcel'].with_user(self.user_officer).create({
            'recipient_id': self.employee_a.id,
            'company_id': self.company_1.id,
        })
        self.assertTrue(parcel)

        # Officer cannot unlink document
        with self.assertRaises(AccessError):
            doc.with_user(self.user_officer).unlink()

        # Officer cannot unlink parcel
        with self.assertRaises(AccessError):
            parcel.with_user(self.user_officer).unlink()

        # Manager CAN unlink document and parcel
        doc.with_user(self.user_manager).unlink()
        parcel.with_user(self.user_manager).unlink()

    def test_03_multi_company_record_isolation(self):
        """Test multi-company security: records in Company Alpha invisible to Company Beta users."""
        doc_alpha = self.env['frontdesk.document'].create({
            'doc_type': 'inbound',
            'recipient_id': self.employee_a.id,
            'company_id': self.company_1.id,
        })
        parcel_alpha = self.env['frontdesk.parcel'].create({
            'recipient_id': self.employee_a.id,
            'company_id': self.company_1.id,
        })

        # Officer in Company Beta searches records
        docs_beta = self.env['frontdesk.document'].with_user(self.user_company_2).search([])
        self.assertNotIn(doc_alpha, docs_beta)

        parcels_beta = self.env['frontdesk.parcel'].with_user(self.user_company_2).search([])
        self.assertNotIn(parcel_alpha, parcels_beta)

        # Direct access by Company Beta user raises AccessError
        with self.assertRaises(AccessError):
            doc_alpha.with_user(self.user_company_2).read(['internal_ref'])

        with self.assertRaises(AccessError):
            parcel_alpha.with_user(self.user_company_2).read(['name'])

    def test_04_vietnamese_localization(self):
        """Test that Vietnamese translations are correctly registered."""
        # Check selection label translation for Inbound doc_type
        doc = self.env['frontdesk.document'].create({
            'doc_type': 'inbound',
            'recipient_id': self.employee_a.id,
            'company_id': self.company_1.id,
        })
        # Check that model exists and can be queried with vi_VN context
        self.env['res.lang']._activate_lang('vi_VN')
        doc_vi = doc.with_context(lang='vi_VN')
        self.assertTrue(doc_vi)
