# Part of Odoo. See LICENSE file for full copyright and licensing details.

from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError, UserError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestRmcDensityMatrix(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.plant = cls.env['stock.warehouse'].create({
            'name': 'Test Batching Plant 01',
            'code': 'TBP01',
            'is_batching_plant': True,
            'plant_code': 'PLANT-001',
            'capacity_m3_per_hour': 120.0,
        })
        cls.sand_tmpl = cls.env['product.template'].create({
            'name': 'Gold Sand Standard',
            'type': 'consu',
            'is_storable': True,
            'rmc_product_type': 'raw_material',
            'standard_density_ton_m3': 1.40,
        })
        cls.sand_product = cls.sand_tmpl.product_variant_id

    def test_01_density_math_and_computation(self):
        """Test dry density computation formula: bulk / (1 + moisture/100)."""
        matrix = self.env['rmc.material.density.matrix'].create({
            'plant_id': self.plant.id,
            'product_id': self.sand_product.id,
            'bulk_density_ton_per_m3': 1.50,
            'moisture_percentage': 5.0,
        })
        expected_dry = 1.50 / (1.0 + 0.05)
        self.assertAlmostEqual(matrix.dry_density_ton_per_m3, expected_dry, places=4)

        # Update moisture percentage and verify recomputation
        matrix.write({'moisture_percentage': 10.0})
        expected_dry_updated = 1.50 / 1.10
        self.assertAlmostEqual(matrix.dry_density_ton_per_m3, expected_dry_updated, places=4)

    def test_02_validation_constrains(self):
        """Test validation error for invalid density and moisture percentage."""
        with self.assertRaises(ValidationError):
            self.env['rmc.material.density.matrix'].create({
                'plant_id': self.plant.id,
                'product_id': self.sand_product.id,
                'bulk_density_ton_per_m3': -1.2,
                'moisture_percentage': 5.0,
            })

        with self.assertRaises(ValidationError):
            self.env['rmc.material.density.matrix'].create({
                'plant_id': self.plant.id,
                'product_id': self.sand_product.id,
                'bulk_density_ton_per_m3': 1.5,
                'moisture_percentage': 105.0,
            })

    def test_03_unique_constraint_plant_product(self):
        """Test that duplicate density records for the same plant and product raise IntegrityError."""
        self.env['rmc.material.density.matrix'].create({
            'plant_id': self.plant.id,
            'product_id': self.sand_product.id,
            'bulk_density_ton_per_m3': 1.45,
            'moisture_percentage': 4.0,
        })
        with mute_logger('odoo.sql_db'), self.assertRaises(IntegrityError):
            with self.cr.savepoint():
                self.env['rmc.material.density.matrix'].create({
                    'plant_id': self.plant.id,
                    'product_id': self.sand_product.id,
                    'bulk_density_ton_per_m3': 1.50,
                    'moisture_percentage': 2.0,
                })

    def test_04_quantity_conversions_with_matrix(self):
        """Test convert_rmc_quantity with an active matrix record."""
        # 1.5 ton/m3 bulk, 0% moisture => 1.5 ton/m3 dry
        self.env['rmc.material.density.matrix'].create({
            'plant_id': self.plant.id,
            'product_id': self.sand_product.id,
            'bulk_density_ton_per_m3': 1.50,
            'moisture_percentage': 0.0,
        })

        # 10 m3 -> wet_ton: 10 * 1.5 = 15.0 ton
        wet_ton = self.env['rmc.material.density.matrix'].convert_rmc_quantity(
            self.plant.id, self.sand_product.id, 10.0, 'm3', 'wet_ton'
        )
        self.assertAlmostEqual(wet_ton, 15.0, places=4)

        # 15.0 wet_ton -> wet_kg: 15,000 kg
        wet_kg = self.env['rmc.material.density.matrix'].convert_rmc_quantity(
            self.plant.id, self.sand_product.id, 15.0, 'wet_ton', 'wet_kg'
        )
        self.assertAlmostEqual(wet_kg, 15000.0, places=2)

        # 15,000 wet_kg -> m3: 10.0 m3
        m3_res = self.env['rmc.material.density.matrix'].convert_rmc_quantity(
            self.plant.id, self.sand_product.id, 15000.0, 'wet_kg', 'm3'
        )
        self.assertAlmostEqual(m3_res, 10.0, places=4)

    def test_05_quantity_conversions_fallback_standard_density(self):
        """Test fallback to standard_density_ton_m3 when no matrix record exists."""
        other_sand = self.env['product.template'].create({
            'name': 'Black Sand Uncalibrated',
            'type': 'consu',
            'is_storable': True,
            'rmc_product_type': 'raw_material',
            'standard_density_ton_m3': 1.40,
        }).product_variant_id

        # 10 m3 -> wet_ton should use standard 1.40: 10 * 1.40 = 14.0
        wet_ton = self.env['rmc.material.density.matrix'].convert_rmc_quantity(
            self.plant.id, other_sand.id, 10.0, 'm3', 'wet_ton'
        )
        self.assertAlmostEqual(wet_ton, 14.0, places=4)
