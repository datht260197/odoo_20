# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    rmc_product_type = fields.Selection(
        selection=[
            ('raw_material', 'Raw Material'),
            ('concrete', 'Ready-Mix Concrete'),
        ],
        string="RMC Product Type",
        help="Classification of ready-mix concrete items vs batching raw ingredients.",
    )
    acs_material_code = fields.Char(
        string="ACS Material Code",
        index=True,
        help="Material code used in the ACS truck scale system.",
    )
    bmes_material_code = fields.Char(
        string="BMES Material Code",
        index=True,
        help="Material code used in the BMES batching control system.",
    )
    fast_legacy_code = fields.Char(
        string="Fast ERP Material Code",
        index=True,
        help="Legacy material code imported from Fast ERP.",
    )

    # Concrete technical specs
    concrete_grade = fields.Char(
        string="Concrete Grade",
        help="Concrete compressive strength grade (e.g. M150, M200, M250, M300, M350, M400, M450, M500).",
    )
    slump_spec = fields.Char(
        string="Slump Spec (cm)",
        help="Design slump specification (e.g. 10±2, 12±2).",
    )
    stone_size = fields.Selection(
        selection=[
            ('1x2', 'Stone 1x2'),
            ('4x6', 'Stone 4x6'),
            ('other', 'Other'),
        ],
        string="Stone Size",
        help="Maximum aggregate coarse stone sizing used in the concrete mix.",
    )

    # Raw material fallback density
    standard_density_ton_m3 = fields.Float(
        string="Standard Density (Ton/m³)",
        digits=(16, 4),
        default=1.0,
        help="Baseline theoretical density used for volumetric conversion when plant matrix is not calibrated.",
    )
