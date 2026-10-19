# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import csv
import io

from odoo import fields, models
from odoo.exceptions import UserError


class RmcFastMigrationWizard(models.TransientModel):
    _name = 'rmc.fast.migration.wizard'
    _description = 'Fast ERP Master Data Migration Wizard'

    migration_type = fields.Selection(
        selection=[
            ('partners', '1. Customers & Suppliers (res.partner)'),
            ('products', '2. Materials & Concrete Grades (product.template)'),
            ('projects', '3. Construction Sites & Balances (project.project)'),
        ],
        string="Migration Entity",
        required=True,
        default='partners',
    )
    import_file = fields.Binary(
        string="CSV Data File",
        required=True,
        help="Upload standard UTF-8 CSV exported from Fast ERP.",
    )
    filename = fields.Char(string="File Name")
    import_log = fields.Text(
        string="Migration Log",
        readonly=True,
        help="Execution outcome and row-by-row status report.",
    )

    def action_import_data(self):
        self.ensure_one()
        if not self.import_file:
            raise UserError(self.env._("Please select a valid CSV file to import!"))

        try:
            if hasattr(self.import_file, 'content'):
                file_bytes = self.import_file.content
            elif isinstance(self.import_file, str):
                file_bytes = base64.b64decode(self.import_file)
            elif isinstance(self.import_file, (bytes, memoryview)):
                file_bytes = bytes(self.import_file)
            else:
                raise UserError(self.env._("Please select a valid CSV file to import!"))

            # Support UTF-8 and UTF-8-SIG (BOM)
            text_data = file_bytes.decode('utf-8-sig')
        except Exception as e:
            raise UserError(self.env._("Failed to read file as UTF-8 encoded CSV: %s", str(e)))

        reader = csv.DictReader(io.StringIO(text_data))
        if not reader.fieldnames:
            raise UserError(self.env._("The uploaded CSV file is empty or missing header columns!"))

        created_count = 0
        updated_count = 0
        skipped_count = 0
        log_entries = []

        if self.migration_type == 'partners':
            created_count, updated_count, skipped_count, log_entries = self._import_partners(reader)
        elif self.migration_type == 'products':
            created_count, updated_count, skipped_count, log_entries = self._import_products(reader)
        elif self.migration_type == 'projects':
            created_count, updated_count, skipped_count, log_entries = self._import_projects(reader)

        summary = (
            f"=== MIGRATION EXECUTION SUMMARY ({self.migration_type.upper()}) ===\n"
            f"Total Processed: {created_count + updated_count + skipped_count}\n"
            f"Created (New): {created_count}\n"
            f"Updated (Upsert): {updated_count}\n"
            f"Skipped / Failed: {skipped_count}\n\n"
            f"=== DETAILS ===\n" + "\n".join(log_entries)
        )

        self.write({'import_log': summary})
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _import_partners(self, reader):
        created, updated, skipped = 0, 0, 0
        logs = []
        partner_obj = self.env['res.partner']

        for row_idx, row in enumerate(reader, start=2):
            name = row.get('name', '').strip()
            if not name:
                skipped += 1
                logs.append(f"Row {row_idx}: Skipped (missing required 'name')")
                continue

            fast_code = row.get('fast_partner_code', '').strip()
            vat = row.get('vat', '').strip()

            vals = {
                'name': name,
                'fast_partner_code': fast_code or False,
                'vat': vat or False,
                'phone': row.get('phone', '').strip() or False,
                'email': row.get('email', '').strip() or False,
                'street': row.get('street', '').strip() or False,
            }
            category = row.get('rmc_partner_category', '').strip().lower()
            if category in {'contractor', 'investor', 'material_supplier', 'other'}:
                vals['rmc_partner_category'] = category

            partner = False
            if fast_code:
                partner = partner_obj.search([('fast_partner_code', '=', fast_code)], limit=1)
            if not partner and vat:
                partner = partner_obj.search([('vat', '=', vat)], limit=1)
            if not partner:
                partner = partner_obj.search([('name', '=ilike', name)], limit=1)

            if partner:
                partner.write(vals)
                updated += 1
                logs.append(f"Row {row_idx}: Updated partner '{name}' (ID: {partner.id})")
            else:
                new_partner = partner_obj.create(vals)
                created += 1
                logs.append(f"Row {row_idx}: Created partner '{name}' (ID: {new_partner.id})")

        return created, updated, skipped, logs

    def _import_products(self, reader):
        created, updated, skipped = 0, 0, 0
        logs = []
        tmpl_obj = self.env['product.template']

        for row_idx, row in enumerate(reader, start=2):
            name = row.get('name', '').strip()
            if not name:
                skipped += 1
                logs.append(f"Row {row_idx}: Skipped (missing required 'name')")
                continue

            fast_code = row.get('fast_legacy_code', '').strip()
            default_code = row.get('default_code', '').strip()
            rmc_type = row.get('rmc_product_type', '').strip().lower()

            vals = {
                'name': name,
                'fast_legacy_code': fast_code or False,
                'default_code': default_code or False,
                'type': 'consu',
            }

            if rmc_type in {'raw_material', 'concrete'}:
                vals['rmc_product_type'] = rmc_type
                vals['is_storable'] = (rmc_type == 'raw_material')

            if row.get('concrete_grade'):
                vals['concrete_grade'] = row.get('concrete_grade', '').strip()
            if row.get('slump_spec'):
                vals['slump_spec'] = row.get('slump_spec', '').strip()
            if row.get('stone_size') in {'1x2', '4x6', 'other'}:
                vals['stone_size'] = row.get('stone_size')

            if row.get('standard_density_ton_m3'):
                try:
                    vals['standard_density_ton_m3'] = float(row.get('standard_density_ton_m3'))
                except ValueError:
                    pass

            product_tmpl = False
            if fast_code:
                product_tmpl = tmpl_obj.search([('fast_legacy_code', '=', fast_code)], limit=1)
            if not product_tmpl and default_code:
                product_tmpl = tmpl_obj.search([('default_code', '=', default_code)], limit=1)
            if not product_tmpl:
                product_tmpl = tmpl_obj.search([('name', '=ilike', name)], limit=1)

            if product_tmpl:
                product_tmpl.write(vals)
                updated += 1
                logs.append(f"Row {row_idx}: Updated product '{name}' (ID: {product_tmpl.id})")
            else:
                new_prod = tmpl_obj.create(vals)
                created += 1
                logs.append(f"Row {row_idx}: Created product '{name}' (ID: {new_prod.id})")

        return created, updated, skipped, logs

    def _import_projects(self, reader):
        created, updated, skipped = 0, 0, 0
        logs = []
        proj_obj = self.env['project.project']

        for row_idx, row in enumerate(reader, start=2):
            name = row.get('name', '').strip()
            if not name:
                skipped += 1
                logs.append(f"Row {row_idx}: Skipped (missing required 'name')")
                continue

            fast_code = row.get('fast_legacy_project_code', '').strip()
            project_code = row.get('project_code', '').strip()

            vals = {
                'name': name,
                'is_concrete_site': True,
                'fast_legacy_project_code': fast_code or False,
                'project_code': project_code or False,
                'site_address': row.get('site_address', '').strip() or False,
            }

            try:
                if row.get('gps_latitude'):
                    vals['gps_latitude'] = float(row.get('gps_latitude'))
                if row.get('gps_longitude'):
                    vals['gps_longitude'] = float(row.get('gps_longitude'))
                if row.get('geofence_radius_m'):
                    vals['geofence_radius_m'] = float(row.get('geofence_radius_m'))
                if row.get('total_contract_quota_m3'):
                    vals['total_contract_quota_m3'] = float(row.get('total_contract_quota_m3'))
                if row.get('total_delivered_m3'):
                    vals['total_delivered_m3'] = float(row.get('total_delivered_m3'))
            except ValueError as e:
                skipped += 1
                logs.append(f"Row {row_idx}: Skipped due to invalid float format: {str(e)}")
                continue

            proj = False
            if fast_code:
                proj = proj_obj.search([('fast_legacy_project_code', '=', fast_code)], limit=1)
            if not proj and project_code:
                proj = proj_obj.search([('project_code', '=', project_code)], limit=1)
            if not proj:
                proj = proj_obj.search([('name', '=ilike', name)], limit=1)

            if proj:
                proj.write(vals)
                updated += 1
                logs.append(f"Row {row_idx}: Updated project site '{name}' (ID: {proj.id})")
            else:
                new_proj = proj_obj.create(vals)
                created += 1
                logs.append(f"Row {row_idx}: Created project site '{name}' (ID: {new_proj.id}, Analytic: {new_proj.account_id.name if new_proj.account_id else 'None'})")

        return created, updated, skipped, logs
