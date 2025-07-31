from flask import Blueprint, render_template, request, jsonify
from app import client
from .utils import new_mapping_id
from foundry_sdk_runtime.types import BatchActionConfig, ReturnEditsMode
from mr_split_sdk.ontology.action_types import CreateResponsibilityMappingBatchRequest

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
    data = request.get_json()

    line_id = data.get("line_id")
    user_names = data.get("user_names")  # List of strings

    # Validate input
    if not line_id or not user_names:
        return jsonify({"status": "error", "message": "line_id and user_names are required"}), 400

    # Map user_names to user IDs
    users_iterator = client.ontology.objects.Users.iterate()
    users = list(users_iterator)
    name_to_id = {user.full_name: user.user_id for user in users if user.full_name}

    user_ids = [name_to_id.get(name) for name in user_names if name in name_to_id]

    if not user_ids:
        return jsonify({"status": "error", "message": "No valid user IDs found for given names"}), 400

    # You need to generate unique mapping_ids for each mapping.
    # For demo purposes, let's generate them based on a simple logic:
    # e.g., max existing mapping_id + incremental index.
    # Fetch all existing mappings to find max mapping_id
    # existing_mappings = list(client.ontology.objects.ResponsibilityMapping.iterate())
    # existing_ids = [mapping.mapping_id for mapping in existing_mappings if mapping.mapping_id is not None]
    # max_mapping_id = max(existing_ids) if existing_ids else 0

    # Prepare batch requests for each user_id
    batch_requests = []
    for idx, user_id in enumerate(user_ids, start=0):
        batch_requests.append(
            CreateResponsibilityMappingBatchRequest(
                mapping_id=new_mapping_id() + idx,
                line_id=line_id,
                user_id=user_id,
                status="unpaid"  # or another default status as per your design
            )
        )

    # Call Foundry batch action to create responsibility mappings
    response = client.ontology.batch_actions.create_responsibility_mapping(
        batch_action_config=BatchActionConfig(return_edits=ReturnEditsMode.ALL),
        requests=batch_requests
    )
    print(response.edits)


    return jsonify({"status": "success"})