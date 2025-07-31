from flask import Blueprint, render_template, request
from app import client

annotate_bp = Blueprint('annotate', __name__, url_prefix='/annotate')

@annotate_bp.route("/", methods=["GET"])
def list_items():
    # Get receipt_id from query parameters, default to None meaning show all
    receipt_id = request.args.get("receipt_id")

    # Normalize receipt_id to an empty string if it is None on first website load.
    if receipt_id == None:
        receipt_id = ""
    active_line_id = request.args.get("active_line_id", type=int)

    # Get all distinct receipt IDs for dropdown options
    all_items = list(client.ontology.objects.PurchasedItem.iterate())
    receipt_ids = sorted({item.receipt_id for item in all_items if item.receipt_id})

    # Filter items if receipt_id specified
    if receipt_id:
        filtered_items = [item for item in all_items if item.receipt_id == receipt_id]
    else:
        filtered_items = all_items

    items_dicts = [{
        "line_id": item.line_id,
        "receipt_id": item.receipt_id,
        "store_name": item.store_name,
        "purchase_date": item.purchase_date,
        "item_name": item.item_name,
        "price": item.price,
        "paid_by": item.paid_by
    } for item in filtered_items]

    # If no active_line_id specified, default to first item's line_id if exists
    if not active_line_id and items_dicts:
        active_line_id = items_dicts[0]["line_id"]


    users_iterator = client.ontology.objects.Users.iterate()
    users = list(users_iterator)
    user_names = [user.full_name for user in users if user.full_name]


    return render_template(
        "annotate.html",
        items=items_dicts,
        receipt_ids=receipt_ids,
        selected_receipt=receipt_id,
        active_line_id=active_line_id,
        user_names=user_names
    )