from mr_split_sdk.ontology.objects import PurchasedItem
from app import client

def new_line_id() -> int:
    """
    Returns the next available line_id (int) by checking the current max.
    """
    highest_item = next(
        client.ontology.objects.PurchasedItem
        .where(~PurchasedItem.object_type.item_name.is_null())
        .order_by(PurchasedItem.object_type.line_id.desc())
        .iterate(),
        None
    )

    if highest_item is None or highest_item.line_id is None:
        return 1

    return highest_item.line_id + 1
