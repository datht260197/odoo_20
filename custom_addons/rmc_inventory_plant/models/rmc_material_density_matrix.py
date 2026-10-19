# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class RmcMaterialDensityMatrix(models.Model):
    _name = 'rmc.material.density.matrix'
    _description = 'RMC Aggregate Density & Moisture Calibration Matrix'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'plant_id, product_id'

    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    plant_id = fields.Many2one(
        comodel_name='stock.warehouse',
        string="Batching Plant",
        domain="[('is_batching_plant', '=', True)]",
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        string="Raw Material",
        domain="[('rmc_product_type', '=', 'raw_material')]",
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    bulk_density_ton_per_m3 = fields.Float(
        string="Wet/Bulk Density (Ton/m³)",
        digits=(16, 4),
        required=True,
        default=1.45,
        tracking=True,
        help="Apparent density of raw aggregates in wet/moist condition.",
    )
    moisture_percentage = fields.Float(
        string="Actual Moisture (%)",
        digits=(16, 2),
        default=0.0,
        tracking=True,
        help="Tested percentage of water content in aggregate sample.",
    )
    dry_density_ton_per_m3 = fields.Float(
        string="Dry Density (Ton/m³)",
        digits=(16, 4),
        compute='_compute_dry_density',
        store=True,
        help="Dry density calculated using formula: bulk_density / (1 + moisture/100).",
    )
    updated_by_id = fields.Many2one(
        comodel_name='res.users',
        string="Last Updated By",
        default=lambda self: self.env.user,
        readonly=True,
    )

    _check_unique_plant_product = models.Constraint(
        'UNIQUE(plant_id, product_id)',
        'A density matrix record already exists for this plant and material!',
    )

    @api.constrains('bulk_density_ton_per_m3', 'moisture_percentage')
    def _check_density_and_moisture(self):
        for record in self:
            if record.bulk_density_ton_per_m3 <= 0:
                raise ValidationError(self.env._("Bulk density must be strictly positive (greater than 0)!"))
            if record.moisture_percentage < 0 or record.moisture_percentage >= 100:
                raise ValidationError(self.env._("Moisture percentage must be between 0% and 99.99%!"))

    @api.depends('bulk_density_ton_per_m3', 'moisture_percentage')
    def _compute_dry_density(self):
        for record in self:
            divisor = 1.0 + (record.moisture_percentage / 100.0)
            if divisor > 0 and record.bulk_density_ton_per_m3:
                record.dry_density_ton_per_m3 = record.bulk_density_ton_per_m3 / divisor
            else:
                record.dry_density_ton_per_m3 = 0.0

    def write(self, vals):
        if 'updated_by_id' not in vals:
            vals['updated_by_id'] = self.env.user.id
        return super().write(vals)

    @api.model
    def convert_rmc_quantity(self, plant_id, product_id, qty, from_unit, to_unit):
        """Convert aggregate quantities between m3, wet_ton, wet_kg, dry_ton, dry_kg.

        Looks up the active static calibration matrix for (plant_id, product_id).
        Falls back to product standard_density_ton_m3 with 0% moisture if not found.
        """
        valid_units = {'m3', 'wet_ton', 'wet_kg', 'dry_ton', 'dry_kg'}
        if from_unit not in valid_units or to_unit not in valid_units:
            raise UserError(self.env._("Unsupported conversion unit: %s to %s", from_unit, to_unit))

        if qty == 0.0 or from_unit == to_unit:
            return float(qty)

        plant_raw_id = plant_id.id if hasattr(plant_id, 'id') else plant_id
        product_rec = self.env['product.product'].browse(product_id.id if hasattr(product_id, 'id') else product_id)

        matrix = self.search([
            ('plant_id', '=', plant_raw_id),
            ('product_id', '=', product_rec.id),
        ], limit=1)

        if matrix:
            bulk_density = matrix.bulk_density_ton_per_m3
            dry_density = matrix.dry_density_ton_per_m3
        else:
            bulk_density = product_rec.standard_density_ton_m3 or 1.0
            dry_density = bulk_density

        if bulk_density <= 0 or dry_density <= 0:
            raise UserError(self.env._("Invalid density value for material %s at plant %s", product_rec.display_name, plant_raw_id))

        # Convert input to m3
        if from_unit == 'm3':
            m3_qty = qty
        elif from_unit == 'wet_ton':
            m3_qty = qty / bulk_density
        elif from_unit == 'wet_kg':
            m3_qty = (qty / 1000.0) / bulk_density
        elif from_unit == 'dry_ton':
            m3_qty = qty / dry_density
        elif from_unit == 'dry_kg':
            m3_qty = (qty / 1000.0) / dry_density

        # Convert m3 to target unit
        if to_unit == 'm3':
            return float(m3_qty)
        elif to_unit == 'wet_ton':
            return float(m3_qty * bulk_density)
        elif to_unit == 'wet_kg':
            return float(m3_qty * bulk_density * 1000.0)
        elif to_unit == 'dry_ton':
            return float(m3_qty * dry_density)
        elif to_unit == 'dry_kg':
            return float(m3_qty * dry_density * 1000.0)
