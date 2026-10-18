# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestItTicket(TransactionCase):
    """Automated tests for IT Helpdesk ticket lifecycle and access controls."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        # Security groups
        cls.group_it_user = cls.env.ref('it_helpdesk.group_it_user')
        cls.group_it_manager = cls.env.ref('it_helpdesk.group_it_manager')

        # Users
        cls.user_it_staff = cls.env['res.users'].create({
            'name': 'IT Technician Ken',
            'login': 'ken_tech',
            'email': 'ken@example.com',
            'group_ids': [(6, 0, [cls.group_it_user.id])],
        })
        cls.user_it_manager = cls.env['res.users'].create({
            'name': 'IT Manager Boss',
            'login': 'boss_it',
            'email': 'boss@example.com',
            'group_ids': [(6, 0, [cls.group_it_manager.id])],
        })
        cls.user_regular = cls.env['res.users'].create({
            'name': 'Regular Employee Jane',
            'login': 'jane_reg',
            'email': 'jane@example.com',
            'group_ids': [(6, 0, [cls.env.ref('base.group_user').id])],
        })

        # Department & Employees
        cls.department = cls.env['hr.department'].create({
            'name': 'Operations Department',
        })
        cls.employee_jane = cls.env['hr.employee'].create({
            'name': 'Jane Employee',
            'user_id': cls.user_regular.id,
            'department_id': cls.department.id,
            'work_phone': '0901234567',
        })

        # IT Team
        cls.it_team = cls.env['it.team'].create({
            'name': 'Tier 1 Support Helpdesk',
            'user_id': cls.user_it_manager.id,
        })

        # IT Asset
        cls.asset = cls.env['it.asset'].create({
            'name': 'ThinkPad T14s LAPTOP-001',
            'serial_number': 'SN-TP-123456',
            'category_type': 'laptop',
            'employee_id': cls.employee_jane.id,
            'state': 'in_use',
        })

    def test_01_create_ticket_automatic_sequence(self):
        """Creating a ticket auto-generates sequential identifier and sets defaults."""
        ticket = self.env['it.ticket'].with_user(self.user_it_staff).create({
            'title': 'Cannot connect to company VPN',
            'request_type': 'incident',
            'category_id': 'network',
            'partner_id': False,
            'employee_id': self.employee_jane.id,
            'team_id': self.it_team.id,
            'priority': '2',
        })
        self.assertTrue(ticket.name)
        self.assertNotEqual(ticket.name, 'New')
        self.assertEqual(ticket.state, 'new')
        self.assertEqual(ticket.phone, '0901234567')
        self.assertEqual(ticket.department_id, self.department)

    def test_02_state_workflow_transitions(self):
        """Ticket transitions through workflow: new -> in_progress -> done."""
        ticket = self.env['it.ticket'].with_user(self.user_it_staff).create({
            'title': 'Outlook email synchronization issue',
            'request_type': 'service_request',
            'category_id': 'email',
            'employee_id': self.employee_jane.id,
            'team_id': self.it_team.id,
        })
        self.assertEqual(ticket.state, 'new')

        # Start handling
        ticket.action_set_in_progress()
        self.assertEqual(ticket.state, 'in_progress')
        self.assertTrue(ticket.date_opened)

        # Complete ticket
        ticket.action_set_done()
        self.assertEqual(ticket.state, 'done')
        self.assertTrue(ticket.date_closed)

    def test_03_locked_states_protection_for_non_manager(self):
        """Locked state prevents regular users from altering core fields."""
        ticket = self.env['it.ticket'].with_user(self.user_it_staff).create({
            'title': 'Printer toner replacement needed',
            'request_type': 'service_request',
            'category_id': 'printer',
            'employee_id': self.employee_jane.id,
            'team_id': self.it_team.id,
        })
        ticket.action_set_in_progress()

        # Regular user attempt to change title should raise UserError
        with self.assertRaises(UserError):
            ticket.with_user(self.user_regular).write({
                'title': 'Tampered title by unauthorized user',
            })

        # Manager is authorized to modify even when locked
        ticket.with_user(self.user_it_manager).write({
            'title': 'Updated Title by IT Manager',
        })
        self.assertEqual(ticket.title, 'Updated Title by IT Manager')

    def test_04_asset_association_and_repair_computation(self):
        """Linking asset to ticket computes repair flags and populates metadata."""
        ticket = self.env['it.ticket'].with_user(self.user_it_staff).create({
            'title': 'Broken laptop screen hinge',
            'request_type': 'incident',
            'category_id': 'laptop',
            'asset_id': self.asset.id,
            'repair_type': 'external',
            'repair_cost': 1500000.0,
        })
        self.assertEqual(ticket.asset_serial, 'SN-TP-123456')
        self.assertTrue(ticket.has_repair)
        self.assertIn(ticket, self.asset.ticket_ids)

    def test_05_role_template_creation(self):
        """Role templates can be defined per department with baseline permissions."""
        template = self.env['it.department.role.template'].create({
            'name': 'DevOps Lead Role Template',
            'code': 'DEVOPS_LEAD',
            'department_id': self.department.id,
            'role_type': 'manager',
            'group_ids': [(6, 0, [self.group_it_manager.id])],
        })
        self.assertEqual(template.department_id, self.department)
        self.assertTrue(template.active)
