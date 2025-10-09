from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mail import Mail, Message
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import os
from werkzeug.utils import secure_filename
from datetime import timedelta
from config import DB_CONFIG, SECRET_KEY
import secrets

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.permanent_session_lifetime = timedelta(days=7)

def get_db():
    return mysql.connector.connect(**DB_CONFIG)

# Flask-Mail Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'       # or your SMTP server
app.config['MAIL_PORT'] = 587                      # 465 for SSL, 587 for TLS
app.config['MAIL_USE_TLS'] = True                  # True for TLS, False if using SSL
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'r.rahulwrokmail@gmail.com'  # your email
app.config['MAIL_PASSWORD'] = 'tpcl tvom gkjo jcku'     # app password, not your main login
app.config['MAIL_DEFAULT_SENDER'] = 'r.rahulwrokmail@gmail.com'
# --- Initialize Mail ---
mail = Mail(app)
# ----------------------
# Helpers
# ----------------------

def current_user():
    return session.get("user")


def login_required(role=None):
    def decorator(func):
        def wrapper(*args, **kwargs):
            u = current_user()
            if not u:
                flash("Please log in.", "warning")
                return redirect(url_for("login"))
            if role and u["role"] != role:
                flash("Unauthorized.", "danger")
                return redirect(url_for("index"))
            return func(*args, **kwargs)
        wrapper.__name__ = func.__name__
        return wrapper
    return decorator

# ----------------------
# Auth
# ----------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        role = "user"  # default
        phone = request.form.get("phone", "").strip()
        address = request.form.get("address", "").strip()

        if not name or not email or not password:
            flash("Name, email, and password are required.", "danger")
            return redirect(url_for("register"))

        pw_hash = generate_password_hash(password)

        con = get_db()
        cur = con.cursor(dictionary=True)
        try:
            cur.execute(
                """
                INSERT INTO users(name,email,password_hash,role,phone,address)
                VALUES(%s,%s,%s,%s,%s,%s)
                """,
                (name, email, pw_hash, role, phone, address),
            )
            con.commit()
            flash("Registration successful. Please log in.", "success")
            return redirect(url_for("login"))
        except mysql.connector.IntegrityError:
            flash("Email already exists.", "danger")
        finally:
            cur.close()
            con.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        con = get_db()
        cur = con.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()
        cur.close()
        con.close()

        if user and check_password_hash(user["password_hash"], password):
            session.permanent = True
            session["user"] = {"id": user["id"], "name": user["name"], "role": user["role"]}
            flash(f"Welcome, {user['name']}!", "success")
            return redirect(url_for("route_by_role"))
        else:
            flash("Invalid credentials.", "danger")

    return render_template("login.html")

import secrets
from datetime import datetime, timedelta

@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"].strip().lower()

        con = get_db()
        cur = con.cursor(dictionary=True)
        cur.execute("SELECT * FROM users WHERE email=%s", (email,))
        user = cur.fetchone()

        if user:
            # Generate token + expiry
            token = secrets.token_urlsafe(32)
            expiry = datetime.utcnow() + timedelta(hours=1)

            # Save in DB
            cur.execute("INSERT INTO password_resets(user_id, token, expires_at) VALUES(%s,%s,%s)",
                        (user["id"], token, expiry))
            con.commit()

            # Reset link
            reset_link = url_for("reset_password", token=token, _external=True)

            # Send Email
            msg = Message("Password Reset Request", recipients=[user["email"]])
            msg.body = f"""
Hello {user['name']},

You requested to reset your password.

Click the link below to reset it:
{reset_link}

This link will expire in 1 hour.

If you did not request this, please ignore this email.
"""
            mail.send(msg)

            flash("A password reset link has been sent to your email.", "info")
        else:
            flash("Email not found.", "danger")

        cur.close()
        con.close()

    return render_template("forgot_password.html")



@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    con = get_db()
    cur = con.cursor(dictionary=True)
    cur.execute("SELECT * FROM password_resets WHERE token=%s AND expires_at > NOW()", (token,))
    record = cur.fetchone()

    if not record:
        flash("Invalid or expired reset link.", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        password = request.form["password"]
        pw_hash = generate_password_hash(password)

        cur.execute("UPDATE users SET password_hash=%s WHERE id=%s", (pw_hash, record["user_id"]))
        cur.execute("DELETE FROM password_resets WHERE id=%s", (record["id"],))  # cleanup
        con.commit()
        cur.close()
        con.close()

        flash("Password reset successful. Please log in.", "success")
        return redirect(url_for("login"))

    cur.close()
    con.close()
    return render_template("reset_password.html", token=token)

@app.route("/logout")
def logout():
    session.pop("user", None)
    flash("Logged out.", "info")
    return redirect(url_for("index"))


@app.route("/route")
def route_by_role():
    u = current_user()
    if not u:
        return redirect(url_for("login"))
    role = u["role"]
    if role == "admin":
        return redirect(url_for("admin_dashboard"))
    if role == "harbour":
        return redirect(url_for("harbour_dashboard"))
    if role == "delivery":
        return redirect(url_for("delivery_dashboard"))
    return redirect(url_for("user_dashboard"))

# ----------------------
# General pages
# ----------------------

@app.route("/")
def index():
    return render_template("index.html", u=current_user())


@app.route("/profile", methods=["GET", "POST"])
def profile():
    u = current_user()
    if not u:
        return redirect(url_for("login"))

    con = get_db()
    cur = con.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form["name"]
        phone = request.form.get("phone", "")
        address = request.form.get("address", "")
        cur.execute(
            "UPDATE users SET name=%s, phone=%s, address=%s WHERE id=%s",
            (name, phone, address, u["id"]),
        )
        con.commit()
        session["user"]["name"] = name
        flash("Profile updated.", "success")

    cur.execute("SELECT * FROM users WHERE id=%s", (u["id"],))
    user = cur.fetchone()
    cur.close()
    con.close()
    return render_template("profile.html", user=user)

# ----------------------
# Admin
# ----------------------

@app.route("/admin")
@login_required(role="admin")
def admin_dashboard():
    con = get_db()
    cur = con.cursor(dictionary=True)
    cur.execute("SELECT COUNT(*) as c FROM users WHERE role='user'")
    users_count = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM harbours")
    harbours_count = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM fish")
    fish_count = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) as c FROM orders")
    orders_count = cur.fetchone()["c"]
    cur.close()
    con.close()
    return render_template(
        "admin/dashboard.html",
        users_count=users_count,
        harbours_count=harbours_count,
        fish_count=fish_count,
        orders_count=orders_count,
    )


@app.route("/admin/users")
@login_required(role="admin")
def admin_users():
    con = get_db()
    cur = con.cursor(dictionary=True)
    cur.execute("SELECT id,name,email,role,phone,address FROM users ORDER BY id DESC")
    users = cur.fetchall()
    cur.close()
    con.close()
    return render_template("admin/users.html", users=users)


@app.route("/admin/harbours", methods=["GET", "POST"])
@login_required(role="admin")
def admin_harbours():
    con = get_db()
    cur = con.cursor(dictionary=True)
    if request.method == "POST":
        name = request.form["name"]
        location = request.form["location"]
        contact = request.form.get("contact", "")
        owner_id = request.form["owner_id"]
        cur.execute(
            "INSERT INTO harbours(name,location,contact,user_id) VALUES(%s,%s,%s,%s)",
            (name, location, contact, owner_id),
        )
        con.commit()
        flash("Harbour added.", "success")
    cur.execute(
        """
        SELECT h.*, u.name as owner_name FROM harbours h
        JOIN users u ON u.id = h.user_id
        ORDER BY h.id DESC
        """
    )
    harbours = cur.fetchall()
    cur.execute("SELECT id,name FROM users WHERE role='harbour'")
    owners = cur.fetchall()
    cur.close()
    con.close()
    return render_template("admin/harbours.html", harbours=harbours, owners=owners)

@app.route("/admin/harbours/<int:hid>/edit", methods=["GET", "POST"])
@login_required(role="admin")
def admin_edit_harbour(hid):
    con = get_db()
    cur = con.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form["name"]
        location = request.form["location"]
        contact = request.form["contact"]
        owner_id = request.form["owner_id"]

        cur.execute(
            "UPDATE harbours SET name=%s, location=%s, contact=%s, user_id=%s WHERE id=%s",
            (name, location, contact, owner_id, hid),
        )
        con.commit()
        flash("Harbour updated successfully.", "success")
        return redirect(url_for("admin_harbours"))

    cur.execute("SELECT * FROM harbours WHERE id=%s", (hid,))
    harbour = cur.fetchone()
    cur.execute("SELECT id, name FROM users WHERE role='harbour'")
    owners = cur.fetchall()

    cur.close()
    con.close()
    return render_template("admin/edit_harbour.html", harbour=harbour, owners=owners)

@app.route("/admin/harbours/<int:hid>/delete", methods=["POST"])
@login_required(role="admin")
def admin_delete_harbour(hid):
    con = get_db()
    cur = con.cursor()
    cur.execute("DELETE FROM harbours WHERE id=%s", (hid,))
    con.commit()
    cur.close()
    con.close()
    flash("Harbour deleted.", "info")
    return redirect(url_for("admin_harbours"))



@app.route("/admin/boats", methods=["GET", "POST"])
@login_required(role="admin")
def admin_boats():
    con = get_db()
    cur = con.cursor(dictionary=True)
    if request.method == "POST":
        name = request.form["name"]
        capacity = int(request.form.get("capacity", 0))
        harbour_id = request.form["harbour_id"]
        cur.execute(
            "INSERT INTO boats(name,capacity,harbour_id) VALUES(%s,%s,%s)",
            (name, capacity, harbour_id),
        )
        con.commit()
        flash("Boat added.", "success")
    cur.execute(
        """
        SELECT b.*, h.name as harbour_name FROM boats b
        JOIN harbours h ON h.id=b.harbour_id ORDER BY b.id DESC
        """
    )
    boats = cur.fetchall()
    cur.execute("SELECT id,name FROM harbours")
    harbour_list = cur.fetchall()
    cur.close()
    con.close()
    return render_template("admin/boats.html", boats=boats, harbour_list=harbour_list)

@app.route("/admin/boats/<int:bid>/edit", methods=["GET", "POST"])
@login_required(role="admin")
def admin_edit_boat(bid):
    con = get_db()
    cur = con.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form["name"]
        capacity = int(request.form["capacity"])
        harbour_id = request.form["harbour_id"]

        cur.execute(
            "UPDATE boats SET name=%s, capacity=%s, harbour_id=%s WHERE id=%s",
            (name, capacity, harbour_id, bid),
        )
        con.commit()
        flash("Boat updated successfully.", "success")
        return redirect(url_for("admin_boats"))

    cur.execute("SELECT * FROM boats WHERE id=%s", (bid,))
    boat = cur.fetchone()
    cur.execute("SELECT id, name FROM harbours")
    harbour_list = cur.fetchall()

    cur.close()
    con.close()
    return render_template("admin/edit_boat.html", boat=boat, harbour_list=harbour_list)

@app.route("/admin/boats/<int:bid>/delete", methods=["POST"])
@login_required(role="admin")
def admin_delete_boat(bid):
    con = get_db()
    cur = con.cursor()
    cur.execute("DELETE FROM boats WHERE id=%s", (bid,))
    con.commit()
    cur.close()
    con.close()
    flash("Boat deleted.", "info")
    return redirect(url_for("admin_boats"))



# Configure upload folder for fish images
UPLOAD_FOLDER = os.path.join("static", "uploads", "fish")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

@app.route("/admin/fish", methods=["GET", "POST"])
@login_required(role="admin")
def admin_fish():
    con = get_db()
    cur = con.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form["name"].strip()
        price = float(request.form["price"])
        stock = int(request.form["stock"])
        harbour_id = request.form["harbour_id"]

        # Handle image upload
        image_file = request.files.get("image")
        image_filename = None
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            image_file.save(image_path)
            image_filename = filename

        cur.execute(
            "INSERT INTO fish(name, price, stock, harbour_id, image) VALUES(%s,%s,%s,%s,%s)",
            (name, price, stock, harbour_id, image_filename),
        )
        con.commit()
        flash("Fish added successfully with image.", "success")

    # Fetch fish list with harbour name
    cur.execute(
        """
        SELECT f.*, h.name as harbour_name 
        FROM fish f
        JOIN harbours h ON h.id=f.harbour_id 
        ORDER BY f.id DESC
        """
    )
    fish = cur.fetchall()

    # Fetch harbours list for dropdown
    cur.execute("SELECT id, name FROM harbours")
    harbours = cur.fetchall()

    cur.close()
    con.close()
    return render_template("admin/fish.html", fish=fish, harbours=harbours)

@app.route("/admin/fish/<int:fid>/edit", methods=["GET", "POST"])
@login_required(role="admin")
def admin_edit_fish(fid):
    con = get_db()
    cur = con.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form["name"]
        price = float(request.form["price"])
        stock = int(request.form["stock"])
        harbour_id = request.form["harbour_id"]

        # Handle new image if uploaded
        image_file = request.files.get("image")
        image_filename = None
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            image_file.save(image_path)
            image_filename = filename

            cur.execute(
                "UPDATE fish SET name=%s, price=%s, stock=%s, harbour_id=%s, image=%s WHERE id=%s",
                (name, price, stock, harbour_id, image_filename, fid),
            )
        else:
            cur.execute(
                "UPDATE fish SET name=%s, price=%s, stock=%s, harbour_id=%s WHERE id=%s",
                (name, price, stock, harbour_id, fid),
            )

        con.commit()
        flash("Fish updated successfully.", "success")
        return redirect(url_for("admin_fish"))

    cur.execute("SELECT * FROM fish WHERE id=%s", (fid,))
    fish = cur.fetchone()
    cur.execute("SELECT id, name FROM harbours")
    harbours = cur.fetchall()

    cur.close()
    con.close()
    return render_template("admin/edit_fish.html", fish=fish, harbours=harbours)

@app.route("/admin/fish/<int:fid>/delete", methods=["POST"])
@login_required(role="admin")
def admin_delete_fish(fid):
    con = get_db()
    cur = con.cursor()
    cur.execute("DELETE FROM fish WHERE id=%s", (fid,))
    con.commit()
    cur.close()
    con.close()
    flash("Fish deleted.", "info")
    return redirect(url_for("admin_fish"))



@app.route("/admin/feedback")
@login_required(role="admin")
def admin_feedback():
    con = get_db()
    cur = con.cursor(dictionary=True)
    cur.execute(
        """
        SELECT f.*, u.name as user_name FROM feedback f
        JOIN users u ON u.id=f.user_id ORDER BY f.id DESC
        """
    )
    items = cur.fetchall()
    cur.close()
    con.close()
    return render_template("admin/feedback.html", items=items)


@app.route("/admin/complaints", methods=["GET", "POST"])
@login_required(role="admin")
def admin_complaints():
    con = get_db()
    cur = con.cursor(dictionary=True)
    if request.method == "POST":
        cid = request.form["complaint_id"]
        reply = request.form["reply"]
        cur.execute("UPDATE complaints SET reply=%s WHERE id=%s", (reply, cid))
        con.commit()
        flash("Reply sent.", "success")
    cur.execute(
        """
        SELECT c.*, u.name as user_name, u.email FROM complaints c
        JOIN users u ON u.id=c.user_id ORDER BY c.id DESC
        """
    )
    items = cur.fetchall()
    cur.close()
    con.close()
    return render_template("admin/complaints.html", items=items)

# ----------------------
# Admin - Delivery Boys
# ----------------------

@app.route("/admin/delivery", methods=["GET", "POST"])
@login_required(role="admin")
def admin_delivery():
    con = get_db()
    cur = con.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        phone = request.form.get("phone", "")
        address = request.form.get("address", "")
        password = request.form["password"]

        if not name or not email or not password:
            flash("Name, email, and password are required.", "danger")
            return redirect(url_for("admin_delivery"))

        pw_hash = generate_password_hash(password)

        try:
            cur.execute(
                """
                INSERT INTO users(name,email,password_hash,role,phone,address,status)
                VALUES(%s,%s,%s,'delivery',%s,%s,'active')
                """,
                (name, email, pw_hash, phone, address),
            )
            con.commit()
            flash("Delivery boy added successfully.", "success")
        except mysql.connector.IntegrityError:
            flash("Email already exists.", "danger")

    cur.execute("SELECT id,name,email,phone,address,status FROM users WHERE role='delivery' ORDER BY id DESC")
    deliveries = cur.fetchall()

    cur.close()
    con.close()
    return render_template("admin/delivery.html", deliveries=deliveries)


@app.route("/admin/delivery/<int:did>/edit", methods=["GET", "POST"])
@login_required(role="admin")
def admin_edit_delivery(did):
    con = get_db()
    cur = con.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form["name"]
        phone = request.form.get("phone", "")
        address = request.form.get("address", "")
        status = request.form.get("status", "active")
        password = request.form.get("password", "")

        if password:
            pw_hash = generate_password_hash(password)
            cur.execute(
                "UPDATE users SET name=%s, phone=%s, address=%s, password_hash=%s, status=%s WHERE id=%s AND role='delivery'",
                (name, phone, address, pw_hash, status, did),
            )
        else:
            cur.execute(
                "UPDATE users SET name=%s, phone=%s, address=%s, status=%s WHERE id=%s AND role='delivery'",
                (name, phone, address, status, did),
            )
        con.commit()
        flash("Delivery boy updated successfully.", "success")
        return redirect(url_for("admin_delivery"))

    cur.execute("SELECT * FROM users WHERE id=%s AND role='delivery'", (did,))
    delivery = cur.fetchone()
    cur.close()
    con.close()
    return render_template("admin/edit_delivery.html", delivery=delivery)


@app.route("/admin/delivery/<int:did>/toggle", methods=["POST"])
@login_required(role="admin")
def admin_toggle_delivery(did):
    con = get_db()
    cur = con.cursor(dictionary=True)

    cur.execute("SELECT status FROM users WHERE id=%s AND role='delivery'", (did,))
    delivery = cur.fetchone()
    if delivery:
        new_status = "inactive" if delivery["status"] == "active" else "active"
        cur.execute("UPDATE users SET status=%s WHERE id=%s AND role='delivery'", (new_status, did))
        con.commit()
        flash(f"Delivery boy status set to {new_status}.", "info")

    cur.close()
    con.close()
    return redirect(url_for("admin_delivery"))

# ----------------------
# Harbour
# ----------------------

@app.route("/harbour")
@login_required(role="harbour")
def harbour_dashboard():
    u = current_user()
    con = get_db()
    cur = con.cursor(dictionary=True)
    cur.execute("SELECT * FROM harbours WHERE user_id=%s", (u["id"],))
    harbour = cur.fetchone()
    harbour_id = harbour["id"] if harbour else None
    cur.execute("SELECT COUNT(*) c FROM orders WHERE harbour_id=%s", (harbour_id,))
    orders_count = cur.fetchone()["c"] if harbour_id else 0
    cur.execute("SELECT COUNT(*) c FROM fish WHERE harbour_id=%s", (harbour_id,))
    fish_count = cur.fetchone()["c"] if harbour_id else 0
    cur.execute("SELECT COUNT(*) c FROM boats WHERE harbour_id=%s", (harbour_id,))
    boats_count = cur.fetchone()["c"] if harbour_id else 0
    cur.close()
    con.close()
    return render_template(
        "harbour/dashboard.html",
        harbour=harbour,
        orders_count=orders_count,
        fish_count=fish_count,
        boats_count=boats_count,
    )

@app.route("/harbour/boats")
@login_required(role="harbour")
def harbour_boats():
    u = current_user()
    con = get_db()
    cur = con.cursor(dictionary=True)

    # Get the harbour linked to this user
    cur.execute("SELECT * FROM harbours WHERE user_id=%s", (u["id"],))
    harbour = cur.fetchone()

    if not harbour:
        flash("No harbour profile found. Ask admin to create one.", "warning")
        cur.close()
        con.close()
        return redirect(url_for("harbour_dashboard"))

    # Fetch boats for this harbour
    cur.execute("SELECT * FROM boats WHERE harbour_id=%s ORDER BY id DESC", (harbour["id"],))
    boats = cur.fetchall()

    cur.close()
    con.close()
    return render_template("harbour/boats.html", boats=boats, harbour=harbour)


@app.route("/harbour/stock", methods=["GET", "POST"])
@login_required(role="harbour")
def harbour_stock():
    u = current_user()
    con = get_db()
    cur = con.cursor(dictionary=True)
    cur.execute("SELECT * FROM harbours WHERE user_id=%s", (u["id"],))
    harbour = cur.fetchone()
    if not harbour:
        flash("No harbour profile yet. Ask admin to create one.", "warning")
        return redirect(url_for("harbour_dashboard"))
    if request.method == "POST":
        fid = request.form.get("fish_id")
        stock = int(request.form.get("stock", "0"))
        price = float(request.form.get("price", "0"))
        cur.execute(
            "UPDATE fish SET stock=%s, price=%s WHERE id=%s AND harbour_id=%s",
            (stock, price, fid, harbour["id"]),
        )
        con.commit()
        flash("Stock updated.", "success")
    cur.execute("SELECT * FROM fish WHERE harbour_id=%s ORDER BY id DESC", (harbour["id"],))
    fish = cur.fetchall()
    cur.close()
    con.close()
    return render_template("harbour/stock.html", fish=fish)


@app.route("/harbour/orders", methods=["GET", "POST"])
@login_required(role="harbour")
def harbour_orders():
    u = current_user()
    con = get_db()
    cur = con.cursor(dictionary=True)

    # Get this harbour's info
    cur.execute("SELECT * FROM harbours WHERE user_id=%s", (u["id"],))
    harbour = cur.fetchone()
    if not harbour:
        flash("No harbour profile.", "warning")
        cur.close()
        con.close()
        return redirect(url_for("harbour_dashboard"))

    # If assigning a delivery person
    if request.method == "POST":
        order_id = request.form["order_id"]
        delivery_user_id = request.form["delivery_user_id"]
        cur.execute("SELECT id FROM deliveries WHERE order_id=%s", (order_id,))
        d = cur.fetchone()
        if d:
            cur.execute(
                "UPDATE deliveries SET delivery_user_id=%s, status='assigned' WHERE order_id=%s",
                (delivery_user_id, order_id),
            )
        else:
            cur.execute(
                "INSERT INTO deliveries(order_id, delivery_user_id, status) VALUES(%s,%s,'assigned')",
                (order_id, delivery_user_id),
            )
        cur.execute("UPDATE orders SET status='assigned' WHERE id=%s", (order_id,))
        con.commit()
        flash("Order assigned to delivery.", "success")

    # Fetch all orders for this harbour
    cur.execute(
        """
        SELECT o.*, u.name as user_name FROM orders o
        JOIN users u ON u.id=o.user_id
        WHERE o.harbour_id=%s ORDER BY o.id DESC
        """,
        (harbour["id"],),
    )
    orders = cur.fetchall()

    # Attach order items with cleaning info
    for o in orders:
        cur.execute(
            """
            SELECT oi.quantity, oi.clean, f.name
            FROM order_items oi
            JOIN fish f ON f.id = oi.fish_id
            WHERE oi.order_id=%s
            """,
            (o["id"],),
        )
        o["items"] = cur.fetchall()

        # Get available delivery users (only active ones)
    cur.execute("SELECT id,name FROM users WHERE role='delivery' AND status='active'")
    deliveries = cur.fetchall()

    cur.close()
    con.close()

    return render_template("harbour/orders.html", orders=orders, deliveries=deliveries)



# ----------------------
# User (Customer)
# ----------------------

@app.route("/user")
@login_required(role="user")
def user_dashboard():
    con = get_db()
    cur = con.cursor(dictionary=True)
    cur.execute("SELECT * FROM harbours ORDER BY id DESC")
    harbours = cur.fetchall()
    cur.close()
    con.close()
    return render_template("user/dashboard.html", harbours=harbours)


@app.route("/harbours/<int:harbour_id>/fish")
def view_fish(harbour_id):
    con = get_db()
    cur = con.cursor(dictionary=True)
    cur.execute("SELECT * FROM harbours WHERE id=%s", (harbour_id,))
    harbour = cur.fetchone()
    cur.execute("SELECT * FROM fish WHERE harbour_id=%s ORDER BY id DESC", (harbour_id,))
    fish = cur.fetchall()
    cur.close()
    con.close()
    return render_template("user/fish.html", harbour=harbour, fish=fish)


@app.route("/cart/add", methods=["POST"])
@login_required(role="user")
def add_to_cart():
    fid = int(request.form["fish_id"])
    qty = int(request.form["quantity"])
    clean = request.form.get("clean") == "yes"

    cart = session.get("cart", {})

    # initialize OR convert old int format to dict format
    if str(fid) not in cart or isinstance(cart[str(fid)], int):
        cart[str(fid)] = {"qty": 0, "clean": False}

    cart[str(fid)]["qty"] += qty

    if clean:
        cart[str(fid)]["clean"] = True

    session["cart"] = cart
    flash("Added to cart.", "success")
    return redirect(request.referrer or url_for("user_dashboard"))


@app.route("/cart")
@login_required(role="user")
def view_cart():
    cart = session.get("cart", {})
    if not cart:
        return render_template("user/cart.html", items=[], total=0)
    ids = list(cart.keys())
    placeholders = ",".join(["%s"] * len(ids))
    con = get_db()
    cur = con.cursor(dictionary=True)
    cur.execute(f"SELECT * FROM fish WHERE id IN ({placeholders})", ids)
    fish_rows = cur.fetchall()
    items = []
    total = 0
    for f in fish_rows:
        entry = cart[str(f["id"])]
        qty = entry["qty"]
        amount = f["price"] * qty
        if entry.get("clean"):  # add cleaning charge
            amount += 100
        total += amount
        items.append({"fish": f, "qty": qty, "clean": entry.get("clean"), "amount": amount})
    cur.close()
    con.close()
    return render_template("user/cart.html", items=items, total=total)


@app.route("/cart/checkout", methods=["POST"])
@login_required(role="user")
def checkout():
    cart = session.get("cart", {})
    if not cart:
        flash("Cart is empty.", "warning")
        return redirect(url_for("view_cart"))

    ids = list(cart.keys())
    placeholders = ",".join(["%s"] * len(ids))

    con = get_db()
    cur = con.cursor(dictionary=True)

    # Fetch fish items in cart
    cur.execute(f"SELECT * FROM fish WHERE id IN ({placeholders})", ids)
    fish_rows = cur.fetchall()
    if not fish_rows:
        flash("Invalid cart.", "danger")
        cur.close()
        con.close()
        return redirect(url_for("view_cart"))

    harbour_id = fish_rows[0]["harbour_id"]
    total = 0

    # Check stock and compute total
    for f in fish_rows:
        entry = cart[str(f["id"])]
        qty = entry["qty"]
        if qty > f["stock"]:
            flash(f"Not enough stock for {f['name']}.", "danger")
            cur.close()
            con.close()
            return redirect(url_for("view_cart"))
        amount = f["price"] * qty
        if entry.get("clean"):
            amount += 100  # cleaning fee
        total += amount

    try:
        # Start transaction
        cur.execute(
            "INSERT INTO orders(user_id, harbour_id, status, total_amount) VALUES(%s,%s,'pending',%s)",
            (current_user()["id"], harbour_id, total),
        )
        order_id = cur.lastrowid

        # Insert order_items with cleaning info
        for f in fish_rows:
            entry = cart[str(f["id"])]
            qty = entry["qty"]
            clean = 1 if entry.get("clean") else 0
            cur.execute(
                "INSERT INTO order_items(order_id, fish_id, quantity, price, clean) VALUES(%s,%s,%s,%s,%s)",
                (order_id, f["id"], qty, f["price"], clean),
            )
            cur.execute("UPDATE fish SET stock=stock-%s WHERE id=%s", (qty, f["id"]))

        con.commit()
    except Exception as e:
        con.rollback()
        cur.close()
        con.close()
        flash(f"Checkout failed: {str(e)}", "danger")
        return redirect(url_for("view_cart"))

    session["cart"] = {}
    flash(f"Order #{order_id} placed successfully! (mock payment).", "success")

    cur.close()
    con.close()
    return redirect(url_for("user_orders"))


@app.route("/user/orders")
@login_required(role="user")
def user_orders():
    con = get_db()
    cur = con.cursor(dictionary=True)
    cur.execute(
        """
        SELECT o.*, h.name as harbour_name, d.status as delivery_status
        FROM orders o
        JOIN harbours h ON h.id=o.harbour_id
        LEFT JOIN deliveries d ON d.order_id = o.id
        WHERE o.user_id=%s
        ORDER BY o.id DESC
        """,
        (current_user()["id"],),
    )
    orders = cur.fetchall()
    cur.close()
    con.close()
    return render_template("user/orders.html", orders=orders)


@app.route("/complaint", methods=["GET", "POST"])
@login_required(role="user")
def complaint():
    con = get_db()
    cur = con.cursor(dictionary=True)
    if request.method == "POST":
        msg = request.form["message"]
        cur.execute("INSERT INTO complaints(user_id, message) VALUES(%s,%s)", (current_user()["id"], msg))
        con.commit()
        flash("Complaint submitted.", "success")
    cur.execute("SELECT * FROM complaints WHERE user_id=%s ORDER BY id DESC", (current_user()["id"],))
    items = cur.fetchall()
    cur.close()
    con.close()
    return render_template("user/complaints.html", items=items)


@app.route("/feedback", methods=["GET", "POST"])
@login_required(role="user")
def feedback():
    con = get_db()
    cur = con.cursor(dictionary=True)
    if request.method == "POST":
        rating = int(request.form["rating"])
        message = request.form.get("message", "")
        cur.execute("INSERT INTO feedback(user_id, rating, message) VALUES(%s,%s,%s)", (current_user()["id"], rating, message))
        con.commit()
        flash("Feedback sent. Thanks!", "success")
    cur.execute("SELECT * FROM feedback WHERE user_id=%s ORDER BY id DESC", (current_user()["id"],))
    items = cur.fetchall()
    cur.close()
    con.close()
    return render_template("user/feedback.html", items=items)

# ----------------------
# Delivery
# ----------------------

@app.route("/delivery")
@login_required(role="delivery")
def delivery_dashboard():
    con = get_db()
    cur = con.cursor(dictionary=True)
    cur.execute(
        """
        SELECT d.*, o.total_amount, o.status as order_status,
           u.name as customer_name, u.phone as customer_phone, u.address as customer_address
    FROM deliveries d
    JOIN orders o ON o.id=d.order_id
    JOIN users u ON u.id=o.user_id
    WHERE d.delivery_user_id=%s
    ORDER BY d.id DESC
        """,
        (current_user()["id"],),
    )
    items = cur.fetchall()
    cur.close()
    con.close()
    return render_template("delivery/dashboard.html", items=items)


@app.route("/delivery/update", methods=["POST"])
@login_required(role="delivery")
def delivery_update():
    delivery_id = request.form["delivery_id"]
    status = request.form["status"]
    con = get_db()
    cur = con.cursor(dictionary=True)
    cur.execute("UPDATE deliveries SET status=%s WHERE id=%s", (status, delivery_id))
    if status == "delivered":
        cur.execute(
            """
            UPDATE orders o
            JOIN deliveries d ON d.order_id=o.id
            SET o.status='delivered'
            WHERE d.id=%s
            """,
            (delivery_id,),
        )
    con.commit()
    cur.close()
    con.close()
    flash("Status updated.", "success")
    return redirect(url_for("delivery_dashboard"))

# ----------------------
# Utilities
# ----------------------

@app.context_processor
def inject_globals():
    return {"u": current_user()}


@app.template_filter("inr")
def inr(amount):
    return f"₹{amount:,.2f}"


if __name__ == "__main__":
    app.run(debug=True)
