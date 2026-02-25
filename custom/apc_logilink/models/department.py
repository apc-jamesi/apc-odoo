# -*- coding: utf-8 -*-
from odoo import api, fields, models

class LogilinkDepartment(models.Model):
    _name = "logilink.department"
    _description = "Department"
    _order = "name"

    name = fields.Char("Name", required=True, help="Department name")
    email = fields.Char("Email", help="Department email address")

    _sql_constraints = [
        ("name_unique", "unique(name)", "Department name must be unique."),
    ]

    def action_view_list_export(self):
        """Open list view for exporting data"""
        return {
            'name': 'Departments - Export',
            'type': 'ir.actions.act_window',
            'res_model': 'logilink.department',
            'view_mode': 'list',
            'view_id': False,
            'target': 'current',
            'context': self.env.context,
        }