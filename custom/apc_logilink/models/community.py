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
    partner_id = fields.Many2one(
        "res.partner",
        string="Contact (res.partner)",
        readonly=True,
        help="Automatically linked contact record used for emails/recipients.",
    )
    active = fields.Boolean(default=True, help="Archive/unarchive community member")

    _sql_constraints = [
        ("id_number_unique", "unique(id_number)", "ID Number must be unique."),
    ]

    def _get_apc_company_partner(self):
        """Return the company partner under which Community contacts should be nested."""
        # Prefer a real company partner named Asia Pacific College (common in demo/real DBs).
        apc_partner = self.env["res.partner"].sudo().search(
            [("is_company", "=", True), ("name", "ilike", "Asia Pacific College")],
            limit=1,
        )
        # Fallback: current company partner.
        return apc_partner or self.env.company.partner_id

    def _ensure_partner_link(self):
        """Ensure each community member has a linked res.partner contact under APC."""
        Partner = self.env["res.partner"].sudo()
        apc_company_partner = self._get_apc_company_partner()

        for rec in self:
            email = (rec.email or "").strip()
            if not email:
                continue

            partner = rec.partner_id
            # Community members must map to a person contact, not to a company record.
            # If current link points to company (or APC company itself), re-resolve below.
            if partner and (partner.is_company or (apc_company_partner and partner.id == apc_company_partner.id)):
                partner = False
            if not partner:
                # Prefer an existing person contact with the same email.
                partner = Partner.search([("email", "=", email), ("is_company", "=", False)], limit=1)

            if not partner:
                partner = Partner.create(
                    {
                        "name": rec.name or email,
                        "email": email,
                        "phone": rec.phone or False,
                        "company_type": "person",
                        "parent_id": apc_company_partner.id if apc_company_partner else False,
                    }
                )
            else:
                # Keep contact info in sync (best-effort).
                vals = {}
                if rec.name and partner.name != rec.name:
                    vals["name"] = rec.name
                if rec.phone and partner.phone != rec.phone:
                    vals["phone"] = rec.phone
                # Ensure it's grouped under APC.
                if (
                    apc_company_partner
                    and partner.id != apc_company_partner.id
                    and partner.parent_id != apc_company_partner
                ):
                    vals["parent_id"] = apc_company_partner.id
                if vals:
                    partner.write(vals)

            if rec.partner_id != partner:
                rec.partner_id = partner.id

    def action_resync_partner(self):
        """Manual button: re-sync/create the linked res.partner contact for this community member."""
        self._ensure_partner_link()
        return True

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._ensure_partner_link()
        return records

    def write(self, vals):
        res = super().write(vals)
        # Re-link if key identity/contact fields changed, or if partner_id is missing.
        if any(k in vals for k in ("name", "email", "phone")) or any(not r.partner_id for r in self):
            self._ensure_partner_link()
        return res

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
