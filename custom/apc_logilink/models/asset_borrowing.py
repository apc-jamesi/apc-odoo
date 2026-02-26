# -*- coding: utf-8 -*-
from odoo import api, fields, models

class LogilinkAssetBorrowing(models.Model):
    _name = "logilink.asset.borrowing"
    _description = "Asset Borrowing / Asset Assignment"
    _order = "borrowed_date desc, name desc"

    name = fields.Char("Reference", compute="_compute_name", store=True, readonly=True)
    asset_id = fields.Many2one("logilink.asset", string="Asset", required=True, help="Asset being borrowed or assigned")
    community_id = fields.Many2one("logilink.community", string="Community Member", required=True, help="Community member borrowing or receiving the asset")
    borrowed_date = fields.Date("Borrowed Date", default=fields.Date.today, required=True, help="Date when asset was borrowed")
    expected_return_date = fields.Date("Expected Return Date", help="Expected date for asset return")
    actual_return_date = fields.Date("Actual Return Date", help="Actual date when asset was returned")
    status = fields.Selection([
        ("draft", "Draft"),
        ("borrowed", "Borrowed"),
        ("returned", "Returned")
    ], string="Status", default="draft", required=True, help="Current status of the borrowing/assignment")
    notes = fields.Text("Notes", help="Additional notes or remarks")
    active = fields.Boolean(default=True, help="Archive/unarchive record")
    is_overdue = fields.Boolean("Is Overdue", compute="_compute_is_overdue", store=False, help="True if expected return date has passed and status is borrowed")

    @api.depends("asset_id", "borrowed_date")
    def _compute_name(self):
        for rec in self:                                        
            if rec.asset_id and rec.borrowed_date:
                rec.name = f"{rec.asset_id.name} - {rec.borrowed_date}"
            elif rec.asset_id:
                rec.name = rec.asset_id.name
            else:
                rec.name = "New"

    @api.depends("status", "expected_return_date")
    def _compute_is_overdue(self):
        today = fields.Date.today()
        for rec in self:
            rec.is_overdue = (
                rec.status == "borrowed" 
                and rec.expected_return_date 
                and rec.expected_return_date < today
            )

    @api.constrains("expected_return_date", "borrowed_date")
    def _check_return_dates(self):
        for rec in self:
            if rec.expected_return_date and rec.borrowed_date:
                if rec.expected_return_date < rec.borrowed_date:
                    raise ValueError("Expected return date cannot be earlier than borrowed date.")
            if rec.actual_return_date and rec.borrowed_date:
                if rec.actual_return_date < rec.borrowed_date:
                    raise ValueError("Actual return date cannot be earlier than borrowed date.")

    def action_view_list_export(self):
        """Open list view for exporting data"""
        return {
            'name': 'Asset Borrowing - Export',
            'type': 'ir.actions.act_window',
            'res_model': 'logilink.asset.borrowing',
            'view_mode': 'list',
            'view_id': False,
            'target': 'current',
            'context': self.env.context,
        }
