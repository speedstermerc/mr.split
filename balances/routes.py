from flask import Blueprint, render_template
from app import client
from collections import defaultdict

balances_bp = Blueprint('balances', __name__, url_prefix='/balances')

@balances_bp.route("/", methods=["GET"])
def show_balance_summary():
    responsibility_mappings = list(client.ontology.objects.ResponsibilityMapping.iterate())

    users = list(client.ontology.objects.Users.iterate())
    user_id_to_name = {user.user_id: user.full_name for user in users if user.user_id and user.full_name}

    purchased_items = list(client.ontology.objects.PurchasedItem.iterate())
    line_id_to_item = {item.line_id: item for item in purchased_items if item.line_id}

    grouped = defaultdict(lambda: {
        "line_id": None,
        "receipt_id": None,
        "item_name": None,
        "price": None,
        "user_names": set(),
        "status": None,
        "paid_by": None  # Added paid_by here
    })

    for mapping in responsibility_mappings:
        item = line_id_to_item.get(mapping.line_id, None)
        if not item:
            continue

        group = grouped[mapping.line_id]
        group["line_id"] = mapping.line_id
        group["receipt_id"] = item.receipt_id
        group["item_name"] = item.item_name
        group["price"] = item.price
        group["status"] = mapping.status  # Assumes same status for all user mappings on the same line
        group["paid_by"] = user_id_to_name.get(item.paid_by, f"User ID {item.paid_by}")  # Map paid_by user id to name
        user_name = user_id_to_name.get(mapping.user_id, f"User ID {mapping.user_id}")
        group["user_names"].add(user_name)

    # Convert user_names from set to sorted list or comma-separated string
    for group in grouped.values():
        group["user_names"] = ", ".join(sorted(group["user_names"]))

    mappings_expanded = list(grouped.values())

    return render_template("balances.html", mappings=mappings_expanded)
