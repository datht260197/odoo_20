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


class FrontdeskRoomBooking(models.Model):
    _name = 'frontdesk.room.booking'
    _description = 'Meeting Room Booking'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'start_datetime desc, id desc'
    _check_company_auto = True

    name = fields.Char(
        string='Meeting Subject',
        required=True,
        tracking=True,
    )
    room_id = fields.Many2one(
        comodel_name='frontdesk.meeting.room',
        string='Meeting Room',
        required=True,
        index=True,
        check_company=True,
        tracking=True,
    )
    organizer_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Organizer',
        required=True,
        index=True,
        default=lambda self: self.env.user.employee_id,
        check_company=True,
        tracking=True,
    )
    start_datetime = fields.Datetime(
        string='Start Date & Time',
        required=True,
        tracking=True,
    )
    end_datetime = fields.Datetime(
        string='End Date & Time',
        required=True,
        tracking=True,
    )
    attendee_count = fields.Integer(
        string='Attendee Count',
        default=1,
    )
    needs_teabreak = fields.Boolean(
        string='Request Teabreak / Drinks',
        default=False,
    )
    teabreak_attendees = fields.Integer(
        string='Teabreak Headcount',
    )
    teabreak_notes = fields.Text(
        string='Teabreak Notes',
    )
    calendar_event_id = fields.Many2one(
        comodel_name='calendar.event',
        string='Calendar Event',
        readonly=True,
        copy=False,
        ondelete='set null',
    )
    state = fields.Selection(
        selection=[
            ('pending', 'Pending Approval'),
            ('confirmed', 'Confirmed'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='pending',
        required=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )

    # -------------------------------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------------------------------
    @api.constrains('room_id', 'start_datetime', 'end_datetime', 'state')
    def _check_booking_collision_and_timing(self):
        for booking in self:
            if booking.start_datetime and booking.end_datetime:
                if booking.end_datetime <= booking.start_datetime:
                    raise ValidationError(self.env._(
                        "End Date & Time must be strictly after Start Date & Time."
                    ))

            if (
                booking.state == 'confirmed'
                and booking.room_id
                and booking.start_datetime
                and booking.end_datetime
            ):
                collision_count = self.search_count([
                    ('id', '!=', booking.id),
                    ('room_id', '=', booking.room_id.id),
                    ('state', '=', 'confirmed'),
                    ('start_datetime', '<', booking.end_datetime),
                    ('end_datetime', '>', booking.start_datetime),
                ])
                if collision_count > 0:
                    raise ValidationError(self.env._(
                        "Room '%s' is already booked for another confirmed meeting during this time slot (%s to %s).",
                        booking.room_id.display_name,
                        booking.start_datetime,
                        booking.end_datetime,
                    ))

    @api.constrains('attendee_count')
    def _check_attendee_count(self):
        for booking in self:
            if booking.attendee_count < 1:
                raise ValidationError(self.env._("Attendee count must be at least 1 person."))

    # -------------------------------------------------------------------------
    # IMMUTABILITY & ACCESS CHECKS
    # -------------------------------------------------------------------------
    def write(self, vals):
        if not (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_manager')
        ):
            locked_bookings = self.filtered(lambda r: r.state in ('done', 'cancelled'))
            if locked_bookings:
                written_fields = set(vals.keys()) - CHATTER_FIELDS
                if written_fields:
                    raise UserError(self.env._(
                        "Booking '%s' is in %s state and cannot be modified by non-managers.",
                        locked_bookings[0].display_name,
                        locked_bookings[0].state,
                    ))
        return super().write(vals)

    def unlink(self):
        if not (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_manager')
        ):
            raise AccessError(self.env._("Only Frontdesk Managers are permitted to delete room bookings."))
        # Also cleanly unlink linked calendar events if any
        for booking in self:
            if booking.calendar_event_id:
                booking.calendar_event_id.sudo().unlink()
        return super().unlink()

    # -------------------------------------------------------------------------
    # STATE MACHINE ACTIONS
    # -------------------------------------------------------------------------
    def action_confirm(self):
        if not (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_officer')
        ):
            raise AccessError(self.env._("Only Frontdesk Officers or Managers can approve room bookings."))

        for booking in self:
            if booking.state != 'pending':
                raise UserError(self.env._(
                    "Only pending bookings can be confirmed (current status: %s).",
                    booking.state,
                ))

            booking.write({'state': 'confirmed'})
            booking._sync_calendar_event()
            if booking.needs_teabreak:
                booking._create_teabreak_activity()

    def action_done(self):
        if not (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_officer')
        ):
            raise AccessError(self.env._("Only Frontdesk Officers or Managers can complete room bookings."))

        for booking in self:
            if booking.state != 'confirmed':
                raise UserError(self.env._(
                    "Only confirmed bookings can be marked as completed (current status: %s).",
                    booking.state,
                ))
            booking.write({'state': 'done'})

    def action_cancel(self):
        is_officer_or_manager = (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_officer')
        )

        for booking in self:
            if booking.state not in ('pending', 'confirmed'):
                raise UserError(self.env._(
                    "Cannot cancel booking '%s' from status %s.",
                    booking.display_name,
                    booking.state,
                ))

            if not is_officer_or_manager:
                # Regular users can only cancel their own pending booking
                if booking.state != 'pending' or not (
                    booking.organizer_id.user_id == self.env.user
                    or booking.create_uid == self.env.user
                ):
                    raise AccessError(self.env._(
                        "You can only cancel your own bookings in Pending status."
                    ))

            # Unlink linked calendar event
            if booking.calendar_event_id:
                booking.calendar_event_id.sudo().unlink()
                booking.calendar_event_id = False

            booking.write({'state': 'cancelled'})

    def action_reset_pending(self):
        if not (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_manager')
        ):
            raise AccessError(self.env._("Only Frontdesk Managers can reset room bookings."))

        for booking in self:
            if booking.calendar_event_id:
                booking.calendar_event_id.sudo().unlink()
                booking.calendar_event_id = False
            booking.write({'state': 'pending'})

    # -------------------------------------------------------------------------
    # INTEGRATION HELPERS
    # -------------------------------------------------------------------------
    def _sync_calendar_event(self):
        """Create or update linked calendar.event on confirmation."""
        for booking in self:
            room_name = booking.room_id.name or self.env._("Meeting Room")
            event_title = f"[{room_name}] {booking.name}"
            location = (
                f"{booking.room_id.name} ({booking.room_id.location})"
                if booking.room_id.location
                else booking.room_id.name
            )

            partner_ids = []
            if booking.organizer_id.user_id and booking.organizer_id.user_id.partner_id:
                partner_ids.append(booking.organizer_id.user_id.partner_id.id)

            event_vals = {
                'name': event_title,
                'start': booking.start_datetime,
                'stop': booking.end_datetime,
                'location': location,
                'user_id': booking.organizer_id.user_id.id or self.env.uid,
                'description': booking.teabreak_notes or False,
                'res_model': 'frontdesk.room.booking',
                'res_id': booking.id,
            }
            if partner_ids:
                event_vals['partner_ids'] = [(6, 0, partner_ids)]

            if booking.calendar_event_id:
                booking.calendar_event_id.sudo().write(event_vals)
            else:
                event = self.env['calendar.event'].sudo().create(event_vals)
                booking.calendar_event_id = event.id

    def _create_teabreak_activity(self):
        """Schedule a teabreak preparation activity for Frontdesk Officers."""
        officer_group = self.env.ref('frontdesk_admin.group_frontdesk_officer', raise_if_not_found=False)
        target_user = False
        if officer_group:
            officer_users = officer_group.user_ids.filtered(lambda u: u.active and not u.share).sorted('id')
            if officer_users:
                target_user = officer_users[0]

        if not target_user:
            target_user = self.env.user

        todo_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        if not todo_type:
            todo_type = self.env['mail.activity.type'].search([('category', '=', 'default')], limit=1)

        for booking in self:
            headcount = booking.teabreak_attendees or booking.attendee_count
            notes = booking.teabreak_notes or self.env._("None")
            summary = self.env._("Prepare Teabreak for %s", booking.name)
            note = self.env._(
                "Room: %s. Headcount: %s. Teabreak details: %s",
                booking.room_id.name,
                headcount,
                notes,
            )
            deadline = booking.start_datetime.date() if booking.start_datetime else fields.Date.today()

            # Schedule activity using mail.activity.mixin helper
            booking.activity_schedule(
                activity_type_id=todo_type.id if todo_type else False,
                summary=summary,
                note=note,
                user_id=target_user.id,
                date_deadline=deadline,
            )
