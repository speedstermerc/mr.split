from mr_split_sdk.ontology.objects import ResponsibilityMapping
from app import client

def new_mapping_id() -> int:
    # Query for the user with the highest user_id
    highest_mapping = next(
        client.ontology.objects.ResponsibilityMapping
        .order_by(ResponsibilityMapping.object_type.mapping_id.desc())
        .iterate(),
        None  # default if none found
    )

    if highest_mapping is None or highest_mapping.mapping_id is None:
        return 1  # no users, start at 1

    return highest_mapping.mapping_id + 1