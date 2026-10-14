# Part of custom_hr_contract. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrVersion(models.Model):
    _inherit = 'hr.version'

    # === Contract Category ===
    contract_category = fields.Selection(
        selection=[
            ('definite', 'Definite Term'),
            ('indefinite', 'Indefinite Term'),
            ('seasonal', 'Seasonal / Job-based'),
        ],
        string='Contract Category',
        groups='hr.group_hr_user',
        tracking=True,
        help="Vietnamese labor contract category as per Labor Code 2019.",
    )

    # === Itemised Allowances ===
    allowance_meal = fields.Monetary(
        string='Meal Allowance',
        currency_field='currency_id',
        groups='hr.group_hr_user',
        tracking=True,
        help="Monthly meal allowance (Phụ cấp ăn trưa).",
    )
    allowance_transport = fields.Monetary(
        string='Transport Allowance',
        currency_field='currency_id',
        groups='hr.group_hr_user',
        tracking=True,
        help="Monthly transport allowance (Phụ cấp đi lại).",
    )
    allowance_phone = fields.Monetary(
        string='Phone Allowance',
        currency_field='currency_id',
        groups='hr.group_hr_user',
        tracking=True,
        help="Monthly phone allowance (Phụ cấp điện thoại).",
    )
    allowance_housing = fields.Monetary(
        string='Housing Allowance',
        currency_field='currency_id',
        groups='hr.group_hr_user',
        tracking=True,
        help="Monthly housing allowance (Phụ cấp nhà ở).",
    )
    allowance_responsibility = fields.Monetary(
        string='Responsibility Allowance',
        currency_field='currency_id',
        groups='hr.group_hr_user',
        tracking=True,
        help="Monthly responsibility allowance (Phụ cấp trách nhiệm).",
    )
    allowance_other = fields.Monetary(
        string='Other Allowances',
        currency_field='currency_id',
        groups='hr.group_hr_user',
        tracking=True,
        help="Other monthly allowances (Phụ cấp khác).",
    )
    total_allowance = fields.Monetary(
        string='Total Allowances',
        currency_field='currency_id',
        compute='_compute_total_allowance',
        store=True,
        groups='hr.group_hr_user',
        help="Sum of all monthly allowances.",
    )
    total_compensation = fields.Monetary(
        string='Total Compensation',
        currency_field='currency_id',
        compute='_compute_total_compensation',
        store=True,
        groups='hr.group_hr_manager',
        help="Wage + Total Allowances.",
    )

    # === Payment Method ===
    payment_method = fields.Selection(
        selection=[
            ('bank', 'Bank Transfer'),
            ('cash', 'Cash'),
        ],
        string='Payment Method',
        default='bank',
        groups='hr.group_hr_user',
        tracking=True,
        help="Method used to pay the employee's salary.",
    )

    # === Work Schedule Detail ===
    work_hours_per_day = fields.Float(
        string='Working Hours/Day',
        default=8.0,
        groups='hr.group_hr_user',
        tracking=True,
        help="Standard working hours per day.",
    )
    work_days_per_week = fields.Float(
        string='Working Days/Week',
        default=5.0,
        groups='hr.group_hr_user',
        tracking=True,
        help="Standard working days per week.",
    )

    @api.depends(
        'allowance_meal', 'allowance_transport', 'allowance_phone',
        'allowance_housing', 'allowance_responsibility', 'allowance_other',
    )
    def _compute_total_allowance(self):
        for version in self:
            version.total_allowance = (
                (version.allowance_meal or 0.0)
                + (version.allowance_transport or 0.0)
                + (version.allowance_phone or 0.0)
                + (version.allowance_housing or 0.0)
                + (version.allowance_responsibility or 0.0)
                + (version.allowance_other or 0.0)
            )

    @api.depends('wage', 'total_allowance')
    def _compute_total_compensation(self):
        for version in self:
            version.total_compensation = (version.wage or 0.0) + (version.total_allowance or 0.0)
