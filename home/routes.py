from flask import Blueprint, render_template
from app import client


home_bp = Blueprint('home', __name__, url_prefix='')

@home_bp.route("/")
def home():
    return render_template("home.html")