from flask import Flask, redirect, url_for
import os
from database import engine, Base
from init_db import seed_admin
from blueprints.auth_bp     import auth_bp
from blueprints.projects_bp import projects_bp
from blueprints.datasets_bp import datasets_bp
from blueprints.metrics_bp  import metrics_bp
from blueprints.admin_bp    import admin_bp

Base.metadata.create_all(bind=engine)
seed_admin()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "metrics_flask_secret_2024")

app.register_blueprint(auth_bp)
app.register_blueprint(projects_bp)
app.register_blueprint(datasets_bp)
app.register_blueprint(metrics_bp)
app.register_blueprint(admin_bp)


@app.route("/")
def root():
    return redirect(url_for("projects.index"))


if __name__ == "__main__":
    app.run(debug=True)
