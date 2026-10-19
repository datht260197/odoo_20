# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestRmcProjectSite(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.plant_primary = cls.env['stock.warehouse'].create({
            'name': 'Hiep Phuoc Plant 01',
            'code': 'HP01',
            'is_batching_plant': True,
            'plant_code': 'HP-01',
        })
        cls.plant_backup = cls.env['stock.warehouse'].create({
            'name': 'Cat Lai Plant 02',
            'code': 'CL02',
            'is_batching_plant': True,
            'plant_code': 'CL-02',
        })

    def test_01_auto_analytic_account_linking(self):
        """Test that creating a concrete site automatically creates and links an analytic account."""
        project = self.env['project.project'].create({
            'name': 'Landmark Tower 81 Foundation',
            'is_concrete_site': True,
            'project_code': 'PRJ-LM81',
            'site_address': '720A Dien Bien Phu, Binh Thanh, HCMC',
            'gps_latitude': 10.7951,
            'gps_longitude': 106.7218,
            'primary_plant_id': self.plant_primary.id,
            'backup_plant_ids': [(4, self.plant_backup.id)],
        })
        self.assertTrue(project.account_id, "Analytic Account must be automatically created and linked.")
        self.assertIn('Landmark Tower 81 Foundation', project.account_id.name)

    def test_02_gps_and_geofence_validation(self):
        """Test constraints on latitude, longitude, and geofence radius."""
        with self.assertRaises(ValidationError):
            self.env['project.project'].create({
                'name': 'Invalid Latitude Site',
                'is_concrete_site': True,
                'gps_latitude': 95.0,  # Invalid: > 90
            })

        with self.assertRaises(ValidationError):
            self.env['project.project'].create({
                'name': 'Invalid Longitude Site',
                'is_concrete_site': True,
                'gps_longitude': -190.0,  # Invalid: < -180
            })

        with self.assertRaises(ValidationError):
            self.env['project.project'].create({
                'name': 'Invalid Geofence Site',
                'is_concrete_site': True,
                'geofence_radius_m': 0.0,  # Invalid: <= 0
            })

    def test_03_pouring_metrics_computation(self):
        """Test remaining quota and completion progress calculations."""
        project = self.env['project.project'].create({
            'name': 'Metro Line 1 Station Pouring',
            'is_concrete_site': True,
            'total_contract_quota_m3': 1000.0,
            'total_delivered_m3': 350.0,
        })
        self.assertAlmostEqual(project.remaining_quota_m3, 650.0, places=2)
        self.assertAlmostEqual(project.completion_progress, 35.0, places=2)

        # Update delivered volume
        project.write({'total_delivered_m3': 1000.0})
        self.assertAlmostEqual(project.remaining_quota_m3, 0.0, places=2)
        self.assertAlmostEqual(project.completion_progress, 100.0, places=2)
