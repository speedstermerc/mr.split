from flask import Blueprint, render_template
from app import client

users_bp = Blueprint('users', __name__, url_prefix='/users')

@users_bp.route("/")
def get_users():
    users_iterator = client.ontology.objects.Users.iterate()
    users = list(users_iterator)
    users_dicts = []
    for user in users:
        users_dicts.append({
            "user_id": user.user_id,
            "full_name": user.full_name,
            "email": user.email
        })
    return render_template("users.html", users=users_dicts)
