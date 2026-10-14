import logging
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

# Fields modified internally by mail thread and activities that shouldn't trigger immutability lock
CHATTER_FIELDS = frozenset({
    'message_follower_ids',
    'message_ids',
    'message_partner_ids',
    'activity_ids',
    'message_main_attachment_id',
    'website_message_ids',
    'message_has_error',
    'message_has_sms_error',
    'message_is_follower',
    'message_needaction',
    'activity_state',
    'activity_user_id',
    'activity_type_id',
    'activity_date_deadline',
    'activity_summary',
    'activity_exception_decoration',
    'activity_exception_icon',
})


class FleetDispatchRequest(models.Model):
    _name = 'fleet.dispatch.request'
    _description = 'Fleet Dispatch Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'start_datetime desc, id desc'
    _check_company_auto = True

    name = fields.Char(
        string='Request Reference',
        readonly=True,
        copy=False,
        help="Registry sequence assigned upon creation.",
    )
    employee_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Requester',
        required=True,
        default=lambda self: self.env.user.employee_id,
        check_company=True,
        tracking=True,
        help="Employee requesting the vehicle dispatch.",
    )
    destination = fields.Char(
        string='Destination / Route',
        required=True,
        tracking=True,
        help="Target destination or itinerary for the trip.",
    )
    purpose = fields.Text(
        string='Trip Purpose',
        required=True,
        help="Business rationale or purpose for the dispatch.",
    )
    passenger_count = fields.Integer(
        string='Passenger Count',
        default=1,
        help="Number of people traveling in the vehicle.",
    )
    start_datetime = fields.Datetime(
        string='Start Date & Time',
        required=True,
        tracking=True,
        help="Expected trip departure time.",
    )
    end_datetime = fields.Datetime(
        string='End Date & Time',
        required=True,
        tracking=True,
        help="Expected trip return time.",
    )
    vehicle_id = fields.Many2one(
        comodel_name='fleet.vehicle',
        string='Assigned Vehicle',
        check_company=True,
        tracking=True,
        help="Fleet vehicle assigned for this trip.",
    )
    driver_id = fields.Many2one(
        comodel_name='res.partner',
        string='Driver',
        check_company=True,
        tracking=True,
        help="Designated driver for the trip.",
    )
    odometer_start = fields.Float(
        string='Start Odometer (km)',
        tracking=True,
        help="Odometer reading when departing frontdesk.",
    )
    odometer_end = fields.Float(
        string='End Odometer (km)',
        tracking=True,
        help="Odometer reading when returning to frontdesk.",
    )
    calendar_event_id = fields.Many2one(
        comodel_name='calendar.event',
        string='Calendar Event',
        readonly=True,
        copy=False,
        help="Linked calendar event to visualize fleet occupancy.",
    )
    expense_ids = fields.One2many(
        comodel_name='fleet.dispatch.expense',
        inverse_name='request_id',
        string='Trip Expenses',
    )
    total_expense_amount = fields.Monetary(
        string='Total Expenses',
        compute='_compute_total_expense',
        store=True,
        currency_field='currency_id',
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('to_approve', 'To Approve'),
            ('approved', 'Approved'),
            ('dispatched', 'Dispatched'),
            ('done', 'Done'),
            ('rejected', 'Rejected'),
            ('cancelled', 'Cancelled'),
        ],
        string='State',
        default='draft',
        required=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Currency',
        related='company_id.currency_id',
        readonly=True,
    )

    # -------------------------------------------------------------------------
    # COMPUTES & CONSTRAINS
    # -------------------------------------------------------------------------
    @api.depends('expense_ids.amount')
    def _compute_total_expense(self):
        for req in self:
            req.total_expense_amount = sum(req.expense_ids.mapped('amount'))

    @api.constrains('start_datetime', 'end_datetime')
    def _check_dates_chronology(self):
        for req in self:
            if req.start_datetime and req.end_datetime and req.start_datetime >= req.end_datetime:
                raise ValidationError(self.env._(
                    "The trip departure date & time must be strictly before the return date & time."
                ))

    @api.constrains('odometer_start', 'odometer_end', 'state')
    def _check_odometer_values(self):
        for req in self:
            if req.state == 'done' or (req.odometer_start and req.odometer_end):
                if req.odometer_end and req.odometer_end < req.odometer_start:
                    raise ValidationError(self.env._(
                        "End Odometer (%(end)s km) cannot be less than Start Odometer (%(start)s km).",
                        end=req.odometer_end,
                        start=req.odometer_start,
                    ))

    @api.constrains('vehicle_id', 'start_datetime', 'end_datetime', 'state')
    def _check_vehicle_collision(self):
        """Strictly prevent booking conflicts on the same vehicle for approved or dispatched trips."""
        for req in self:
            if req.vehicle_id and req.state in ('approved', 'dispatched'):
                overlapping = self.search([
                    ('id', '!=', req.id),
                    ('vehicle_id', '=', req.vehicle_id.id),
                    ('state', 'in', ('approved', 'dispatched')),
                    ('start_datetime', '<', req.end_datetime),
                    ('end_datetime', '>', req.start_datetime),
                ])
                if overlapping:
                    raise ValidationError(self.env._(
                        "Vehicle '%(vehicle)s' is already booked for dispatch request '%(conflict)s' "
                        "from %(start)s to %(end)s.",
                        vehicle=req.vehicle_id.name,
                        conflict=overlapping[0].name,
                        start=fields.Datetime.to_string(overlapping[0].start_datetime),
                        end=fields.Datetime.to_string(overlapping[0].end_datetime),
                    ))

    # -------------------------------------------------------------------------
    # CRUD OVERRIDES
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                start_date = vals.get('start_datetime') or fields.Date.context_today(self)
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('fleet.dispatch.request', sequence_date=start_date)
                    or '/'
                )
        return super().create(vals_list)

    def write(self, vals):
        if not (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_manager')
        ):
            # Immutability: Block write on records that are ALREADY in done or cancelled state
            locked = self.filtered(lambda r: r.state in ('done', 'cancelled'))
            if locked:
                written_fields = set(vals.keys()) - CHATTER_FIELDS
                if written_fields:
                    raise UserError(self.env._(
                        "Dispatch request '%s' is in %s state and cannot be modified by non-managers.",
                        locked[0].name,
                        locked[0].state,
                    ))
        res = super().write(vals)

        # Synchronize linked calendar event if schedule or vehicle changed
        if any(f in vals for f in ('start_datetime', 'end_datetime', 'destination', 'vehicle_id')):
            for req in self:
                if req.calendar_event_id:
                    event_vals = {}
                    if 'start_datetime' in vals:
                        event_vals['start'] = req.start_datetime
                    if 'end_datetime' in vals:
                        event_vals['stop'] = req.end_datetime
                    if 'destination' in vals or 'vehicle_id' in vals:
                        event_vals['name'] = (
                            f"[{req.vehicle_id.name}] {req.destination}"
                            if req.vehicle_id
                            else req.destination
                        )
                    if event_vals:
                        req.calendar_event_id.sudo().write(event_vals)
        return res

    def unlink(self):
        if not (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_manager')
        ):
            raise AccessError(self.env._("Only Frontdesk Managers are permitted to delete dispatch requests."))
        for req in self:
            if req.calendar_event_id:
                req.calendar_event_id.sudo().unlink()
        return super().unlink()

    # -------------------------------------------------------------------------
    # WORKFLOW ACTIONS
    # -------------------------------------------------------------------------
    def action_submit(self):
        for req in self:
            if req.state != 'draft':
                raise UserError(self.env._("Only draft requests can be submitted for approval."))
            req.state = 'to_approve'

    def action_approve(self):
        is_manager = (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_manager')
        )
        current_user = self.env.user
        for req in self:
            if req.state != 'to_approve':
                raise UserError(self.env._("Only pending requests can be approved."))
            # Department Manager authorization check
            is_direct_manager = (
                req.employee_id.parent_id
                and req.employee_id.parent_id.user_id == current_user
            )
            if not (is_manager or is_direct_manager):
                raise AccessError(self.env._(
                    "Only the department manager of '%(employee)s' or a Frontdesk Manager can approve this request.",
                    employee=req.employee_id.name,
                ))
            req.state = 'approved'

    def action_reject(self):
        is_manager = (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_manager')
        )
        current_user = self.env.user
        for req in self:
            if req.state != 'to_approve':
                raise UserError(self.env._("Only pending requests can be rejected."))
            is_direct_manager = (
                req.employee_id.parent_id
                and req.employee_id.parent_id.user_id == current_user
            )
            if not (is_manager or is_direct_manager):
                raise AccessError(self.env._(
                    "Only the department manager of '%(employee)s' or a Frontdesk Manager can reject this request.",
                    employee=req.employee_id.name,
                ))
            req.state = 'rejected'

    def action_dispatch(self):
        for req in self:
            if req.state != 'approved':
                raise UserError(self.env._("Only approved requests can be dispatched."))
            if not req.vehicle_id or not req.driver_id:
                raise UserError(self.env._("Please assign both a vehicle and a driver before dispatching."))

            # Auto-fetch start odometer from vehicle if not already set
            if not req.odometer_start:
                req.odometer_start = req.vehicle_id.sudo().odometer or 0.0

            # Automatically create or sync linked calendar event
            if not req.calendar_event_id:
                partner_ids = []
                if req.driver_id:
                    partner_ids.append((4, req.driver_id.id))
                if req.employee_id.work_contact_id:
                    partner_ids.append((4, req.employee_id.work_contact_id.id))

                event = self.env['calendar.event'].sudo().create({
                    'name': f"[{req.vehicle_id.name}] {req.destination}",
                    'start': req.start_datetime,
                    'stop': req.end_datetime,
                    'partner_ids': partner_ids,
                    'description': self.env._(
                        "Dispatch Request: %(ref)s\nPurpose: %(purpose)s\nDriver: %(driver)s",
                        ref=req.name,
                        purpose=req.purpose,
                        driver=req.driver_id.name or '',
                    ),
                })
                req.calendar_event_id = event.id

            req.state = 'dispatched'

    def action_done(self):
        for req in self:
            if req.state != 'dispatched':
                raise UserError(self.env._("Only dispatched trips can be marked as completed."))
            if not req.odometer_end:
                raise UserError(self.env._("Please record the End Odometer reading upon trip return."))
            if req.odometer_end < req.odometer_start:
                raise ValidationError(self.env._(
                    "End Odometer (%(end)s km) cannot be less than Start Odometer (%(start)s km).",
                    end=req.odometer_end,
                    start=req.odometer_start,
                ))

            # Automatically record native fleet.vehicle.odometer
            self.env['fleet.vehicle.odometer'].sudo().create({
                'vehicle_id': req.vehicle_id.id,
                'value': req.odometer_end,
                'date': fields.Date.context_today(self),
            })

            req.state = 'done'

    def action_cancel(self):
        for req in self:
            if req.state in ('done', 'cancelled'):
                raise UserError(self.env._("Cannot cancel requests that are already done or cancelled."))
            # Unlink calendar event when cancelled
            if req.calendar_event_id:
                event = req.calendar_event_id
                req.calendar_event_id = False
                event.sudo().unlink()
            req.state = 'cancelled'

    def action_reset_draft(self):
        self.check_access('write')
        if not (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_manager')
        ):
            raise AccessError(self.env._("Only Frontdesk Managers can reset completed or cancelled trips."))
        for req in self:
            if req.calendar_event_id:
                event = req.calendar_event_id
                req.calendar_event_id = False
                event.sudo().unlink()
            req.state = 'draft'

    def action_view_calendar_event(self):
        self.ensure_one()
        if not self.calendar_event_id:
            return False
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'calendar.event',
            'view_mode': 'form',
            'res_id': self.calendar_event_id.id,
            'target': 'current',
        }
