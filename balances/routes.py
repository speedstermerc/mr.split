from flask import Blueprint, render_template, redirect, url_for, request
from app import client
from foundry_sdk_runtime.types import BatchActionConfig, ReturnEditsMode
from mr_split_sdk.ontology.action_types import DeleteResponsibilityMappingBatchRequest
from balances.utils import compute_balances

balances_bp = Blueprint('balances', __name__, url_prefix='/balances')

@balances_bp.route("/", methods=["GET"])
def show_balance_summary():
    responsibility_mappings = list(client.ontology.objects.ResponsibilityMapping.iterate())
    users = list(client.ontology.objects.Users.iterate())
    user_id_to_name = {u.user_id: u.full_name for u in users if u.user_id and u.full_name}

    purchased_items = list(client.ontology.objects.PurchasedItem.iterate())
    line_id_to_item = {item.line_id: item for item in purchased_items if item.line_id}

    # Expand rows for the existing table
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

    # --- NEW: compute balances ---
    pairwise, per_user = compute_balances(responsibility_mappings, purchased_items)

    # Convert IDs to names and cents to dollars for display
    def fmt_cents(c): return f"${c/100:.2f}"

    pairwise_display = [{
        "from": user_id_to_name.get(frm, f"User ID {frm}"),
        "to":   user_id_to_name.get(to,  f"User ID {to}"),
        "amount": fmt_cents(amt),
    } for (frm, to, amt) in pairwise]

    per_user_display = [{
        "user":  user_id_to_name.get(uid, f"User ID {uid}"),
        "net":   fmt_cents(cents),
        "status": "is owed" if cents > 0 else ("owes" if cents < 0 else "settled")
    } for uid, cents in sorted(per_user.items(), key=lambda kv: user_id_to_name.get(kv[0], str(kv[0])) or "")]

    error = request.args.get("error")

    return render_template(
        "balances.html",
        mappings=mappings_expanded,
        pairwise=pairwise_display,
        per_user=per_user_display,
        error=error
    )


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