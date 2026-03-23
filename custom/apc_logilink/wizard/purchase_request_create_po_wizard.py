# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class LogilinkPurchaseRequestCreatePoWizard(models.TransientModel):
    _name = "logilink.purchase.request.create.po.wizard"
    _description = "Create Purchase Order from Purchase Request (Multiple POs)"

    pr_id = fields.Many2one(
        "logilink.purchase.request.header",
        string="Purchase Request",
        required=True,
        readonly=True,
    )
    supplier_id = fields.Many2one(
        "res.partner",
        string="Supplier",
        required=True,
        help="Vendor to create the Purchase Order for.",
    )
    po_number = fields.Char(
        string="PO Number",
        help="Optional custom PO number. Leave blank to auto-generate.",
    )
    line_ids = fields.One2many(
        "logilink.purchase.request.create.po.wizard.line",
        "wizard_id",
        string="Lines to Order",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        pr_id = self.env.context.get("default_pr_id") or self.env.context.get("active_id")
        if pr_id and "pr_id" in fields_list:
            res["pr_id"] = pr_id
        if pr_id and "po_number" in fields_list:
            pr = self.env["logilink.purchase.request.header"].browse(pr_id)
            po_number_base = f"PO-{pr.pr_number}" if pr.pr_number else f"PO-{fields.Date.today().strftime('%Y%m%d')}-{pr.id}"
            po_number = po_number_base
            counter = 1
            while self.env["logilink.purchase.order.header"].search([("po_number", "=", po_number)], limit=1):
                po_number = f"{po_number_base}-{counter}"
                counter += 1
            res["po_number"] = po_number
        if pr_id and "line_ids" in fields_list:
            pr = self.env["logilink.purchase.request.header"].browse(pr_id)
            lines_cmds = []
            for line in pr.line_ids:
                default_qty = line.remaining_qty if (line.remaining_qty or 0.0) > 0 else (line.quantity_requested or 0.0)
                lines_cmds.append(
                    (
                        0,
                        0,
                        {
                            "pr_line_id": line.id,
                            "item_description": line.item_description,
                            "qty_remaining": line.remaining_qty,
                            "qty_to_order": default_qty,
                            "unit_price": line.estimated_unit_cost or 0.0,
                        },
                    )
                )
            res["line_ids"] = lines_cmds
        return res

    def action_confirm(self):
        self.ensure_one()
        valid_lines = self.line_ids.filtered(lambda l: l.pr_line_id)

        pr = self.pr_id

        po_number = (self.po_number or "").strip()
        if not po_number:
            po_number_base = f"PO-{pr.pr_number}" if pr.pr_number else f"PO-{fields.Date.today().strftime('%Y%m%d')}-{pr.id}"
            po_number = po_number_base
            counter = 1
            while self.env["logilink.purchase.order.header"].search([("po_number", "=", po_number)], limit=1):
                po_number = f"{po_number_base}-{counter}"
                counter += 1
        elif self.env["logilink.purchase.order.header"].search([("po_number", "=", po_number)], limit=1):
            raise UserError(_("PO Number '%s' already exists. Please choose a different one.") % po_number)

        po = self.env["logilink.purchase.order.header"].create(
            {
                "po_number": po_number,
                "pr_id": pr.id,
                "supplier_id": self.supplier_id.id,
                "po_date": fields.Date.today(),
                "status": "requested",
                "currency_id": pr.currency_id.id,
                "active": True,
            }
        )

        created_any = False
        for wline in valid_lines:
            qty = wline.qty_to_order or 0.0
            if qty <= 0:
                continue

            pr_line = wline.pr_line_id

            self.env["logilink.purchase.order.line"].create(
                {
                    "po_id": po.id,
                    "pr_line_id": pr_line.id,
                    "item_description": wline.item_description or pr_line.item_description,
                    "quantity_ordered": qty,
                    "unit_price": wline.unit_price or (pr_line.estimated_unit_cost or 0.0),
                }
            )
            created_any = True

        # Allow creating a PO header even when no positive-qty lines are selected.
        # This supports cases where users need a fresh PO record first.

        return {
            "type": "ir.actions.act_window",
            "res_model": "logilink.purchase.order.header",
            "view_mode": "form",
            "res_id": po.id,
            "target": "current",
        }


class LogilinkPurchaseRequestCreatePoWizardLine(models.TransientModel):
    _name = "logilink.purchase.request.create.po.wizard.line"
    _description = "Create PO Wizard Line"

    wizard_id = fields.Many2one(
        "logilink.purchase.request.create.po.wizard",
        required=True,
        ondelete="cascade",
    )
    pr_line_id = fields.Many2one(
        "logilink.purchase.request.line",
        string="Request Line",
        required=False,
        readonly=True,
    )
    item_description = fields.Text(string="Item Description", readonly=True)
    qty_remaining = fields.Float(string="Remaining Qty", readonly=True)
    qty_to_order = fields.Float(string="Qty to Order", required=True)
    unit_price = fields.Monetary(string="Unit Price", currency_field="currency_id", required=True)
    currency_id = fields.Many2one("res.currency", related="wizard_id.pr_id.currency_id", readonly=True)

    @api.onchange("qty_to_order")
    def _onchange_qty_to_order(self):
        for rec in self:
            if rec.qty_to_order and rec.qty_to_order < 0:
                rec.qty_to_order = 0

