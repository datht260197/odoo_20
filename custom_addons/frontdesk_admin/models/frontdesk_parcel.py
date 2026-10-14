import base64
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


class FrontdeskParcel(models.Model):
    _name = 'frontdesk.parcel'
    _description = 'Frontdesk Parcel'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'received_date desc, id desc'
    _check_company_auto = True

    name = fields.Char(
        string='Parcel Number',
        readonly=True,
        copy=False,
        help="Internal tracking identifier generated automatically upon creation.",
    )
    tracking_ref = fields.Char(
        string='Tracking Reference',
        index=True,
        tracking=True,
        help="Courier tracking number provided by the delivery partner (e.g., DHL, FedEx, VNPost).",
    )
    carrier_id = fields.Many2one(
        comodel_name='res.partner',
        string='Carrier / Delivery Partner',
        check_company=True,
        tracking=True,
        help="Logistics partner or courier delivering the package.",
    )
    recipient_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Recipient',
        required=True,
        index=True,
        check_company=True,
        tracking=True,
        help="Designated recipient employee.",
    )
    delivery_notes = fields.Text(
        string='Handover / Proxy Recipient Notes',
        help="Special instructions, proxy handover authorization, or pickup notes.",
    )
    photo = fields.Image(
        string='Parcel Photo',
        max_width=1920,
        max_height=1920,
        help="Actual photo of the received parcel taken at frontdesk intake.",
    )
    received_date = fields.Datetime(
        string='Received Date',
        default=fields.Datetime.now,
        readonly=True,
        tracking=True,
    )
    delivered_date = fields.Datetime(
        string='Delivered Date',
        readonly=True,
        tracking=True,
    )
    delivered_by_id = fields.Many2one(
        comodel_name='res.users',
        string='Handed Over By',
        readonly=True,
        tracking=True,
        help="Frontdesk officer or user who executed the handover.",
    )
    state = fields.Selection(
        selection=[
            ('received', 'Received'),
            ('notified', 'Notified'),
            ('delivered', 'Delivered'),
            ('returned', 'Returned'),
        ],
        string='State',
        default='received',
        required=True,
        tracking=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name'):
                received_date = vals.get('received_date') or fields.Datetime.now()
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('frontdesk.parcel', sequence_date=received_date)
                    or '/'
                )
        parcels = super().create(vals_list)
        for parcel in parcels:
            if parcel.state == 'received':
                parcel._send_receipt_notification_safe()
        return parcels

    def _send_receipt_notification_safe(self):
        """Send inbox and email notifications with photo attached and transition to 'notified'.
        Never fails or rolls back the transaction.
        """
        for parcel in self:
            try:
                photo_attachment = None
                attachment_ids = []
                if parcel.photo:
                    raw_data = parcel.photo
                    if isinstance(raw_data, str):
                        raw_data = base64.b64decode(raw_data)
                    photo_attachment = self.env['ir.attachment'].create({
                        'name': f"{parcel.name or 'parcel'}_photo.jpg",
                        'type': 'binary',
                        'raw': raw_data,
                        'res_model': 'frontdesk.parcel',
                        'res_id': parcel.id,
                    })
                    attachment_ids.append(photo_attachment.id)

                recipient = parcel.recipient_id
                recipient_user = recipient.user_id
                recipient_email = recipient.work_email

                subject = self.env._("Parcel Received: %s", parcel.name)
                body = self.env._(
                    "<p>Dear %(name)s,</p>"
                    "<p>A parcel (<b>%(ref)s</b>) has been received for you at the frontdesk.</p>"
                    "<ul>"
                    "<li>Tracking Reference: %(tracking)s</li>"
                    "<li>Carrier: %(carrier)s</li>"
                    "<li>Received Date: %(date)s</li>"
                    "</ul>"
                    "<p>Please contact the frontdesk to collect your parcel.</p>",
                    name=recipient.name or '',
                    ref=parcel.name or '',
                    tracking=parcel.tracking_ref or '-',
                    carrier=parcel.carrier_id.name or '-',
                    date=fields.Datetime.to_string(parcel.received_date) if parcel.received_date else '',
                )

                # 1. Real-time User Inbox Notification
                if recipient_user and recipient_user.partner_id:
                    parcel.message_notify(
                        partner_ids=recipient_user.partner_id.ids,
                        subject=subject,
                        body=body,
                        attachment_ids=attachment_ids,
                    )

                # 2. Email Notification with attached photo
                if recipient_email:
                    template = self.env.ref(
                        'frontdesk_admin.mail_template_parcel_received',
                        raise_if_not_found=False,
                    )
                    if template:
                        email_values = {'email_to': recipient_email}
                        if attachment_ids:
                            email_values['attachment_ids'] = [(4, aid) for aid in attachment_ids]
                        template.send_mail(parcel.id, email_values=email_values, force_send=True)
                else:
                    _logger.warning(
                        "Recipient employee '%s' has no work email. Skipping email notification.",
                        recipient.name,
                    )

                # Transition to 'notified'
                parcel.state = 'notified'

            except Exception as exc:
                _logger.error("Failed to dispatch parcel notification for %s: %s", parcel.name, exc)
                # Ensure state progresses to notified even if notification fails
                parcel.state = 'notified'

    def write(self, vals):
        if not (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_manager')
        ):
            # Immutability: Block write on records that are ALREADY in delivered or returned state
            locked_parcels = self.filtered(lambda r: r.state in ('delivered', 'returned'))
            if locked_parcels:
                written_fields = set(vals.keys()) - CHATTER_FIELDS
                if written_fields:
                    raise UserError(self.env._(
                        "Parcel '%s' is in %s state and cannot be modified by non-managers.",
                        locked_parcels[0].display_name,
                        locked_parcels[0].state,
                    ))
        return super().write(vals)

    def unlink(self):
        if not (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_manager')
        ):
            raise AccessError(self.env._("Only Frontdesk Managers are permitted to delete parcels."))
        return super().unlink()

    # -------------------------------------------------------------------------
    # STATE MACHINE ACTIONS
    # -------------------------------------------------------------------------
    def action_deliver(self):
        for parcel in self:
            if parcel.state not in ('received', 'notified'):
                raise UserError(self.env._(
                    "Parcel '%s' can only be delivered from Received or Notified state.",
                    parcel.display_name,
                ))
            parcel.write({
                'state': 'delivered',
                'delivered_date': fields.Datetime.now(),
                'delivered_by_id': self.env.user.id,
            })

    def action_return(self):
        for parcel in self:
            if parcel.state not in ('received', 'notified'):
                raise UserError(self.env._(
                    "Parcel '%s' can only be returned from Received or Notified state.",
                    parcel.display_name,
                ))
            parcel.state = 'returned'

    def action_reset_draft(self):
        self.check_access('write')
        if not (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_manager')
        ):
            raise AccessError(self.env._("Only Frontdesk Managers can reset parcels."))
        self.state = 'received'
