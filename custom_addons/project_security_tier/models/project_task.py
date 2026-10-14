from odoo import api, fields, models
from odoo.exceptions import AccessError


class ProjectTask(models.Model):
    _inherit = 'project.task'

    is_project_leader = fields.Boolean(
        string='Is Project Leader or Admin',
        compute='_compute_is_project_leader',
        compute_sudo=False,
    )

    @api.depends('project_id.user_id')
    def _compute_is_project_leader(self):
        is_admin = (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('project.group_project_manager')
        )
        has_leader_group = self.env.user.has_group('project_security_tier.group_project_tier_leader')
        current_uid = self.env.user.id
        for task in self:
            if is_admin:
                task.is_project_leader = True
            elif has_leader_group and task.project_id.user_id.id == current_uid:
                task.is_project_leader = True
            else:
                task.is_project_leader = False

    def write(self, vals):
        is_admin = (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('project.group_project_manager')
        )
        has_leader_group = self.env.user.has_group('project_security_tier.group_project_tier_leader')
        current_uid = self.env.user.id

        # 1. Check allocated_hours modifications on existing tasks
        if 'allocated_hours' in vals and not is_admin:
            for task in self:
                if task.allocated_hours != vals['allocated_hours']:
                    is_leader = has_leader_group and (task.project_id.user_id.id == current_uid)
                    if not is_leader:
                        raise AccessError(self.env._(
                            "Only Project Leaders or Administrators are allowed to modify allocated hours."
                        ))

        # 2. Check stage_id transition restrictions
        if 'stage_id' in vals and not is_admin:
            new_stage = self.env['project.task.type'].browse(vals['stage_id'])
            for task in self:
                old_stage = task.stage_id
                if old_stage != new_stage and (old_stage.is_manager_only or new_stage.is_manager_only):
                    is_leader = has_leader_group and (task.project_id.user_id.id == current_uid)
                    if not is_leader:
                        restricted_stage = new_stage if new_stage.is_manager_only else old_stage
                        lock_msg = restricted_stage.lock_reason or self.env._(
                            "Only Project Managers or Administrators can move tasks into or out of this stage."
                        )
                        raise AccessError(lock_msg)

        return super().write(vals)

    def unlink(self):
        is_admin = (
            self.env.su
            or self.env.is_system()
            or self.env.user.has_group('project.group_project_manager')
        )
        has_leader_group = self.env.user.has_group('project_security_tier.group_project_tier_leader')
        current_uid = self.env.user.id

        if not is_admin:
            for task in self:
                is_leader = has_leader_group and (task.project_id.user_id.id == current_uid)
                if not is_leader:
                    raise AccessError(self.env._("You are not permitted to delete tasks."))

        return super().unlink()
