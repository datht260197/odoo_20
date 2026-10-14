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


class FrontdeskDocument(models.Model):
    _name = 'frontdesk.document'
    _description = 'Frontdesk Document'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'internal_ref'
    _order = 'issue_date desc, id desc'
    _check_company_auto = True

    internal_ref = fields.Char(
        string='Internal Ref',
        readonly=True,
        copy=False,
        help="Internal registry sequence assigned automatically upon creation.",
    )
    external_ref = fields.Char(
        string='External Ref',
        index=True,
        help="Official number or reference from the external issuer/authority.",
    )
    doc_type = fields.Selection(
        selection=[
            ('inbound', 'Inbound'),
            ('outbound', 'Outbound'),
            ('contract', 'Contract'),
            ('other', 'Other'),
        ],
        string='Document Type',
        required=True,
        default='inbound',
        tracking=True,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Partner / Authority',
        index=True,
        check_company=True,
        tracking=True,
        help="Sender (for inbound), recipient (for outbound), or signing authority.",
    )
    recipient_id = fields.Many2one(
        comodel_name='hr.employee',
        string='Internal Recipient',
        index=True,
        check_company=True,
        tracking=True,
        help="Internal designated employee handling this document.",
    )
    issue_date = fields.Date(
        string='Issue Date',
        default=fields.Date.context_today,
        tracking=True,
    )
    summary = fields.Text(
        string='Executive Summary',
        help="Overview or abstract of the document content.",
    )
    is_confidential = fields.Boolean(
        string='Confidential',
        default=False,
        tracking=True,
        help="If set, only the designated recipient and Frontdesk Managers can read the summary and scanned files.",
    )
    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment',
        relation='frontdesk_document_attachment_rel',
        column1='document_id',
        column2='attachment_id',
        string='Scanned Files',
    )
    state = fields.Selection(
        selection=[
            ('received', 'Received'),
            ('processing', 'Processing'),
            ('archived', 'Archived'),
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

    can_read_confidential = fields.Boolean(
        string='Can Read Confidential Content',
        compute='_compute_can_read_confidential',
    )

    @api.depends_context('uid')
    @api.depends('is_confidential', 'recipient_id')
    def _compute_can_read_confidential(self):
        is_manager = (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_manager')
        )
        current_user = self.env.user
        for doc in self:
            if not doc.is_confidential or is_manager:
                doc.can_read_confidential = True
            elif doc.recipient_id and doc.recipient_id.user_id == current_user:
                doc.can_read_confidential = True
            else:
                doc.can_read_confidential = False

    def _can_read_confidential(self):
        self.ensure_one()
        if (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_manager')
        ):
            return True
        if self.recipient_id and self.recipient_id.user_id == self.env.user:
            return True
        return False

    def _check_confidential_field_access(self, field_names):
        if (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_manager')
        ):
            return
        confidential_fields = {'summary', 'attachment_ids'}
        if not (confidential_fields & set(field_names)):
            return
        for doc in self:
            if doc.is_confidential and not doc._can_read_confidential():
                raise AccessError(self.env._(
                    "You are not allowed to access confidential content of document '%s'.",
                    doc.display_name or doc.internal_ref or '',
                ))

    def read(self, fields=None, load='_classic_read'):
        if fields is None:
            fields_to_check = set(self._fields.keys())
        else:
            fields_to_check = set(fields)
        self._check_confidential_field_access(fields_to_check)
        return super().read(fields=fields, load=load)

    def __getitem__(self, key):
        if key in ('summary', 'attachment_ids'):
            self._check_confidential_field_access([key])
        return super().__getitem__(key)

    def __getattribute__(self, name):
        if name in ('summary', 'attachment_ids') and not name.startswith('_'):
            try:
                env = super().__getattribute__('env')
                if not (
                    env.su
                    or env.is_system()
                    or env.user.has_group('frontdesk_admin.group_frontdesk_manager')
                ):
                    for record in self:
                        if record.id and super(models.Model, record).__getattribute__('is_confidential'):
                            rec = super(models.Model, record).__getattribute__('recipient_id')
                            if not (rec and rec.user_id == env.user):
                                raise AccessError(env._(
                                    "You are not allowed to access confidential content of document '%s'.",
                                    record.display_name or record.internal_ref or '',
                                ))
            except AttributeError:
                pass
        return super().__getattribute__(name)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('internal_ref'):
                doc_type = vals.get('doc_type', 'inbound')
                seq_code = (
                    'frontdesk.document.outbound'
                    if doc_type == 'outbound'
                    else 'frontdesk.document.inbound'
                )
                issue_date = vals.get('issue_date') or fields.Date.context_today(self)
                vals['internal_ref'] = (
                    self.env['ir.sequence'].next_by_code(seq_code, sequence_date=issue_date)
                    or '/'
                )
        return super().create(vals_list)

    def write(self, vals):
        if not (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_manager')
        ):
            # Immutability: Block write on records that are ALREADY in archived state
            archived_records = self.filtered(lambda r: r.state == 'archived')
            if archived_records:
                written_fields = set(vals.keys()) - CHATTER_FIELDS
                if written_fields:
                    raise UserError(self.env._(
                        "Document '%s' is archived and cannot be modified by non-managers.",
                        archived_records[0].display_name,
                    ))
        return super().write(vals)

    def unlink(self):
        if not (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_manager')
        ):
            raise AccessError(self.env._("Only Frontdesk Managers are permitted to delete documents."))
        return super().unlink()

    # -------------------------------------------------------------------------
    # STATE MACHINE ACTIONS
    # -------------------------------------------------------------------------
    def action_process(self):
        for doc in self:
            if doc.state != 'received':
                raise UserError(self.env._(
                    "Document '%s' can only transition to Processing from Received state.",
                    doc.display_name,
                ))
            doc.state = 'processing'

    def action_archive(self):
        for doc in self:
            if doc.state != 'processing':
                raise UserError(self.env._(
                    "Document '%s' can only transition to Archived from Processing state.",
                    doc.display_name,
                ))
            doc.state = 'archived'

    def action_reset_to_received(self):
        self.check_access('write')
        if not (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_manager')
        ):
            raise AccessError(self.env._("Only Frontdesk Managers can reset archived documents."))
        self.state = 'received'
