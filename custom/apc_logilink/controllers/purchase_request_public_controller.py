# -*- coding: utf-8 -*-
import logging
from itertools import zip_longest
from urllib.parse import quote

from odoo import _, http
from odoo.http import request

_logger = logging.getLogger(__name__)


class PublicPurchaseRequestController(http.Controller):

    def _get_communities(self):
        return request.env["logilink.community"].sudo().search([("active", "=", True)], order="name")

    def _get_departments(self):
        return request.env["logilink.department"].sudo().search([], order="name")

    def _get_item_type_options(self):
        return list(request.env["logilink.purchase.request.line"]._fields["item_type"].selection)

    def _get_default_lines(self):
        return [{"item_description": "", "quantity_requested": "1", "item_type": "consumable"}]

    def _build_form_context(self, values=None, errors=None):
        values = dict(values or {})
        if not values.get("lines"):
            values["lines"] = self._get_default_lines()
        return {
            "communities": self._get_communities(),
            "departments": self._get_departments(),
            "item_type_options": self._get_item_type_options(),
            "values": values,
            "errors": errors or [],
        }

    @http.route("/purchase/request", type="http", auth="public", website=True)
    def purchase_request_form(self, **kwargs):
        return request.render(
            "apc_logilink.purchase_request_public_form",
            self._build_form_context(),
        )

    @http.route("/purchase/request/submit", type="http", auth="public", methods=["POST"], website=True)
    def purchase_request_submit(self, **post):
        form = request.httprequest.form
        values = {
            "community_id": (post.get("community_id") or "").strip(),
            "approver_id": (post.get("approver_id") or "").strip(),
            "requested_by": "",
            "requester_id_number": "",
            "department_id": (post.get("department_id") or "").strip(),
            "purpose": (post.get("purpose") or "").strip(),
            "lines": [],
        }
        errors = []
        cleaned_lines = []
        valid_item_types = {value for value, _label in self._get_item_type_options()}

        if not values["purpose"]:
            errors.append(_("Purpose is required."))

        community = request.env["logilink.community"]
        if values["community_id"]:
            try:
                community = request.env["logilink.community"].sudo().browse(int(values["community_id"]))
            except (TypeError, ValueError):
                community = request.env["logilink.community"]
        if not getattr(community, "id", False) or not community.exists():
            errors.append(_("Please select a valid requester."))
        else:
            values["requested_by"] = (community.name or "").strip()
            values["requester_id_number"] = (community.id_number or "").strip()

        approver = request.env["logilink.community"]
        if values["approver_id"]:
            try:
                approver = request.env["logilink.community"].sudo().browse(int(values["approver_id"]))
            except (TypeError, ValueError):
                approver = request.env["logilink.community"]
            if not getattr(approver, "id", False) or not approver.exists():
                errors.append(_("Please select a valid approver."))

        department = request.env["logilink.department"]
        if values["department_id"]:
            try:
                department = request.env["logilink.department"].sudo().browse(int(values["department_id"]))
            except (TypeError, ValueError):
                department = request.env["logilink.department"]
        if not getattr(department, "id", False) or not department.exists():
            errors.append(_("Please select a valid department."))

        item_descriptions = form.getlist("item_description[]")
        quantities = form.getlist("quantity_requested[]")
        item_types = form.getlist("item_type[]")

        for index, (description_raw, quantity_raw, item_type_raw) in enumerate(
            zip_longest(item_descriptions, quantities, item_types, fillvalue=""),
            start=1,
        ):
            description = (description_raw or "").strip()
            quantity_text = (quantity_raw or "").strip()
            item_type = (item_type_raw or "consumable").strip()

            values["lines"].append(
                {
                    "item_description": description,
                    "quantity_requested": quantity_text or "1",
                    "item_type": item_type or "consumable",
                }
            )

            # Ignore the untouched default row so users can leave the last blank item in place.
            if not description and quantity_text in ("", "1") and item_type in ("", "consumable"):
                continue

            if not description:
                errors.append(_("Line %(line)s: Item Description is required.") % {"line": index})
                continue

            try:
                quantity = float(quantity_text)
            except (TypeError, ValueError):
                errors.append(_("Line %(line)s: Quantity must be a valid number.") % {"line": index})
                continue

            if quantity <= 0:
                errors.append(_("Line %(line)s: Quantity must be greater than zero.") % {"line": index})
                continue

            if item_type not in valid_item_types:
                errors.append(_("Line %(line)s: Item Type is invalid.") % {"line": index})
                continue

            cleaned_lines.append(
                {
                    "item_description": description,
                    "quantity_requested": quantity,
                    "item_type": item_type,
                }
            )

        if errors:
            return request.render(
                "apc_logilink.purchase_request_public_form",
                self._build_form_context(values=values, errors=errors),
            )

        try:
            public_user = request.env.ref("base.public_user").sudo()
            pr_record = request.env["logilink.purchase.request.header"].sudo().create(
                {
                    "department_id": department.id,
                    "requested_by": public_user.id,
                    "requested_by_community_id": community.id,
                    "approver_id": approver.id if getattr(approver, "id", False) and approver.exists() else False,
                    "purpose": values["purpose"],
                    "status": "requested",
                }
            )

            line_model = request.env["logilink.purchase.request.line"].sudo()
            for line in cleaned_lines:
                line_model.create(
                    {
                        "pr_id": pr_record.id,
                        "item_description": line["item_description"],
                        "quantity_requested": line["quantity_requested"],
                        "item_type": line["item_type"],
                    }
                )

            return request.redirect(
                "/purchase/request/thank-you?pr_number=%s" % quote(pr_record.pr_number or "")
            )
        except Exception:
            _logger.exception("Failed to submit public purchase request")
            errors.append(
                _("We could not submit your purchase request right now. Please try again.")
            )
            return request.render(
                "apc_logilink.purchase_request_public_form",
                self._build_form_context(values=values, errors=errors),
            )

    @http.route("/purchase/request/thank-you", type="http", auth="public", website=True)
    def purchase_request_thank_you(self, **kwargs):
        return request.render(
            "apc_logilink.purchase_request_public_thank_you",
            {"pr_number": (kwargs.get("pr_number") or "").strip()},
        )
