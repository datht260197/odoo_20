# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64

from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRmcFastMigration(TransactionCase):

    def test_01_idempotent_partner_migration(self):
        """Test importing partners via CSV and verifying idempotent Upsert."""
        csv_data = (
            "fast_partner_code,name,vat,phone,email,rmc_partner_category\n"
            "CUST-001,Coteccons Construction Corp,0305001234,02838001122,info@coteccons.vn,contractor\n"
            "SUPP-001,Vicem Ha Tien Cement,0300456789,02838223344,sales@hatien.vn,material_supplier\n"
        )
        b64_file = base64.b64encode(csv_data.encode('utf-8')).decode('ascii')

        wizard = self.env['rmc.fast.migration.wizard'].create({
            'migration_type': 'partners',
            'import_file': b64_file,
            'filename': 'partners.csv',
        })
        wizard.action_import_data()

        partner1 = self.env['res.partner'].search([('fast_partner_code', '=', 'CUST-001')])
        self.assertEqual(len(partner1), 1)
        self.assertEqual(partner1.rmc_partner_category, 'contractor')
        self.assertEqual(partner1.vat, '0305001234')

        # Re-import modified file with updated phone
        csv_data_updated = (
            "fast_partner_code,name,vat,phone,email,rmc_partner_category\n"
            "CUST-001,Coteccons Construction Corp,0305001234,0909999888,info@coteccons.vn,contractor\n"
        )
        wizard.write({
            'import_file': base64.b64encode(csv_data_updated.encode('utf-8')).decode('ascii'),
        })
        wizard.action_import_data()

        # Verify record was updated in-place without duplicate
        partners = self.env['res.partner'].search([('fast_partner_code', '=', 'CUST-001')])
        self.assertEqual(len(partners), 1)
        self.assertEqual(partners.phone, '0909999888')

    def test_02_idempotent_product_migration(self):
        """Test importing materials and concrete grades with proper storable flags."""
        csv_data = (
            "fast_legacy_code,name,rmc_product_type,concrete_grade,slump_spec,stone_size,standard_density_ton_m3\n"
            "BT-M300-12,Concrete Grade M300 R28 Slump 12,concrete,M300,12±2,1x2,0.0\n"
            "CAT-VANG-01,Washed Yellow Concrete Sand,raw_material,,,,1.45\n"
        )
        wizard = self.env['rmc.fast.migration.wizard'].create({
            'migration_type': 'products',
            'import_file': base64.b64encode(csv_data.encode('utf-8')).decode('ascii'),
            'filename': 'products.csv',
        })
        wizard.action_import_data()

        concrete = self.env['product.template'].search([('fast_legacy_code', '=', 'BT-M300-12')])
        self.assertEqual(len(concrete), 1)
        self.assertEqual(concrete.rmc_product_type, 'concrete')
        self.assertFalse(concrete.is_storable, "Concrete products must be consumable (is_storable=False)")
        self.assertEqual(concrete.concrete_grade, 'M300')
        self.assertEqual(concrete.stone_size, '1x2')

        sand = self.env['product.template'].search([('fast_legacy_code', '=', 'CAT-VANG-01')])
        self.assertEqual(len(sand), 1)
        self.assertEqual(sand.rmc_product_type, 'raw_material')
        self.assertTrue(sand.is_storable, "Raw material aggregates must be storable (is_storable=True)")
        self.assertAlmostEqual(sand.standard_density_ton_m3, 1.45, places=2)

    def test_03_idempotent_project_migration(self):
        """Test importing construction sites and verifying automatic analytic account creation."""
        csv_data = (
            "fast_legacy_project_code,project_code,name,site_address,gps_latitude,gps_longitude,geofence_radius_m,total_contract_quota_m3,total_delivered_m3\n"
            "FAST-PRJ-01,SITE-VCP,Vinhomes Central Park Tower 5,Nguyen Huu Canh Binh Thanh,10.7933,106.7215,200.0,5000.0,1200.0\n"
        )
        wizard = self.env['rmc.fast.migration.wizard'].create({
            'migration_type': 'projects',
            'import_file': base64.b64encode(csv_data.encode('utf-8')).decode('ascii'),
            'filename': 'projects.csv',
        })
        wizard.action_import_data()

        proj = self.env['project.project'].search([('fast_legacy_project_code', '=', 'FAST-PRJ-01')])
        self.assertEqual(len(proj), 1)
        self.assertTrue(proj.is_concrete_site)
        self.assertTrue(proj.account_id, "Analytic account must be linked upon project creation")
        self.assertAlmostEqual(proj.remaining_quota_m3, 3800.0, places=2)
        self.assertAlmostEqual(proj.completion_progress, 24.0, places=2)
