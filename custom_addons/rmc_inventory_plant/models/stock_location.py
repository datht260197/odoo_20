# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class StockLocation(models.Model):
    _inherit = 'stock.location'

    rmc_storage_type = fields.Selection(
        selection=[
            ('silo', 'Cement / Fly Ash Silo'),
            ('aggregate_bin', 'Aggregate Bin / Hopper (Sand/Stone)'),
            ('admixture_tank', 'Admixture Tank'),
            ('water_tank', 'Water Tank'),
        ],
        string="RMC Storage Type",
        help="Physical storage unit type for batching materials.",
    )
    max_capacity_ton = fields.Float(
        string="Max Capacity (Tons)",
        help="Maximum safe physical storage capacity in metric tons.",
    )
