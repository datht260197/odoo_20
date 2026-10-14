from odoo import fields, models


class ProjectTaskType(models.Model):
    _inherit = 'project.task.type'

    is_manager_only = fields.Boolean(
        string='Leader / Manager Only',
        default=False,
        help="If checked, only Project Leaders or Administrators can move tasks into or out of this stage.",
    )
    lock_reason = fields.Char(
        string='Lock Reason Message',
        default=lambda self: self.env._('Only Project Managers or Administrators can move tasks into or out of this stage.'),
        help="Custom explanation displayed when an unauthorized user attempts to move a task into or out of this stage.",
    )
