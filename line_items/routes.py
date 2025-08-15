from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import client
from .utils import new_line_id
from foundry_sdk_runtime.types import (
    ActionConfig,
    ActionMode,
    ReturnEditsMode,
    SyncApplyActionResponse
)

line_items_bp = Blueprint('line_items', __name__, url_prefix='/line-items')

@line_items_bp.route("/", methods=["GET"])
def list_line_items():
    items_iter = client.ontology.objects.PurchasedItem.iterate()
    items = list(items_iter)

    items_dicts = [{
        "line_id": item.line_id,
        "receipt_id": item.receipt_id,
        "store_name": item.store_name,
        "purchase_date": item.purchase_date,
        "item_name": item.item_name,
        "price": item.price,  # price in dollars
        "paid_by": item.paid_by
    } for item in items]

    return render_template("line_items.html", items=items_dicts)

@line_items_bp.route("/add", methods=["POST"])
def add_line_item():
    form_receipt_id = request.form.get("receipt_id")
    form_store_name = request.form.get("store_name")
    form_purchase_date = request.form.get("purchase_date")
    form_item_name = request.form.get("item_name")
    form_price = request.form.get("price")
    form_paid_by = request.form.get("paid_by")

    # Basic validation
    if not all([form_receipt_id, form_store_name, form_purchase_date, form_item_name, form_price, form_paid_by]):
        flash("All fields are required.", "error")
        return redirect(url_for("line_items.list_line_items"))

    try:
        price_float = float(form_price)
    except ValueError:
        flash("Price must be a number (in dollars).", "error")
        return redirect(url_for("line_items.list_line_items"))

    try:
        receipt_id_str = str(form_receipt_id)
        paid_by_int = int(form_paid_by)
    except ValueError:
        flash("Receipt ID and Paid By must be integers.", "error")
        return redirect(url_for("line_items.list_line_items"))

    # Create in ontology
    response: SyncApplyActionResponse = client.ontology.actions.create_purchased_item(
        action_config=ActionConfig(
            mode=ActionMode.VALIDATE_AND_EXECUTE,
            return_edits=ReturnEditsMode.ALL
        ),
        line_id=new_line_id(),
        receipt_id=receipt_id_str,
        store_name=form_store_name,
        purchase_date=form_purchase_date,  # must be in Foundry's expected date format
        item_name=form_item_name,
        price=price_float,  # dollars
        paid_by=paid_by_int
    )

    if response.validation.result == "VALID":
        flash(f"Line item '{form_item_name}' added successfully!", "success")
    else:
        flash("Failed to add line item.", "error")

    return redirect(url_for("line_items.list_line_items"))

@line_items_bp.route("/delete", methods=["POST"])
def delete_line_item():
    line_id = request.form.get("delete_line_id")
    if not line_id:
        flash("Line ID is required to delete a line item.", "error")
        return redirect(url_for("line_items.list_line_items"))

    try:
        line_id_int = int(line_id)
    except ValueError:
        flash("Line ID must be an integer.", "error")
        return redirect(url_for("line_items.list_line_items"))

    response: SyncApplyActionResponse = client.ontology.actions.delete_purchased_item(
        action_config=ActionConfig(
            mode=ActionMode.VALIDATE_AND_EXECUTE,
            return_edits=ReturnEditsMode.ALL
        ),
        purchased_item= line_id_int
    )

    if response.validation.result == "VALID":
        flash(f"Line item with ID {line_id} deleted successfully.", "success")
    else:
        flash(f"Failed to delete line item with ID {line_id}.", "error")

    return redirect(url_for("line_items.list_line_items"))


