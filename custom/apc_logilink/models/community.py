# -*- coding: utf-8 -*-
from odoo import api, fields, models

class LogilinkCommunity(models.Model):
    _name = "logilink.community"
    _description = "Community Members"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "name"

    id_number = fields.Char("ID Number", required=True, help="Unique identification number for the community member")
    name = fields.Char("Name", required=True, help="Full name of the community member")
    email = fields.Char("Email", help="Email address of the community member")
    phone = fields.Char("Phone", help="Phone number of the community member")
    active = fields.Boolean(default=True, help="Archive/unarchive community member")

    _sql_constraints = [
        ("id_number_unique", "unique(id_number)", "ID Number must be unique."),
    ]

    def action_view_list_export(self):
        """Open list view for exporting data"""
        return {
            'name': 'Community - Export',
            'type': 'ir.actions.act_window',
            'res_model': 'logilink.community',
            'view_mode': 'list',
            'view_id': False,
            'target': 'current',
            'context': self.env.context,
        }
