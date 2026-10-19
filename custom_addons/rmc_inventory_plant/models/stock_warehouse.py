# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    is_batching_plant = fields.Boolean(
        string="Is Batching Plant",
        default=False,
        help="Check this box if this warehouse is an RMC batching plant.",
    )
    plant_code = fields.Char(
        string="Plant Code (BMES/ACS)",
        index=True,
        copy=False,
        help="Unique identifier of the batching plant in BMES and ACS batching systems.",
    )
    capacity_m3_per_hour = fields.Float(
        string="Design Capacity (m³/h)",
        help="Nominal batching output capacity in cubic meters per hour.",
    )
    plant_manager_id = fields.Many2one(
        comodel_name='hr.employee',
        string="Plant Manager",
        help="Employee in charge of operational management at this batching plant.",
    )
    density_matrix_ids = fields.One2many(
        comodel_name='rmc.material.density.matrix',
        inverse_name='plant_id',
        string="Density Matrices",
        help="Active density and moisture calibration matrix for materials at this plant.",
    )

    _check_unique_plant_code = models.Constraint(
        'UNIQUE(company_id, plant_code)',
        'The batching plant code must be unique per company!',
    )
