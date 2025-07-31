from flask import Blueprint, render_template, request, redirect, url_for, flash
from app import client
from .utils import *

from foundry_sdk_runtime.types import (
    ActionConfig,
    ActionMode,
    ReturnEditsMode,
    SyncApplyActionResponse
)

users_bp = Blueprint('users', __name__, url_prefix='/users')

@users_bp.route("/", methods=["GET"])
def list_users():
    users_iterator = client.ontology.objects.Users.iterate()
    users = list(users_iterator)
    users_dicts = [{
        "user_id": user.user_id,
        "full_name": user.full_name,
        "email": user.email
    } for user in users]

    return render_template("users.html", users=users_dicts)

@users_bp.route("/add", methods=["POST"])
def add_users():
    form_full_name = request.form.get("full_name")
    form_email = request.form.get("email")

    if not form_full_name or not form_email:
        flash("Full name and email are required.", "error")
    else:
        # Create new user in ontology
        response: SyncApplyActionResponse = client.ontology.actions.create_users(
            action_config=ActionConfig(
                mode=ActionMode.VALIDATE_AND_EXECUTE,
                return_edits=ReturnEditsMode.ALL),
            user_id=new_user_id(),
            full_name=form_full_name,
            email=form_email
        )
        if response.validation.result == "VALID":
            flash(f"User '{form_full_name}' added successfully!", "success")
        else:
            flash(f"Something went wrong :()", "error")
    return redirect(url_for("users.list_users"))



@users_bp.route("/delete", methods=["POST"])
def delete_user():
    user_id = request.form.get("delete_user_id")
    if not user_id:
        flash("User ID is required to delete a user.", "error")
        return redirect(url_for("users.list_users"))

    try:
        user_id_int = int(user_id)
    except ValueError:
        flash("User ID must be an integer.", "error")
        return redirect(url_for("users.list_users"))

    # Call the ontology delete action or delete method (replace with your actual method)
    response: SyncApplyActionResponse = client.ontology.actions.delete_users(
        action_config=ActionConfig(
            mode=ActionMode.VALIDATE_AND_EXECUTE,
            return_edits=ReturnEditsMode.ALL),
        users=user_id_int
    )


    if response.validation.result == "VALID":
        flash(f"User with ID {user_id} deleted successfully.", "success")
    else:
        flash(f"Failed to delete user with ID {user_id}.", "error")

    return redirect(url_for("users.list_users"))

