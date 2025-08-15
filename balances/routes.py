from flask import Blueprint, render_template, redirect, url_for, request
from app import client
from foundry_sdk_runtime.types import BatchActionConfig, ReturnEditsMode
from mr_split_sdk.ontology.action_types import DeleteResponsibilityMappingBatchRequest

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


@balances_bp.route("/delete_all", methods=["POST"])
def delete_all_mappings():
    # Server-side safety: require exact "DELETE" confirmation
    confirm_text = request.form.get("confirm_text", "")
    if confirm_text != "DELETE":
        return redirect(url_for("balances.show_balance_summary",
                                error="Deletion cancelled. You must type DELETE to confirm."))

    responsibility_mappings = list(client.ontology.objects.ResponsibilityMapping.iterate())

    if responsibility_mappings:
        requests = [
            DeleteResponsibilityMappingBatchRequest(
                responsibility_mapping=mapping.mapping_id  # primary key field
            )
            for mapping in responsibility_mappings
        ]
        if len(requests) > 0:
            client.ontology.batch_actions.delete_responsibility_mapping(
                batch_action_config=BatchActionConfig(return_edits=ReturnEditsMode.ALL),
                requests=requests
            )

    return redirect(url_for("balances.show_balance_summary"))