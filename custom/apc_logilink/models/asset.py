# -*- coding: utf-8 -*-
from odoo import api, fields, models

class LogilinkAsset(models.Model):
    _name = "logilink.asset"
    _description = "Asset Registry"
    _order = "name"

    name = fields.Char("Name", required=True, help="Asset name or title")
    description = fields.Text("Description", help="Detailed description of the asset")
    asset_code = fields.Char("Asset Code", help="Unique asset identification code")
    display_name = fields.Char("Display Name", compute="_compute_display_name", store=True, index=True)
    model_no = fields.Char("Model No.", help="Model number of the asset")
    serial_no = fields.Char("Serial No.", help="Serial number of the asset")
    received_by_id = fields.Many2one("res.users", string="Received By", help="Person who received the asset")
    department_id = fields.Many2one("logilink.department", string="Department", help="Department associated with this asset")
    date = fields.Date("Date", default=fields.Date.today, help="Date of asset registration or receipt")
    purchase_order_no = fields.Char("Purchase Order No.", help="Purchase order number associated with the asset")
    supplier_id = fields.Many2one("res.partner", string="Supplier", help="Supplier or vendor of the asset")
    warranty_expiration = fields.Date("Warranty Expiration", help="Warranty expiration date")
    price = fields.Monetary("Price", currency_field="currency_id", help="Purchase price of the asset")
    currency_id = fields.Many2one("res.currency", string="Currency", default=lambda self: self.env.company.currency_id)
    active = fields.Boolean(default=True, help="Archive/unarchive asset")
    
    # Transaction History Fields
    borrowing_ids = fields.One2many("logilink.asset.borrowing", "asset_id", string="Transaction History", help="All borrowing/assignment records for this asset")
    transaction_count = fields.Integer("Transaction Count", compute="_compute_transaction_count", store=False, help="Total number of borrowing/assignment transactions")

    _sql_constraints = [
        ("asset_code_unique", "unique(asset_code)", "Asset code must be unique."),
    ]

    @api.depends('name', 'asset_code')
    def _compute_display_name(self):
        """Compute display name with asset code"""
        for rec in self:
            name = rec.name or ''
            if rec.asset_code:
                rec.display_name = f"{name} [{rec.asset_code}]"
            else:
                rec.display_name = name

    def name_get(self):
        """Override to display Name and Asset Code together"""
        result = []
        for rec in self:
            result.append((rec.id, rec.display_name))
        return result

    @api.model
    def _name_search(self, name='', domain=None, operator='ilike', limit=100, order=None):
        """Enable searching by both name and asset_code"""
        domain = domain or []
        if name:
            domain = ['|', ('name', operator, name), ('asset_code', operator, name)] + domain
        return self._search(domain, limit=limit, order=order or self._order)

    @api.depends("borrowing_ids")
    def _compute_transaction_count(self):
        """Compute the total number of transactions for this asset"""
        for rec in self:
            rec.transaction_count = len(rec.borrowing_ids)

    def action_view_transactions(self):
        """Open filtered view of transactions for this asset"""
        self.ensure_one()
        return {
            'name': f'Transaction History - {self.display_name}',
            'type': 'ir.actions.act_window',
            'res_model': 'logilink.asset.borrowing',
            'view_mode': 'list,form,kanban',
            'domain': [('asset_id', '=', self.id)],
            'context': {'default_asset_id': self.id, 'search_default_asset_id': self.id},
        }

    @api.constrains("price")
    def _check_price(self):
        for rec in self:
            if rec.price < 0:
                raise ValueError("Price cannot be negative.")
