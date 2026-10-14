from odoo.tests import common, tagged
from odoo.exceptions import AccessError
from odoo import Command


@tagged('post_install', '-at_install')
class TestProjectSecurityTier(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.group_employee = cls.env.ref('base.group_user')
        cls.group_tier_user = cls.env.ref('project_security_tier.group_project_tier_user')
        cls.group_tier_leader = cls.env.ref('project_security_tier.group_project_tier_leader')
        cls.group_project_manager = cls.env.ref('project.group_project_manager')

        # Create test users
        cls.user_regular_1 = cls.env['res.users'].create({
            'name': 'Regular User 1',
            'login': 'user_regular_1',
            'email': 'user1@example.com',
            'group_ids': [Command.set([cls.group_employee.id, cls.group_tier_user.id])],
        })

        cls.user_regular_2 = cls.env['res.users'].create({
            'name': 'Regular User 2',
            'login': 'user_regular_2',
            'email': 'user2@example.com',
            'group_ids': [Command.set([cls.group_employee.id, cls.group_tier_user.id])],
        })

        cls.user_leader = cls.env['res.users'].create({
            'name': 'Leader User',
            'login': 'user_leader',
            'email': 'leader@example.com',
            'group_ids': [Command.set([cls.group_employee.id, cls.group_tier_leader.id])],
        })

        cls.user_manager = cls.env['res.users'].create({
            'name': 'Manager User',
            'login': 'user_manager',
            'email': 'manager@example.com',
            'group_ids': [Command.set([cls.group_employee.id, cls.group_project_manager.id])],
        })

        # Create test projects
        cls.project_leader_owned = cls.env['project.project'].create({
            'name': 'Project Alpha (Leader Owned)',
            'user_id': cls.user_leader.id,
        })

        cls.project_other = cls.env['project.project'].create({
            'name': 'Project Beta (Other)',
            'user_id': cls.user_manager.id,
        })

        # Create stages
        cls.stage_normal = cls.env['project.task.type'].create({
            'name': 'In Progress',
            'is_manager_only': False,
            'project_ids': [Command.set([cls.project_leader_owned.id, cls.project_other.id])],
        })

        cls.stage_restricted = cls.env['project.task.type'].create({
            'name': 'Done / Locked',
            'is_manager_only': True,
            'lock_reason': 'Stage is locked for Manager/Leader only.',
            'project_ids': [Command.set([cls.project_leader_owned.id, cls.project_other.id])],
        })

    def test_01_allocated_hours_permissions(self):
        """Test task creation with allocated_hours and subsequent modifications."""
        # 1. Regular user can create task with initial allocated_hours
        task = self.env['project.task'].with_user(self.user_regular_1).create({
            'name': 'Task Created by Regular 1',
            'project_id': self.project_leader_owned.id,
            'allocated_hours': 10.0,
            'user_ids': [Command.set([self.user_regular_1.id])],
            'stage_id': self.stage_normal.id,
        })
        self.assertEqual(task.allocated_hours, 10.0)

        # 2. Regular user CANNOT modify allocated_hours on existing task
        with self.assertRaises(AccessError):
            task.with_user(self.user_regular_1).write({'allocated_hours': 15.0})

        # 3. Project Leader CAN modify allocated_hours on project they lead
        task.with_user(self.user_leader).write({'allocated_hours': 12.0})
        self.assertEqual(task.allocated_hours, 12.0)

        # 4. Project Manager / Admin CAN modify allocated_hours
        task.with_user(self.user_manager).write({'allocated_hours': 16.0})
        self.assertEqual(task.allocated_hours, 16.0)

        # 5. Project Leader CANNOT modify allocated_hours on project they do NOT lead
        task_other = self.env['project.task'].with_user(self.user_manager).create({
            'name': 'Task in Project Beta',
            'project_id': self.project_other.id,
            'allocated_hours': 5.0,
            'user_ids': [Command.set([self.user_leader.id])],
            'stage_id': self.stage_normal.id,
        })
        with self.assertRaises(AccessError):
            task_other.with_user(self.user_leader).write({'allocated_hours': 20.0})

    def test_02_stage_transition_locks(self):
        """Test stage transition into and out of is_manager_only stages."""
        task = self.env['project.task'].with_user(self.user_regular_1).create({
            'name': 'Stage Test Task',
            'project_id': self.project_leader_owned.id,
            'user_ids': [Command.set([self.user_regular_1.id])],
            'stage_id': self.stage_normal.id,
        })

        # 1. Regular user cannot move task into restricted stage
        with self.assertRaises(AccessError) as cm:
            task.with_user(self.user_regular_1).write({'stage_id': self.stage_restricted.id})
        self.assertIn('Stage is locked for Manager/Leader only.', str(cm.exception))

        # 2. Project Leader can move task into restricted stage
        task.with_user(self.user_leader).write({'stage_id': self.stage_restricted.id})
        self.assertEqual(task.stage_id, self.stage_restricted)

        # 3. Regular user cannot move task OUT of restricted stage
        with self.assertRaises(AccessError) as cm:
            task.with_user(self.user_regular_1).write({'stage_id': self.stage_normal.id})
        self.assertIn('Stage is locked for Manager/Leader only.', str(cm.exception))

        # 4. Project Manager can move task OUT of restricted stage
        task.with_user(self.user_manager).write({'stage_id': self.stage_normal.id})
        self.assertEqual(task.stage_id, self.stage_normal)

    def test_03_task_deletion_restriction(self):
        """Test task deletion restrictions for regular users vs leaders and managers."""
        task_reg = self.env['project.task'].with_user(self.user_regular_1).create({
            'name': 'Task to Delete',
            'project_id': self.project_leader_owned.id,
            'user_ids': [Command.set([self.user_regular_1.id])],
        })

        # Regular user cannot unlink
        with self.assertRaises(AccessError):
            task_reg.with_user(self.user_regular_1).unlink()

        # Leader can unlink task in their project
        task_reg.with_user(self.user_leader).unlink()
        self.assertFalse(task_reg.exists())

    def test_04_task_visibility_isolation(self):
        """Test that regular users can only see their own / assigned tasks."""
        task_u1 = self.env['project.task'].with_user(self.user_manager).create({
            'name': 'Task User 1 Only',
            'project_id': self.project_leader_owned.id,
            'user_ids': [Command.set([self.user_regular_1.id])],
        })

        task_u2 = self.env['project.task'].with_user(self.user_manager).create({
            'name': 'Task User 2 Only',
            'project_id': self.project_leader_owned.id,
            'user_ids': [Command.set([self.user_regular_2.id])],
        })

        tasks_seen_u1 = self.env['project.task'].with_user(self.user_regular_1).search([
            ('id', 'in', [task_u1.id, task_u2.id])
        ])
        self.assertIn(task_u1, tasks_seen_u1)
        self.assertNotIn(task_u2, tasks_seen_u1)

        tasks_seen_u2 = self.env['project.task'].with_user(self.user_regular_2).search([
            ('id', 'in', [task_u1.id, task_u2.id])
        ])
        self.assertIn(task_u2, tasks_seen_u2)
        self.assertNotIn(task_u1, tasks_seen_u2)

        # Leader sees both in their project
        tasks_seen_leader = self.env['project.task'].with_user(self.user_leader).search([
            ('id', 'in', [task_u1.id, task_u2.id])
        ])
        self.assertIn(task_u1, tasks_seen_leader)
        self.assertIn(task_u2, tasks_seen_leader)

    def test_05_vietnamese_localization(self):
        """Test Vietnamese translations for critical security messages."""
        env_vi = self.env(context={'lang': 'vi_VN'})
        msg_allocated = env_vi._("Only Project Leaders or Administrators are allowed to modify allocated hours.")
        self.assertEqual(msg_allocated, "Chỉ Trưởng dự án hoặc Quản trị viên mới được phép điều chỉnh giờ phân bổ.")

        msg_delete = env_vi._("You are not permitted to delete tasks.")
        self.assertEqual(msg_delete, "Bạn không có quyền xóa nhiệm vụ.")

        msg_stage = env_vi._("Only Project Managers or Administrators can move tasks into or out of this stage.")
        self.assertEqual(msg_stage, "Chỉ Trưởng dự án hoặc Quản trị viên mới có thể chuyển nhiệm vụ vào hoặc ra khỏi giai đoạn này.")
