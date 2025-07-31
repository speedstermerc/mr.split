from flask import Blueprint, render_template
from app import client

balances_bp = Blueprint('balances', __name__, url_prefix='/balances')

@balances_bp.route("/", methods=["GET"])
def show_balance_summary():
    responsibility_mappings = list(client.ontology.objects.ResponsibilityMapping.iterate())

    users = list(client.ontology.objects.Users.iterate())
    user_id_to_name = {user.user_id: user.full_name for user in users if user.user_id and user.full_name}

    purchased_items = list(client.ontology.objects.PurchasedItem.iterate())
    line_id_to_item = {item.line_id: item for item in purchased_items if item.line_id}

    mappings_expanded = []

    for mapping in responsibility_mappings:
        item = line_id_to_item.get(mapping.line_id)
        if not item:
            continue

        user_name = user_id_to_name.get(mapping.user_id, f"User ID {mapping.user_id}")
        paid_by_name = user_id_to_name.get(item.paid_by, f"User ID {item.paid_by}")

        mappings_expanded.append({
            "line_id": mapping.line_id,
            "receipt_id": item.receipt_id,
            "item_name": item.item_name,
            "price": item.price,
            "user_name": user_name,
            "status": mapping.status,
            "paid_by": paid_by_name
        })

    mappings_expanded.sort(key=lambda x: x["line_id"])

    return render_template("balances.html", mappings=mappings_expanded)
