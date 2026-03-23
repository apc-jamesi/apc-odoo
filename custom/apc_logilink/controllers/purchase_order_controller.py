# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class PurchaseOrderController(http.Controller):
    @http.route(
        "/purchase_order/<int:po_id>/approve",
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
    )
    def approve_purchase_order(self, po_id, message="", **kwargs):
        """Handle approve action from email button."""
        try:
            po = request.env["logilink.purchase.order.header"].sudo().browse(po_id)
            if not po.exists():
                return request.render("apc_logilink.po_action_error", {"error": "Purchase Order not found"})

            if request.httprequest.method == "POST":
                message = request.params.get("message", "").strip() or kwargs.get("message", "").strip()
                po.action_approve_with_message(message)
                return request.render(
                    "apc_logilink.po_action_success",
                    {"po": po, "action": "approved", "message": message},
                )

            return request.render(
                "apc_logilink.po_action_form",
                {
                    "po": po,
                    "action": "approve",
                    "action_label": "Approve",
                    "action_url": f"/purchase_order/{po_id}/approve",
                    "button_color": "#27ae60",
                    "button_bg": "#e8f5e9",
                },
            )
        except Exception as e:
            _logger.error("Error approving purchase order %s: %s", po_id, str(e))
            return request.render("apc_logilink.po_action_error", {"error": str(e)})

    @http.route(
        "/purchase_order/<int:po_id>/decline",
        type="http",
        auth="public",
        methods=["GET", "POST"],
        csrf=False,
    )
    def decline_purchase_order(self, po_id, message="", **kwargs):
        """Handle decline action from email button."""
        try:
            po = request.env["logilink.purchase.order.header"].sudo().browse(po_id)
            if not po.exists():
                return request.render("apc_logilink.po_action_error", {"error": "Purchase Order not found"})

            if request.httprequest.method == "POST":
                message = request.params.get("message", "").strip() or kwargs.get("message", "").strip()
                po.action_decline_with_message(message)
                return request.render(
                    "apc_logilink.po_action_success",
                    {"po": po, "action": "declined", "message": message},
                )

            return request.render(
                "apc_logilink.po_action_form",
                {
                    "po": po,
                    "action": "decline",
                    "action_label": "Decline",
                    "action_url": f"/purchase_order/{po_id}/decline",
                    "button_color": "#e74c3c",
                    "button_bg": "#ffebee",
                },
            )
        except Exception as e:
            _logger.error("Error declining purchase order %s: %s", po_id, str(e))
            return request.render("apc_logilink.po_action_error", {"error": str(e)})

