import logging
from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

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


class FrontdeskVisitor(models.Model):
    _name = 'frontdesk.visitor'
    _description = 'Frontdesk Visitor'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'checkin_time desc, id desc'
    _check_company_auto = True

    name = fields.Char(
        string='Visitor Name',
        required=True,
        tracking=True,
    )
    phone = fields.Char(
        string='Phone Number',
    )
    email = fields.Char(
        string='Email',
    )
    company_name = fields.Char(
        string='Visitor Company / Organization',
    )
    purpose = fields.Text(
        string='Purpose of Visit',
        required=True,
    )
    host_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Host Employee',
        required=True,
        index=True,
        check_company=True,
        tracking=True,
    )
    room_id = fields.Many2one(
        comodel_name='frontdesk.meeting.room',
        string='Assigned Room',
        check_company=True,
        tracking=True,
    )
    room_name = fields.Char(
        string='Other Room / Location',
    )
    checkin_time = fields.Datetime(
        string='Check-in Time',
        readonly=True,
        copy=False,
    )
    checkout_time = fields.Datetime(
        string='Check-out Time',
        readonly=True,
        copy=False,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Scheduled'),
            ('arrived', 'In Building'),
            ('departed', 'Departed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
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

    def write(self, vals):
        if not (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_manager')
        ):
            # Immutability: Block write on records that are in departed state
            locked_visitors = self.filtered(lambda r: r.state == 'departed')
            if locked_visitors:
                written_fields = set(vals.keys()) - CHATTER_FIELDS
                if written_fields:
                    raise UserError(self.env._(
                        "Visitor record '%s' is in Departed state and cannot be modified by non-managers.",
                        locked_visitors[0].display_name,
                    ))
        return super().write(vals)

    def unlink(self):
        if not (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_manager')
        ):
            raise AccessError(self.env._("Only Frontdesk Managers are permitted to delete visitor records."))
        return super().unlink()

    # -------------------------------------------------------------------------
    # STATE MACHINE ACTIONS
    # -------------------------------------------------------------------------
    def action_checkin(self):
        for visitor in self:
            if visitor.state != 'draft':
                raise UserError(self.env._(
                    "Only scheduled visitors can be checked in (current status: %s).",
                    visitor.state,
                ))
            visitor.write({
                'state': 'arrived',
                'checkin_time': fields.Datetime.now(),
            })
            visitor._send_arrival_notification_safe()

    def action_checkout(self):
        for visitor in self:
            if visitor.state != 'arrived':
                raise UserError(self.env._(
                    "Only visitors currently in the building can be checked out (current status: %s).",
                    visitor.state,
                ))
            visitor.write({
                'state': 'departed',
                'checkout_time': fields.Datetime.now(),
            })

    def action_cancel(self):
        for visitor in self:
            if visitor.state not in ('draft', 'arrived'):
                raise UserError(self.env._(
                    "Cannot cancel visit '%s' from status %s.",
                    visitor.display_name,
                    visitor.state,
                ))
            visitor.write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.check_access('write')
        if not (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_manager')
        ):
            raise AccessError(self.env._("Only Frontdesk Managers can reset visitor records."))
        self.write({
            'state': 'draft',
            'checkin_time': False,
            'checkout_time': False,
        })

    # -------------------------------------------------------------------------
    # NOTIFICATIONS
    # -------------------------------------------------------------------------
    def _send_arrival_notification_safe(self):
        """Send inbox and email notifications upon visitor arrival.
        Must never fail or roll back the check-in transaction.
        """
        for visitor in self:
            try:
                host = visitor.host_id
                host_user = host.user_id
                host_email = host.work_email
                company_str = visitor.company_name or self.env._('N/A')
                location_str = (visitor.room_id.name or visitor.room_name or self.env._('Reception'))

                subject = self.env._("Visitor Arrived: %s", visitor.name)
                body = self.env._(
                    "Guest %s from %s has arrived and is waiting at reception (Location: %s).",
                    visitor.name,
                    company_str,
                    location_str,
                )

                # 1. Real-time User Inbox Notification
                if host_user and host_user.partner_id:
                    visitor.message_notify(
                        partner_ids=host_user.partner_id.ids,
                        subject=subject,
                        body=body,
                    )
                else:
                    _logger.info(
                        "Host employee '%s' has no linked user account. Skipping inbox notification.",
                        host.name,
                    )

                # 2. Email Notification using QWeb mail template
                if host_email:
                    template = self.env.ref(
                        'frontdesk_admin.mail_template_visitor_arrived',
                        raise_if_not_found=False,
                    )
                    if template:
                        email_values = {'email_to': host_email}
                        template.send_mail(visitor.id, email_values=email_values, force_send=True)
                else:
                    msg = self.env._(
                        "Host employee '%s' has no work email configured. Email notification could not be sent.",
                        host.name,
                    )
                    _logger.warning(msg)
                    visitor.message_post(body=msg)

            except Exception as exc:
                _logger.error(
                    "Failed to dispatch arrival notification for visitor %s: %s",
                    visitor.name,
                    exc,
                )
                visitor.message_post(
                    body=self.env._(
                        "Warning: Automatic notification failed to send due to a system error: %s",
                        str(exc),
                    )
                )
