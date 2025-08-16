from flask import Blueprint, render_template, request, jsonify
from app import client
from .utils import new_mapping_id
from foundry_sdk_runtime.types import BatchActionConfig, ReturnEditsMode
from mr_split_sdk.ontology.action_types import CreateResponsibilityMappingBatchRequest, DeleteResponsibilityMappingBatchRequest
from typing import Iterator
from mr_split_sdk.ontology.objects import ResponsibilityMapping

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

@annotate_bp.route("/save-responsibility", methods=["POST"])
def save_responsibility():
    def _to_int(x):
        try:
            if isinstance(x, int): return x
            if isinstance(x, float): return int(x)
            return int(str(x).strip())
        except Exception:
            return None

    data = request.get_json()
    line_id = _to_int(data.get("line_id"))
    user_names = data.get("user_names")  # List[str]

    if not line_id or not user_names:
        return jsonify({"status": "error", "message": "line_id and user_names are required"}), 400

    # Map names -> IDs
    users = list(client.ontology.objects.Users.iterate())
    name_to_id = {u.full_name: u.user_id for u in users if u.full_name is not None}

    user_ids = [_to_int(name_to_id.get(name)) for name in user_names if name in name_to_id]
    user_ids = [uid for uid in user_ids if uid is not None]
    if not user_ids:
        return jsonify({"status": "error", "message": "No valid user IDs found for given names"}), 400

    # Load the purchased item to find the payer
    # (You can also use .where(...) if you prefer)
    item = next(
        (it for it in client.ontology.objects.PurchasedItem.iterate() if _to_int(it.line_id) == line_id),
        None
    )
    paid_by = _to_int(getattr(item, "paid_by", None)) if item else None

    # Delete existing mappings for this line
    existing = list(
        client.ontology.objects.ResponsibilityMapping.where(
            ResponsibilityMapping.object_type.line_id == line_id
        ).iterate()
    )
    delete_requests = []
    for rm in existing:
        if getattr(rm, "mapping_id", None) is not None:
            delete_requests.append(
                DeleteResponsibilityMappingBatchRequest(
                    responsibility_mapping=rm.mapping_id
                )
            )
    if delete_requests:
        client.ontology.batch_actions.delete_responsibility_mapping(
            batch_action_config=BatchActionConfig(return_edits=ReturnEditsMode.ALL),
            requests=delete_requests
        )

    # Create new mappings; mark as "paid" if user == payer
    batch_requests = []
    base_id = new_mapping_id()
    for idx, uid in enumerate(user_ids):
        status_val = "paid" if (paid_by is not None and uid == paid_by) else "unpaid"
        batch_requests.append(
            CreateResponsibilityMappingBatchRequest(
                mapping_id=base_id + idx,
                line_id=line_id,
                user_id=uid,
                status=status_val
            )
        )

    client.ontology.batch_actions.create_responsibility_mapping(
        batch_action_config=BatchActionConfig(return_edits=ReturnEditsMode.ALL),
        requests=batch_requests
    )

    return jsonify({"status": "success"})
