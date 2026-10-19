# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProjectProject(models.Model):
    _inherit = 'project.project'

    is_concrete_site = fields.Boolean(
        string="Is Concrete Site",
        default=True,
        help="Mark this project as an active Ready-Mix Concrete construction site.",
    )
    project_code = fields.Char(
        string="Project Code",
        index=True,
        copy=False,
        help="Internal engineering/dispatching code for the construction site.",
    )
    fast_legacy_project_code = fields.Char(
        string="Fast ERP Project Code",
        index=True,
        help="Legacy project code imported from Fast ERP.",
    )
    site_address = fields.Char(
        string="Discharge Site Address",
        help="Full physical address or landmark of the concrete discharge site.",
    )
    gps_latitude = fields.Float(
        string="Latitude",
        digits=(10, 7),
        help="GPS Latitude in decimal degrees (e.g. 10.762622).",
    )
    gps_longitude = fields.Float(
        string="Longitude",
        digits=(10, 7),
        help="GPS Longitude in decimal degrees (e.g. 106.660172).",
    )
    geofence_radius_m = fields.Float(
        string="Geofence Radius (m)",
        default=150.0,
        help="Radius in meters from the site center for automated arrival/departure geofence validation.",
    )
    primary_plant_id = fields.Many2one(
        comodel_name='stock.warehouse',
        string="Primary Batching Plant",
        domain="[('is_batching_plant', '=', True)]",
        help="Default batching plant assigned to supply concrete to this site.",
    )
    backup_plant_ids = fields.Many2many(
        comodel_name='stock.warehouse',
        relation='rmc_project_backup_plant_rel',
        column1='project_id',
        column2='warehouse_id',
        string="Backup Batching Plants",
        domain="[('is_batching_plant', '=', True)]",
        help="Alternative batching plants capable of supplying this site in case of high load or plant breakdown.",
    )

    # Progress & Quota Placeholders (ready for Phase 2/4/5 hooks)
    total_contract_quota_m3 = fields.Float(
        string="Total Contract Quota (m³)",
        compute='_compute_rmc_site_metrics',
        inverse='_inverse_rmc_site_metrics',
        store=True,
        readonly=False,
        help="Total contracted volume of concrete for this project.",
    )
    total_delivered_m3 = fields.Float(
        string="Total Delivered Volume (m³)",
        compute='_compute_rmc_site_metrics',
        inverse='_inverse_rmc_site_metrics',
        store=True,
        readonly=False,
        help="Cumulative volume of concrete confirmed as delivered at the job site.",
    )
    remaining_quota_m3 = fields.Float(
        string="Remaining Quota (m³)",
        compute='_compute_rmc_site_metrics',
        store=True,
        help="Contract quota minus delivered volume.",
    )
    completion_progress = fields.Float(
        string="Pouring Completion Progress (%)",
        compute='_compute_rmc_site_metrics',
        store=True,
        help="Percentage of contracted volume that has been delivered.",
    )
    transport_violation_count = fields.Integer(
        string="Transport Violations",
        compute='_compute_rmc_site_metrics',
        inverse='_inverse_rmc_site_metrics',
        store=True,
        readonly=False,
        help="Recorded logistics violations (e.g., geofence bypass, excessive waiting time).",
    )

    @api.constrains('gps_latitude', 'gps_longitude', 'geofence_radius_m')
    def _check_gps_and_geofence(self):
        for project in self:
            if project.gps_latitude and not (-90.0 <= project.gps_latitude <= 90.0):
                raise ValidationError(self.env._("GPS Latitude must be between -90.0 and 90.0 degrees!"))
            if project.gps_longitude and not (-180.0 <= project.gps_longitude <= 180.0):
                raise ValidationError(self.env._("GPS Longitude must be between -180.0 and 180.0 degrees!"))
            if project.geofence_radius_m <= 0:
                raise ValidationError(self.env._("Geofence radius must be strictly positive (greater than 0 meters)!"))

    @api.depends('total_contract_quota_m3', 'total_delivered_m3')
    def _compute_rmc_site_metrics(self):
        for project in self:
            quota = project.total_contract_quota_m3 or 0.0
            delivered = project.total_delivered_m3 or 0.0
            project.remaining_quota_m3 = max(0.0, quota - delivered)
            project.completion_progress = (delivered / quota * 100.0) if quota > 0 else 0.0
            if not project.transport_violation_count:
                project.transport_violation_count = 0

    def _inverse_rmc_site_metrics(self):
        """Allow manual entry and migration until Phase 2/4/5 automated hooks take over."""
        pass

    @api.model_create_multi
    def create(self, vals_list):
        projects = super().create(vals_list)
        for project in projects:
            if project.is_concrete_site:
                if not project.account_id:
                    project._create_analytic_account()
                project._compute_rmc_site_metrics()
        return projects

    def write(self, vals):
        res = super().write(vals)
        if any(k in vals for k in ('total_contract_quota_m3', 'total_delivered_m3')):
            self._compute_rmc_site_metrics()
        return res
