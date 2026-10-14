import logging
import os
import stat
from odoo import api, models
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    def _can_user_access_confidential_attachment(self, attachment):
        """Check if current user can access an attachment linked to a frontdesk.document."""
        if (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_manager')
        ):
            return True

        current_user = self.env.user

        # 1. Direct res_model / res_id link
        if attachment.res_model == 'frontdesk.document' and attachment.res_id:
            doc = self.env['frontdesk.document'].browse(attachment.res_id).sudo()
            if doc.exists() and doc.is_confidential:
                if not (doc.recipient_id and doc.recipient_id.user_id == current_user):
                    return False

        # 2. Linked via Many2many attachment_ids on frontdesk.document
        if attachment.id:
            conf_docs = self.env['frontdesk.document'].sudo().search([
                ('attachment_ids', 'in', attachment.id),
                ('is_confidential', '=', True),
            ])
            for doc in conf_docs:
                if not (doc.recipient_id and doc.recipient_id.user_id == current_user):
                    return False

        return True

    def _check_confidential_attachment_access(self):
        """Strictly raise AccessError if an unauthorized user attempts to read confidential attachments."""
        if (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_manager')
        ):
            return

        for attachment in self:
            if not self._can_user_access_confidential_attachment(attachment):
                raise AccessError(self.env._(
                    "You are not allowed to access attachments of confidential documents."
                ))

    def read(self, fields=None, load='_classic_read'):
        self._check_confidential_attachment_access()
        return super().read(fields=fields, load=load)

    def _check_access(self, operation: str):
        if operation == 'read' and not (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_manager')
        ):
            for attachment in self:
                if not self._can_user_access_confidential_attachment(attachment):
                    return attachment, lambda: AccessError(self.env._(
                        "You are not allowed to access attachments of confidential documents."
                    ))
        return super()._check_access(operation)

    def _compute_res_access(self, operation: str):
        super()._compute_res_access(operation)
        if not (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_manager')
        ):
            field_name = f'res_access_{operation}'
            for attachment in self:
                if not self._can_user_access_confidential_attachment(attachment):
                    attachment[field_name] = False

    def _inaccessible_comodel_records(self, model_and_ids, operation):
        for res_model, res_id in super()._inaccessible_comodel_records(model_and_ids, operation):
            yield res_model, res_id

        if not (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_manager')
        ):
            if 'frontdesk.document' in model_and_ids:
                doc_ids = model_and_ids['frontdesk.document']
                docs = self.env['frontdesk.document'].browse(doc_ids).sudo()
                for doc in docs:
                    if doc.is_confidential:
                        if not (doc.recipient_id and doc.recipient_id.user_id == self.env.user):
                            yield 'frontdesk.document', doc.id

    def _gc_file_store_unsafe(self, grace_period):
        """Safely handle Windows PermissionError and GC assertion error during filestore GC."""
        filestore_dir = self._filestore()
        if os.path.isdir(filestore_dir):
            for dirpath, _subdirs, filenames in os.walk(filestore_dir):
                for filename in filenames:
                    p = os.path.join(dirpath, filename)
                    try:
                        os.chmod(p, stat.S_IWRITE)
                    except OSError:
                        pass
                    if filename.endswith('.__gc'):
                        try:
                            os.unlink(p)
                        except OSError:
                            pass
        try:
            return super()._gc_file_store_unsafe(grace_period)
        except (PermissionError, AssertionError, OSError) as e:
            _logger.warning("Suppressed filestore GC error (%s) on Windows safely.", e)
