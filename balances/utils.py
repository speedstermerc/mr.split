from mr_split_sdk.ontology.objects import Users
from app import client

def new_user_id() -> int:
    # Query for the user with the highest user_id
    highest_user = next(
        client.ontology.objects.Users
        .where(~Users.object_type.full_name.is_null())
        .order_by(Users.object_type.user_id.desc())
        .iterate(),
        None  # default if none found
    )

    if highest_user is None or highest_user.user_id is None:
        return 1  # no users, start at 1

    return highest_user.user_id + 1