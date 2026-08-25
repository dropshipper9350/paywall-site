import os
from datetime import datetime
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, abort, flash, redirect, render_template, request, url_for
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from werkzeug.security import check_password_hash, generate_password_hash

import payments
from models import Article, Order, User, db

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///paywall.db"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["UNLOCK_PRICE_INR"] = int(os.environ.get("UNLOCK_PRICE_INR", 499))
    app.config["ADMIN_EMAIL"] = os.environ.get("ADMIN_EMAIL", "").strip().lower()

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    with app.app_context():
        db.create_all()
        _seed_articles()

    _register_routes(app)
    return app


def _seed_articles():
    if Article.query.count() > 0:
        return
    samples = [
        (
            "Simran",
            "getting-started",
            "A quick orientation before you dive in.",
            "This is placeholder lesson content — replace it with your real "
            "material. Full lessons only render below once a reader has "
            "unlocked access.",
            "/static/images/lesson1.jpg",
        ),
        (
            "Nikita",
            "core-technique",
            "The foundational method the rest of the course builds on.",
            "Placeholder content. Swap in your actual lesson text, images, "
            "or embedded video here.",
            "/static/images/lesson2.jpg", 
        ),
        (
            "Anjali",
            "advanced-playbook",
            "Where things get interesting once the basics click.",
            "Placeholder content. This is where a paying reader would find "
            "your most advanced material.",
            "/static/images/lesson3.jpg", 
        ),
    ]
    for title, slug, excerpt, content, image_url in samples:
        db.session.add(Article(title=title, slug=slug, excerpt=excerpt, content=content, image_url=image_url))
    db.session.commit()


def _register_routes(app):
    @app.context_processor
    def inject_is_admin():
        is_admin = bool(
            app.config["ADMIN_EMAIL"]
            and current_user.is_authenticated
            and current_user.email == app.config["ADMIN_EMAIL"]
        )
        return {"is_admin": is_admin}

    @app.route("/")
    def index():
        articles = Article.query.all()
        return render_template("index.html", articles=articles)

    @app.route("/article/<slug>")
    def article(slug):
        art = Article.query.filter_by(slug=slug).first_or_404()
        unlocked = current_user.is_authenticated and current_user.has_access
        return render_template("article.html", article=art, unlocked=unlocked)

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":
            email = request.form["email"].strip().lower()
            password = request.form["password"]
            if not email or not password:
                flash("Email and password are required.", "error")
                return redirect(url_for("signup"))
            if User.query.filter_by(email=email).first():
                flash("An account with that email already exists.", "error")
                return redirect(url_for("signup"))
            user = User(email=email, password_hash=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for("index"))
        return render_template("signup.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form["email"].strip().lower()
            password = request.form["password"]
            user = User.query.filter_by(email=email).first()
            if user and check_password_hash(user.password_hash, password):
                login_user(user)
                return redirect(url_for("index"))
            flash("Incorrect email or password.", "error")
        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("index"))

    def admin_required(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated or not app.config["ADMIN_EMAIL"]:
                abort(404)
            if current_user.email != app.config["ADMIN_EMAIL"]:
                abort(404)
            return fn(*args, **kwargs)
        return wrapper

    @app.route("/unlock", methods=["GET"])
    @login_required
    def unlock():
        if current_user.has_access:
            return redirect(url_for("index"))

        # Reuse an existing pending/submitted order instead of spawning
        # a new QR (and new amount) every time this page is visited.
        order = Order.query.filter_by(
            user_id=current_user.id, status="pending"
        ).first() or Order.query.filter_by(
            user_id=current_user.id, status="submitted"
        ).first()

        if not order:
            base_price = app.config["UNLOCK_PRICE_INR"]
            order = Order(user_id=current_user.id, status="pending")
            db.session.add(order)
            db.session.flush()  # assigns order.id without committing yet
            order.order_ref = payments.new_order_ref(current_user.id)
            order.amount_rupees = payments.unique_amount(base_price, order.id)
            db.session.commit()

        qr = None
        uri = None
        if order.status == "pending":
            uri = payments.upi_uri(
                order.amount_rupees, f"Unlock access {order.order_ref}", order.order_ref
            )
            qr = payments.qr_data_uri(uri)

        return render_template(
            "pay.html",
            order=order,
            qr_data_uri=qr,
            upi_uri=uri,
            payee_name=os.environ.get("UPI_PAYEE_NAME", "Your Name"),
            vpa=os.environ.get("UPI_VPA", "your-vpa@bank"),
        )

    @app.route("/unlock/submit", methods=["POST"])
    @login_required
    def unlock_submit():
        order = Order.query.filter_by(
            id=request.form.get("order_id"), user_id=current_user.id
        ).first_or_404()
        utr = request.form.get("utr", "").strip()
        if not utr:
            flash("Enter the UPI transaction/reference number from your payment app.", "error")
            return redirect(url_for("unlock"))
        if Order.query.filter_by(utr_number=utr).first():
            flash("That reference number has already been submitted on another order.", "error")
            return redirect(url_for("unlock"))

        order.utr_number = utr
        order.status = "submitted"
        order.submitted_at = datetime.utcnow()
        db.session.commit()
        return redirect(url_for("unlock"))

    @app.route("/admin")
    @admin_required
    def admin():
        pending = (
            Order.query.filter_by(status="submitted")
            .order_by(Order.submitted_at.asc())
            .all()
        )
        return render_template("admin.html", orders=pending)

    @app.route("/admin/orders/<int:order_id>/approve", methods=["POST"])
    @admin_required
    def admin_approve(order_id):
        order = Order.query.get_or_404(order_id)
        order.status = "verified"
        order.verified_at = datetime.utcnow()
        user = db.session.get(User, order.user_id)
        user.has_access = True
        db.session.commit()
        return redirect(url_for("admin"))

    @app.route("/admin/orders/<int:order_id>/reject", methods=["POST"])
    @admin_required
    def admin_reject(order_id):
        order = Order.query.get_or_404(order_id)
        order.status = "rejected"
        db.session.commit()
        return redirect(url_for("admin"))


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
