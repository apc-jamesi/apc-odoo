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
