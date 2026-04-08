# -*- coding: utf-8 -*-
from odoo import models


class MailComposeMessage(models.TransientModel):
    _inherit = "mail.compose.message"

    def action_send_mail(self):
        send_targets = []
        for wizard in self:
            send_targets.append(
                {
                    "model": wizard.model,
                    "res_ids": wizard._evaluate_res_ids(),
                }
            )

        result = super().action_send_mail()

        for target in send_targets:
            if target["model"] != "logilink.purchase.order.header" or not target["res_ids"]:
                continue

            orders = self.env[target["model"]].browse(target["res_ids"])
            if self.env.context.get("mark_po_sent_supplier_after_send"):
                orders._mark_sent_supplier_after_email()
            if self.env.context.get("mark_po_submitted_email_after_send"):
                orders._mark_submitted_email_after_send()

        return result
