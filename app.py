import os
from flask import Flask, render_template
from mr_split_sdk import FoundryClient, UserTokenAuth


# Initialize Foundry client once
auth = UserTokenAuth(token=os.environ["FOUNDRY_TOKEN"])
client = FoundryClient(auth=auth, hostname="https://roshan-built-this.usw-18.palantirfoundry.com")


def create_app():
    app = Flask(__name__)
    app.secret_key = "asdf"  # Use a strong secret in production

    # Register blueprints
    from users.routes import users_bp
    app.register_blueprint(users_bp)

    from annotate.routes import annotate_bp
    app.register_blueprint(annotate_bp)

    from balances.routes import balances_bp
    app.register_blueprint(balances_bp)

    from home.routes import home_bp
    app.register_blueprint(home_bp)

    return app





if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
