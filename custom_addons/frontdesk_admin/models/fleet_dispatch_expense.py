import logging
from odoo import api, fields, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


class FleetDispatchExpense(models.Model):
    _name = 'fleet.dispatch.expense'
    _description = 'Fleet Dispatch Expense'
    _order = 'id asc'
    _check_company_auto = True

    request_id = fields.Many2one(
        comodel_name='fleet.dispatch.request',
        string='Dispatch Request',
        required=True,
        ondelete='cascade',
        index=True,
    )
    expense_type = fields.Selection(
        selection=[
            ('fuel', 'Fuel'),
            ('toll', 'Toll / BOT'),
            ('parking', 'Parking'),
            ('other', 'Other'),
        ],
        string='Expense Type',
        required=True,
        default='toll',
    )
    amount = fields.Monetary(
        string='Amount',
        required=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        related='request_id.currency_id',
        readonly=True,
    )
    receipt_image = fields.Binary(
        string='Receipt Image',
        help="Scanned receipt or bill of the expense.",
    )
    description = fields.Char(
        string='Description',
        help="Brief note or description about this trip expense.",
    )
    payment_status = fields.Selection(
        selection=[
            ('unpaid', 'Unpaid'),
            ('paid', 'Paid'),
        ],
        string='Payment Status',
        default='unpaid',
        required=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        related='request_id.company_id',
        store=True,
        readonly=True,
    )

    def write(self, vals):
        # Strict permission check for marking expense as paid
        if 'payment_status' in vals and vals['payment_status'] == 'paid':
            if not (
                self.env.su
                or self.env.is_system()
                or self.env.user.has_group('frontdesk_admin.group_frontdesk_officer')
                or self.env.user.has_group('frontdesk_admin.group_frontdesk_manager')
            ):
                raise AccessError(self.env._(
                    "Only Frontdesk Officers or Managers are authorized to mark expenses as Paid."
                ))
        return super().write(vals)
