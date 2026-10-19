# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    fast_partner_code = fields.Char(
        string="Fast ERP Partner Code",
        index=True,
        help="Unique customer or vendor accounting code from Fast ERP.",
    )
    rmc_partner_category = fields.Selection(
        selection=[
            ('contractor', 'Building Contractor'),
            ('investor', 'Project Investor'),
            ('material_supplier', 'Raw Material Supplier'),
            ('other', 'Other'),
        ],
        string="RMC Partner Category",
        help="Industry role classification for concrete logistics and credit management.",
    )
