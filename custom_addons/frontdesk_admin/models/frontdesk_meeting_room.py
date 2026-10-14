from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class FrontdeskMeetingRoom(models.Model):
    _name = 'frontdesk.meeting.room'
    _description = 'Frontdesk Meeting Room'
    _rec_name = 'name'
    _order = 'name asc'
    _check_company_auto = True

    name = fields.Char(
        string='Room Name',
        required=True,
    )
    location = fields.Char(
        string='Location / Floor',
    )
    capacity = fields.Integer(
        string='Capacity (People)',
        default=10,
    )
    has_projector = fields.Boolean(
        string='Projector / Screen',
        default=False,
    )
    has_video_conference = fields.Boolean(
        string='Video Conference Equipment',
        default=False,
    )
    has_whiteboard = fields.Boolean(
        string='Whiteboard',
        default=False,
    )
    equipment_notes = fields.Text(
        string='Equipment Notes',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
    )

    @api.constrains('capacity')
    def _check_capacity(self):
        for room in self:
            if room.capacity < 1:
                raise ValidationError(self.env._("Room capacity must be at least 1 person."))

    def unlink(self):
        if not (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('frontdesk_admin.group_frontdesk_manager')
        ):
            raise AccessError(self.env._("Only Frontdesk Managers are permitted to delete meeting rooms."))
        return super().unlink()
