# -*- coding: utf-8 -*-
from odoo import api, fields, models

class LogilinkGoodsReceiptHeader(models.Model):
    _name = "logilink.goods.receipt.header"
    _description = "Goods Receipt Note (GRN) Header"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "date_received desc, grn_number desc"
    _rec_name = "grn_number"

    grn_number = fields.Char("GRN Number", required=True, help="Goods Receipt Note Number")
    po_id = fields.Many2one("logilink.purchase.order.header", string="Purchase Order", required=True, help="Related Purchase Order")
    date_received = fields.Date("Date Received", default=fields.Date.today, required=True, help="Date when goods were received")
    received_by = fields.Many2one("res.users", string="Received By", default=lambda self: self.env.user, required=True, help="Person who received the goods")
    status = fields.Selection([
        ("pending", "Pending"),
        ("completed", "Completed")
    ], string="Status", default="pending", required=True, help="Current status of the goods receipt")
    active = fields.Boolean(default=True, help="Archive/unarchive record")
    
    # Related fields
    line_ids = fields.One2many("logilink.goods.receipt.line", "grn_id", string="GRN Lines", help="Items received in this GRN")

    _sql_constraints = [
        ("grn_number_unique", "unique(grn_number)", "GRN Number must be unique."),
    ]


class LogilinkGoodsReceiptLine(models.Model):
    _name = "logilink.goods.receipt.line"
    _description = "Goods Receipt Note Line"
    _order = "grn_id, id"

    grn_id = fields.Many2one("logilink.goods.receipt.header", string="GRN", required=True, ondelete="cascade", help="Goods Receipt Note this line belongs to")
    po_line_id = fields.Many2one("logilink.purchase.order.line", string="PO Line", required=True, help="Related Purchase Order Line")
    quantity_received = fields.Float("Quantity Received", required=True, default=0.0, help="Quantity of items received")
    quantity_accepted = fields.Float("Quantity Accepted", required=True, default=0.0, help="Quantity of items accepted")
    condition = fields.Selection([
        ("good", "Good"),
        ("damaged", "Damaged"),
        ("defective", "Defective")
    ], string="Condition", default="good", help="Condition of received items")
    remarks = fields.Text("Remarks", help="Additional remarks about the received items")
