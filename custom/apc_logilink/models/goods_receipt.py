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

    @api.onchange("po_id")
    def _onchange_po_id_populate_lines(self):
        """When a Purchase Order is selected, auto-add GRN lines for all PO lines."""
        for rec in self:
            if not rec.po_id:
                rec.line_ids = [(5, 0, 0)]
                continue

            new_lines = []
            for po_line in rec.po_id.line_ids:
                new_lines.append(
                    (
                        0,
                        0,
                        {
                            "po_line_id": po_line.id,
                            # Default ordered/delivered equal to ordered; user can adjust delivered as needed.
                            "quantity_received": po_line.quantity_ordered,
                            "quantity_delivered": po_line.quantity_ordered,
                        },
                    )
                )
            # Replace current GRN lines with lines from the selected PO.
            rec.line_ids = [(5, 0, 0)] + new_lines

    def action_view_list_export(self):
        """Open list view for exporting data"""
        return {
            'name': 'GRNs - Export',
            'type': 'ir.actions.act_window',
            'res_model': 'logilink.goods.receipt.header',
            'view_mode': 'list',
            'view_id': False,
            'target': 'current',
            'context': self.env.context,
        }

    def action_print_grn(self):
        """Print GRN as PDF."""
        self.ensure_one()
        report = self.env.ref("apc_logilink.action_report_goods_receipt")
        return report.report_action(self)


class LogilinkGoodsReceiptLine(models.Model):
    _name = "logilink.goods.receipt.line"
    _description = "Goods Receipt Note Line"
    _order = "grn_id, id"

    grn_id = fields.Many2one("logilink.goods.receipt.header", string="GRN", required=True, ondelete="cascade", help="Goods Receipt Note this line belongs to")
    po_line_id = fields.Many2one("logilink.purchase.order.line", string="PO Line", required=True, help="Related Purchase Order Line")
    # quantity_received now represents the ordered quantity for reference.
    quantity_received = fields.Float("Quantity Ordered", required=True, default=0.0, help="Quantity of items ordered on the Purchase Order")
    # New field: what was actually delivered.
    quantity_delivered = fields.Float("Quantity Delivered", required=True, default=0.0, help="Quantity of items actually delivered")
    # Legacy field kept for compatibility but no longer shown in the UI.
    quantity_accepted = fields.Float("Quantity Accepted", required=True, default=0.0, help="(Legacy) Quantity of items accepted")
    po_line_summary = fields.Char(
        string="PO Line",
        compute="_compute_po_line_summary",
        help="Human-readable summary of the related PO line.",
    )

    @api.depends(
        "po_line_id.item_description",
        "po_line_id.quantity_ordered",
        "po_line_id.unit_price",
        "po_line_id.line_total",
        "po_line_id.currency_id",
    )
    def _compute_po_line_summary(self):
        for rec in self:
            po_line = rec.po_line_id
            if not po_line:
                rec.po_line_summary = False
                continue
            desc = (po_line.item_description or "").strip() or "(No Description)"
            sym = po_line.currency_id.symbol if po_line.currency_id and po_line.currency_id.symbol else ""
            qty = po_line.quantity_ordered or 0.0
            unit = po_line.unit_price or 0.0
            total = po_line.line_total or (qty * unit)
            rec.po_line_summary = "%s | Qty: %.2f | Unit: %s%.2f | Total: %s%.2f" % (
                desc,
                qty,
                sym,
                unit,
                sym,
                total,
            )
    condition = fields.Selection([
        ("good", "Good"),
        ("damaged", "Damaged"),
        ("defective", "Defective")
    ], string="Condition", default="good", help="Condition of received items")
    remarks = fields.Text("Remarks", help="Additional remarks about the received items")
