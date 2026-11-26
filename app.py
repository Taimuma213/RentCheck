"""RentCheck - Parts 1 to 4: Rentor flow (Identity to Report, Tenant requests) and Rentee flow (Identity to Rent report)."""

import json
import os
import re
import uuid
from datetime import datetime
from functools import wraps

from flask import (Flask, Response, abort, flash, redirect, render_template, request,
                   session, url_for)
from fpdf import FPDF
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import documents

app = Flask(__name__)
app.secret_key = "rentcheck-secret-key-change-me"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
NID_FILE = os.path.join(DATA_DIR, "nid_records.json")
PROPERTIES_FILE = os.path.join(DATA_DIR, "properties.json")
APPOINTMENTS_FILE = os.path.join(DATA_DIR, "appointments.json")
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
FLAT_DIR = os.path.join(UPLOAD_DIR, "flats")
DOC_DIR = os.path.join(UPLOAD_DIR, "documents")

# Steps shown in the left sidebar.
RENTOR_STEPS = ["Identity", "Property", "Documents", "Cross-check", "Risk", "Report"]
RENTEE_STEPS = ["Identity", "Preferences", "Homes", "Property check", "Rent report"]
IDENTITY_FIELDS = ("full_name", "nid", "dob", "phone")
PROPERTY_TYPES = ["Apartment", "House", "Shared apartment"]
DOC_ROWS = [
    ("rental_agreement", "Rental agreement"),
    ("utility_bill", "Utility bill"),
    ("ownership_paper", "Ownership paper"),
    ("landlord_id_copy", "Landlord ID copy")
]
IMAGE_EXT = {"jpg", "jpeg", "png", "webp"}
DOC_EXT = {"pdf", "jpg", "jpeg", "png"}
MAX_PHOTOS = 8
LEVEL_ANGLE = {"Low": -60, "Medium": 0, "High": 60}  # where the gauge needle points
AREAS = [
    "Dhanmondi", "Uttara", "Mirpur", "Gulshan", "Banani", "Mohammadpur",
    "Bashundhara", "Badda", "Rampura", "Khilgaon", "Motijheel", "Tejgaon"
]
TYPE_WORD = {"Apartment": "flat", "House": "house", "Shared apartment": "shared apartment"}
BEDROOM_OPTIONS = ["Any", "1", "2", "3", "4+"]
BATHROOM_OPTIONS = ["Any", "1", "2", "3", "4+"]
HOMES_PER_PAGE = 6


# ============================ JSON FILE HELPERS ============================

def load_json(path, default=None):
    if not os.path.exists(path):
        return [] if default is None else default

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def setup_data_files():
    """Create the data folder and two demo accounts the first time the app runs."""

    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(FLAT_DIR, exist_ok=True)
    os.makedirs(DOC_DIR, exist_ok=True)

    if not os.path.exists(PROPERTIES_FILE):
        save_json(PROPERTIES_FILE, [])

    if not os.path.exists(APPOINTMENTS_FILE):
        save_json(APPOINTMENTS_FILE, [])

    if not os.path.exists(USERS_FILE):
        save_json(USERS_FILE, [
            {
                "name": "Demo Rentor",
                "email": "rentor@demo.com",
                "role": "Rentor",
                "password": generate_password_hash("demo123")
            },
            {
                "name": "Demo Rentee",
                "email": "rentee@demo.com",
                "role": "Rentee",
                "password": generate_password_hash("demo123")
            },
        ])


# ============================ USERS AND LOGIN ============================

login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "warning"


class User(UserMixin):

    def __init__(self, data):
        self.id = data["email"]
        self.name = data["name"]
        self.role = data["role"]


def find_user(email):

    for user in load_json(USERS_FILE):
        if user["email"] == email:
            return user

    return None


@login_manager.user_loader
def load_user(email):

    data = find_user(email)

    return User(data) if data else None


def role_required(role):
    """Allow a page only for one role."""

    def decorator(view):

        @wraps(view)
        def wrapper(*args, **kwargs):

            if current_user.role != role:
                flash(
                    f"That page is only for {role}s.",
                    "warning"
                )
                return redirect(url_for("identity"))

            return view(*args, **kwargs)

        return login_required(wrapper)

    return decorator


@app.template_filter("num")
def show_number(value):
    """Show 25000.0 as 25000 and keep empty values empty."""

    if value in ("", None):
        return ""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return value

    return int(number) if number == int(number) else number


@app.template_filter("pill")
def pill_class(value):
    """Colour of a status badge: green, yellow or red."""

    if value in ("Matched", "Clear", "Yes", "Low", "Have", "Verified"):
        return "pill-green"

    if value in ("Issue", "Missing", "No", "High"):
        return "pill-red"

    return "pill-yellow"


@app.template_filter("tk")
def money(value):
    """Show 25000 as Tk 25,000."""

    try:
        return "Tk {:,.0f}".format(float(value))
    except (TypeError, ValueError):
        return "Tk 0"


@app.template_filter("initial")
def first_letter(name):

    return (name or "?").strip()[:1].upper() or "?"


@app.template_filter("avatar_color")
def avatar_color(name):

    colors = ["#C77700", "#0B4D33", "#6A3FA0", "#1F6FB2", "#A83255"]

    return colors[sum(ord(c) for c in (name or "")) % len(colors)]


@app.context_processor
def inject_navigation():
    """Menu items depend on the role."""

    links = []

    if current_user.is_authenticated:

        if current_user.role == "Rentor":
            wanted = [
                ("Add property", "rentor_property"),
                ("Tenant requests", "tenant_requests")
            ]
        else:
            wanted = [
                ("Find homes", "rentee_preferences")
            ]

        links = [
            (label, endpoint)
            for label, endpoint in wanted
            if endpoint in app.view_functions
        ]

    return {"nav_links": links}


# ============================ DUMMY NID CHECK ============================

def clean_name(text):
    return " ".join((text or "").split()).lower()


def check_identity(full_name, nid, dob):
    """
    Return Matched only if name, NID number and date of birth
    all match one valid dummy record.

    Invalid or empty records are skipped safely.
    """

    records = load_json(NID_FILE)

    if not isinstance(records, list):
        return "Needs Review"

    for record in records:

        # Skip empty or invalid records
        if not isinstance(record, dict):
            continue

        # Use .get() to avoid KeyError
        record_nid = str(record.get("nid_number", "")).strip()
        record_name = str(record.get("full_name", "")).strip()
        record_dob = str(record.get("date_of_birth", "")).strip()

        # Skip incomplete records
        if not record_nid or not record_name or not record_dob:
            continue

        if record_nid == str(nid).strip():

            same_name = (
                clean_name(record_name)
                == clean_name(full_name)
            )

            same_dob = (
                record_dob == str(dob).strip()
            )

            return (
                "Matched"
                if same_name and same_dob
                else "Needs Review"
            )

    return "Needs Review"


# ============================ LOGIN / REGISTER / LOGOUT ============================

@app.route("/")
def index():

    return redirect(
        url_for("identity")
        if current_user.is_authenticated
        else url_for("login")
    )


@app.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("identity"))

    role = request.form.get("role", "Rentee")

    if request.method == "POST":

        email = request.form.get(
            "email", ""
        ).strip().lower()

        user = find_user(email)

        if not user or not check_password_hash(
            user["password"],
            request.form.get("password", "")
        ):

            flash("Wrong email or password.", "danger")

        elif user["role"] != role:

            flash(
                f"This account is registered as a {user['role']}. "
                f"Please select {user['role']}.",
                "danger"
            )

        else:

            login_user(User(user))

            return redirect(url_for("identity"))

    return render_template("login.html", role=role)


@app.route("/register", methods=["GET", "POST"])
def register():

    if current_user.is_authenticated:
        return redirect(url_for("identity"))

    role = request.form.get("role", "Rentee")

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not name or not re.match(
            r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
            email
        ):

            flash(
                "Please enter your full name and a valid email address.",
                "danger"
            )

        elif len(password) < 6:

            flash(
                "Password must be at least 6 characters.",
                "danger"
            )

        elif role not in ("Rentee", "Rentor"):

            flash(
                "Please choose Rentee or Rentor.",
                "danger"
            )

        elif find_user(email):

            flash(
                "This email is already registered. Please log in.",
                "danger"
            )

        else:

            users = load_json(USERS_FILE)

            users.append({
                "name": name,
                "email": email,
                "role": role,
                "password": generate_password_hash(password)
            })

            save_json(USERS_FILE, users)

            flash(
                "Account created. You can log in now.",
                "success"
            )

            return redirect(url_for("login"))

    return render_template("register.html", role=role)


@app.route("/logout")
@login_required
def logout():

    logout_user()
    session.clear()

    return redirect(url_for("login"))


# ============================ SHARED PAGES ============================

@app.route("/identity", methods=["GET", "POST"])
@login_required
def identity():

    steps = (
        RENTOR_STEPS
        if current_user.role == "Rentor"
        else RENTEE_STEPS
    )

    next_page = (
        "rentor_property"
        if current_user.role == "Rentor"
        else "rentee_preferences"
    )

    saved = session.get("identity", {})

    values = {
        k: saved.get(k, "")
        for k in IDENTITY_FIELDS
    }

    def unchanged():
        return all(
            values[k] == saved.get(k)
            for k in IDENTITY_FIELDS
        )

    if request.method == "POST":

        values = {
            k: request.form.get(k, "").strip()
            for k in IDENTITY_FIELDS
        }

        action = request.form.get("action")

        if action == "check":

            if not values["full_name"]:

                flash(
                    "Please enter your full name.",
                    "danger"
                )

            else:

                saved = {
                    **values,
                    "status": check_identity(
                        values["full_name"],
                        values["nid"],
                        values["dob"]
                    )
                }

                session["identity"] = saved

        elif action == "next":

            if saved.get("status") and unchanged():

                return redirect(url_for(next_page))

            flash(
                "Please click “Check Identity” first.",
                "warning"
            )

    status = (
        saved.get("status")
        if unchanged()
        else None
    )

    return render_template(
        "identity.html",
        steps=steps,
        step=1,
        values=values,
        status=status
    )


@app.route("/profile")
@login_required
def profile():

    return render_template(
        "profile.html",
        identity=session.get("identity")
    )


# ============================ PROPERTY HELPERS ============================

def get_property(pid):

    for prop in load_json(PROPERTIES_FILE):

        if prop["id"] == pid:
            return prop

    return None


def save_property(prop):

    props = load_json(PROPERTIES_FILE)

    props = [
        prop if p["id"] == prop["id"] else p
        for p in props
    ]

    if not any(
        p["id"] == prop["id"]
        for p in props
    ):
        props.append(prop)

    save_json(PROPERTIES_FILE, props)


def current_property():
    """The property this Rentor is working on right now."""

    prop = get_property(session.get("property_id"))

    return (
        prop
        if prop and prop["owner"] == current_user.id
        else None
    )


def new_property():

    props = load_json(PROPERTIES_FILE)

    return {
        "id": max(
            [p["id"] for p in props] + [11574]
        ) + 1,

        "owner": current_user.id,
        "owner_name": current_user.name,
        "status": "draft",

        "photos": [],

        "documents": {
            key: None
            for key, _ in DOC_ROWS
        },

        "ownership": {
            "format": None,
            "name": "",
            "address": ""
        },

        "agreement": {
            "name": "",
            "address": "",
            "conditions": {
                c: "Missing"
                for c in documents.CLAUSES
            }
        },
    }


def extension(filename):

    return (
        filename.rsplit(".", 1)[-1].lower()
        if "." in filename
        else ""
    )


def save_upload(file, folder, allowed, prefix):
    """Save an uploaded file and return its path relative to /static."""

    if (
        not file
        or not file.filename
        or extension(file.filename) not in allowed
    ):
        return None

    name = (
        f"{prefix}_{uuid.uuid4().hex[:10]}_"
        f"{secure_filename(file.filename)}"
    )

    file.save(os.path.join(folder, name))

    return (
        "uploads/"
        + os.path.basename(folder)
        + "/"
        + name
    )


def remove_upload(relative_path):

    if relative_path:

        path = os.path.join(
            BASE_DIR,
            "static",
            relative_path
        )

        if os.path.exists(path):
            os.remove(path)


def to_number(text, whole=False):
    """Number from text, or None if empty/invalid/negative."""

    try:
        value = float(str(text).strip())

    except ValueError:
        return None

    if value < 0 or (
        whole and value != int(value)
    ):
        return None

    return int(value) if whole else value


def read_property_form(form):
    """Check the Step 2 form. Returns (data, error_message)."""

    data = {
        k: form.get(k, "").strip()
        for k in (
            "address",
            "landlord_name",
            "landlord_phone",
            "property_type",
            "other_charge_description"
        )
    }

    if not data["address"] or not data["landlord_name"]:
        return data, "Property address and landlord name are required."

    if data["property_type"] not in PROPERTY_TYPES:
        return data, "Please choose a property type."

    for key, label in (
        ("bedrooms", "Bedrooms"),
        ("washrooms", "Washrooms"),
        ("balconies", "Balconies")
    ):

        value = to_number(
            form.get(key, ""),
            whole=True
        )

        if value is None:
            return data, f"{label} must be a whole number (0 or more)."

        data[key] = value

    size = to_number(
        form.get("flat_size", "")
    )

    if size is None:
        return data, "Flat size must be a number (0 or more)."

    data["flat_size"] = size

    for key, label in (
        ("rent", "Rent"),
        ("deposit", "Deposit"),
        ("service_charge", "Service charge"),
        ("utility", "Utility"),
        ("other_charges", "Other charges")
    ):

        value = to_number(
            form.get(key, "") or "0"
        )

        if value is None:
            return data, f"{label} must be a number (0 or more)."

        data[key] = value

    if data["rent"] <= 0:
        return data, "Rent must be greater than 0."

    if data["other_charges"] == 0:
        data["other_charge_description"] = ""

    return data, None


def identity_done():

    return bool(
        session.get("identity", {}).get("status")
    )


# ============================ RENTOR: STEP 2 PROPERTY ============================

@app.route("/property", methods=["GET", "POST"])
@role_required("Rentor")
def rentor_property():

    if not identity_done():

        flash(
            "Please complete the identity check first.",
            "warning"
        )

        return redirect(url_for("identity"))

    prop = current_property()
    values = dict(prop) if prop else {}

    if request.method == "POST":

        data, error = read_property_form(request.form)

        if error:

            flash(error, "danger")

            values = {
                **values,
                **request.form.to_dict()
            }

        else:

            prop = prop or new_property()

            prop.update(data)

            prop["identity"] = {
                "full_name": session["identity"]["full_name"],
                "status": session["identity"]["status"]
            }

            for photo in request.files.getlist("photos"):

                if len(prop["photos"]) >= MAX_PHOTOS:

                    flash(
                        f"Only {MAX_PHOTOS} photos are kept for one property.",
                        "warning"
                    )

                    break

                if photo and photo.filename:

                    saved = save_upload(
                        photo,
                        FLAT_DIR,
                        IMAGE_EXT,
                        f"flat{prop['id']}"
                    )

                    if saved:
                        prop["photos"].append(saved)

                    else:
                        flash(
                            f"“{photo.filename}” was skipped. "
                            "Photos must be JPG, PNG or WEBP.",
                            "warning"
                        )

            save_property(prop)

            session["property_id"] = prop["id"]

            return redirect(url_for("rentor_documents"))

    return render_template(
        "form.html",
        steps=RENTOR_STEPS,
        step=2,
        v=values,
        types=PROPERTY_TYPES,
        photos=(prop or {}).get("photos", [])
    )


@app.route("/property/new")
@role_required("Rentor")
def rentor_property_new():

    session.pop("property_id", None)
    session.pop("crosscheck", None)

    flash(
        "You can enter a new property now.",
        "success"
    )

    return redirect(url_for("rentor_property"))


# ============================ RENTOR: STEP 3 DOCUMENTS ============================

def need_property():
    """Return a redirect if the Rentor has not saved Step 2 yet."""

    if not identity_done():

        flash(
            "Please complete the identity check first.",
            "warning"
        )

        return redirect(url_for("identity"))

    if not current_property():

        flash(
            "Please fill in the property information first.",
            "warning"
        )

        return redirect(url_for("rentor_property"))

    return None


@app.route("/documents")
@role_required("Rentor")
def rentor_documents():

    if (redirect_to := need_property()):
        return redirect_to

    prop = current_property()
    rows = []

    for key, label in DOC_ROWS:

        info = prop["documents"].get(key)

        rows.append({
            "key": key,
            "label": label,
            "have": bool(info),
            "file": info["file"] if info else None,
            "original": info["original"] if info else ""
        })

    return render_template(
        "checklist.html",
        steps=RENTOR_STEPS,
        step=3,
        rows=rows,
        agreement=prop["agreement"]
    )


@app.route("/documents/upload/<doc_key>", methods=["POST"])
@role_required("Rentor")
def upload_document(doc_key):

    if (redirect_to := need_property()):
        return redirect_to

    label = dict(DOC_ROWS).get(doc_key)

    if not label:

        flash("Unknown document.", "danger")

        return redirect(url_for("rentor_documents"))

    prop = current_property()
    file = request.files.get("file")

    if not file or not file.filename:
        return redirect(url_for("rentor_documents"))

    saved = save_upload(
        file,
        DOC_DIR,
        DOC_EXT,
        f"doc{prop['id']}_{doc_key}"
    )

    if not saved:

        flash(
            f"{label}: please upload a PDF, JPG or PNG file.",
            "danger"
        )

        return redirect(url_for("rentor_documents"))

    old = prop["documents"].get(doc_key)

    if old:
        remove_upload(old["file"])

    prop["documents"][doc_key] = {
        "file": saved,
        "original": file.filename
    }

    is_pdf = extension(saved) == "pdf"

    text = (
        documents.read_pdf_text(
            os.path.join(BASE_DIR, "static", saved)
        )
        if is_pdf
        else ""
    )

    if doc_key == "rental_agreement":

        if text:

            result = documents.parse_agreement(text)

            prop["agreement"] = {
                "name": result["name"],
                "address": result["address"],
                "conditions": result["conditions"]
            }

            flash(
                "Rental agreement uploaded. "
                "The agreement details were filled in automatically.",
                "success"
            )

        else:

            prop["agreement"] = {
                "name": "",
                "address": "",
                "conditions": {
                    c: "Unclear"
                    for c in documents.CLAUSES
                }
            }

            flash(
                "Rental agreement uploaded, but its text could not be read. "
                "Please upload a text-based PDF so the agreement details "
                "can be filled in.",
                "warning"
            )

    elif doc_key == "ownership_paper":

        if text:
            prop["ownership"] = documents.parse_ownership(text)

        else:
            prop["ownership"] = {
                "format": "Invalid Format",
                "name": "",
                "address": ""
            }

        flash(
            "Ownership paper uploaded.",
            "success"
        )

    else:

        flash(
            f"{label} uploaded.",
            "success"
        )

    save_property(prop)

    return redirect(url_for("rentor_documents"))


# ============================ RENTOR: STEP 4 CROSS-CHECK ============================

def build_crosscheck(prop):
    """Compare landlord entries with ownership paper and agreement."""

    own, agr = prop["ownership"], prop["agreement"]

    rows, problems = [], []

    for field, label, landlord, from_owner, from_agreement in (

        (
            "Name",
            "Landlord name",
            prop["landlord_name"],
            own.get("name", ""),
            agr.get("name", "")
        ),

        (
            "Address",
            "Property address",
            prop["address"],
            own.get("address", ""),
            agr.get("address", "")
        )

    ):

        cells = [
            {
                "text": landlord,
                "bad": False
            }
        ]

        for value, source in (
            (from_owner, "the ownership paper"),
            (from_agreement, "the agreement")
        ):

            bad = (
                bool(value)
                and not documents.same_text(landlord, value)
            )

            cells.append({
                "text": value or "—",
                "bad": bad
            })

            if bad:
                problems.append(
                    f"{label} does not match {source}."
                )

        rows.append({
            "field": field,
            "cells": cells
        })

    return rows, problems


@app.route("/cross-check")
@role_required("Rentor")
def rentor_crosscheck():

    if (redirect_to := need_property()):
        return redirect_to

    prop = current_property()

    rows, problems = build_crosscheck(prop)

    prop["crosscheck"] = {
        "has_mismatch": bool(problems),
        "problems": problems
    }

    save_property(prop)

    session["crosscheck"] = prop["crosscheck"]

    return render_template(
        "crosscheck.html",
        steps=RENTOR_STEPS,
        step=4,
        rows=rows,
        problems=problems
    )


# ============================ RENTOR: STEP 5 RISK ============================

def risk_level(score):

    if score <= 20:
        return "Low"

    if score <= 40:
        return "Medium"

    return "High"


def mismatch_items(problems):
    """Turn "Landlord name does not match the agreement." into ("Landlord name", "the agreement")."""

    items = []

    for text in problems:

        label, _, source = text.rstrip(".").partition(" does not match ")

        items.append((label, source))

    return items


def assess_risk(prop, identity_status):
    """
    Apply the prototype risk rules (Appendix C) to everything collected in Steps 1-4.

    Returns a dictionary with the score, the level, one card per issue
    and the facts the Report page needs.
    """

    _, problems = build_crosscheck(prop)
    mismatches = mismatch_items(problems)
    identity_bad = identity_status == "Needs Review"

    issues = []

    # Rule 1 (+20, counted once): a detail does not match another detail
    if mismatches or identity_bad:

        if len(mismatches) == 1 and not identity_bad:

            label, source = mismatches[0]

            title = f"{label} mismatch"
            advice = (
                f"Clarify the {label.lower()} with {source} "
                "to reduce risk by 20 points."
            )

        elif identity_bad and not mismatches:

            title = "Identity check needs review"
            advice = (
                "Re-check your full name, NID number and date of birth "
                "to reduce risk by 20 points."
            )

        else:

            parts = [
                f"{label.lower()} vs {source}"
                for label, source in mismatches
            ]

            if identity_bad:
                parts.append("the identity check result")

            title = "Details do not match"
            advice = (
                "Clarify: " + "; ".join(parts)
                + ". This reduces risk by 20 points."
            )

        issues.append({"title": title, "points": 20, "advice": advice})

    # Rule 2 (+20, counted once): important information missing or inconsistent
    phone_missing = not prop.get("landlord_phone")
    format_bad = prop["ownership"].get("format") == "Invalid Format"

    if phone_missing or format_bad:

        if phone_missing and not format_bad:

            title = "Landlord phone missing"
            advice = (
                "Add the landlord's phone number "
                "to reduce risk by 20 points."
            )

        elif format_bad and not phone_missing:

            title = "Ownership paper format invalid"
            advice = (
                "Upload the ownership paper with the lines Owner Name, "
                "Property Address, Deed Number and Registration Date "
                "to reduce risk by 20 points."
            )

        else:

            title = "Important information missing"
            advice = (
                "Add the landlord's phone number and upload the ownership "
                "paper in the correct format to reduce risk by 20 points."
            )

        issues.append({"title": title, "points": 20, "advice": advice})

    # Rule 3 (+10 each): a supporting document is missing
    missing_docs = [
        label
        for key, label in DOC_ROWS
        if not prop["documents"].get(key)
    ]

    for label in missing_docs:

        issues.append({
            "title": f"{label} missing",
            "points": 10,
            "advice": (
                f"Submit the {label.lower()} "
                "to reduce risk by 10 points."
            )
        })

    # Rule 4 (+10 each): a key rental condition is unclear or missing
    bad_conditions = [
        (name, state)
        for name, state in prop["agreement"]["conditions"].items()
        if state in ("Unclear", "Missing")
    ]

    for name, state in bad_conditions:

        issues.append({
            "title": f"{name} {state.lower()}",
            "points": 10,
            "advice": (
                f"Confirm the {name.lower()} in the rental agreement "
                "to reduce risk by 10 points."
            )
        })

    score = sum(issue["points"] for issue in issues)

    return {
        "score": score,
        "level": risk_level(score),
        "issues": issues,
        "problems": problems,
        "identity_bad": identity_bad,
        "phone_missing": phone_missing,
        "format_bad": format_bad,
        "missing_docs": missing_docs,
        "bad_conditions": [name for name, _ in bad_conditions]
    }


@app.route("/risk")
@role_required("Rentor")
def rentor_risk():

    if (redirect_to := need_property()):
        return redirect_to

    prop = current_property()

    result = assess_risk(prop, session["identity"]["status"])

    # The Report page uses this saved result so both pages always agree.
    session["risk"] = {
        "score": result["score"],
        "level": result["level"]
    }

    return render_template(
        "risk.html",
        steps=RENTOR_STEPS,
        step=5,
        risk=result,
        needle=LEVEL_ANGLE[result["level"]]
    )


# ============================ RENTOR: STEP 6 REPORT ============================

def build_summary(prop, identity_status, result):
    """The four status rows of the Summary card."""

    all_documents = not result["missing_docs"]

    all_terms = all(
        state == "Have"
        for state in prop["agreement"]["conditions"].values()
    )

    return [
        ("Identity", identity_status),

        (
            "Property info",
            "Clear"
            if prop["ownership"].get("format") == "Valid Format"
            else "Needs Review"
        ),

        (
            "Cross-check",
            "Issue" if result["problems"] else "Clear"
        ),

        (
            "Documents",
            "Clear" if all_documents and all_terms else "Missing"
        ),
    ]


def build_recommendations(result):
    """Short, specific action items for the Recommendations list."""

    recommendations = []

    if result["missing_docs"]:
        recommendations.append(
            "Missing documents: " + ", ".join(result["missing_docs"])
        )

    if result["bad_conditions"]:
        recommendations.append(
            "Unclear/missing terms: " + ", ".join(result["bad_conditions"])
        )

    for problem in result["problems"]:
        recommendations.append("Clarify mismatch: " + problem)

    if result["identity_bad"]:
        recommendations.append(
            "Identity check needs review: check your name, NID number and date of birth"
        )

    if result["phone_missing"]:
        recommendations.append("Add the landlord's phone number")

    if result["format_bad"]:
        recommendations.append("Ownership paper format needs review")

    if not recommendations:
        recommendations.append("All documents and details look clear.")

    return recommendations


def report_data():
    """
    Collect everything the report needs, or return a redirect.

    The risk result saved by the Risk page is shown as it is. If the data
    changed after that page was opened, the Rentor is sent back to it.
    """

    if (redirect_to := need_property()):
        return None, redirect_to

    prop = current_property()
    identity_status = session["identity"]["status"]

    result = assess_risk(prop, identity_status)
    saved_risk = session.get("risk")

    if not saved_risk or saved_risk["score"] != result["score"]:

        flash(
            "Please check the risk result before opening the report.",
            "warning"
        )

        return None, redirect(url_for("rentor_risk"))

    return {
        "prop": prop,
        "risk": saved_risk,
        "result": result,
        "summary": build_summary(prop, identity_status, result),
        "recommendations": build_recommendations(result)
    }, None


@app.route("/report")
@role_required("Rentor")
def rentor_report():

    data, redirect_to = report_data()

    if redirect_to:
        return redirect_to

    prop = data["prop"]

    # Save the finished report so Rentees can see this property in Homes.
    prop["status"] = "published"
    prop["identity_status"] = session["identity"]["status"]
    prop["risk"] = data["risk"]
    prop["summary"] = data["summary"]
    prop["recommendations"] = data["recommendations"]
    prop["published_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    save_property(prop)

    return render_template(
        "result.html",
        steps=RENTOR_STEPS,
        step=6,
        prop=prop,
        risk=data["risk"],
        summary=data["summary"],
        recommendations=data["recommendations"]
    )


@app.route("/report.pdf")
@role_required("Rentor")
def rentor_report_pdf():

    data, redirect_to = report_data()

    if redirect_to:
        return redirect_to

    prop = data["prop"]

    def clean(text):
        return str(text).encode("latin-1", "replace").decode("latin-1")

    pdf = FPDF()
    pdf.add_page()

    def line(text, size=11, bold=False, gap=6):

        pdf.set_font("Helvetica", "B" if bold else "", size)

        pdf.multi_cell(
            0, gap, clean(text),
            new_x="LMARGIN", new_y="NEXT"
        )

    line("RentCheck", 20, True, 10)
    line("Assessment report", 14, True, 8)
    line(prop["address"])
    line(f"Landlord: {prop['landlord_name']}")
    line(f"Prepared for: {prop['owner_name']}   Date: {datetime.now().strftime('%Y-%m-%d')}")
    line("")

    line("Summary", 13, True)

    for label, value in data["summary"]:
        line(f"- {label}: {value}")

    line("")

    line(
        f"Overall risk: {data['risk']['score']} points, {data['risk']['level']}",
        13, True
    )

    for issue in data["result"]["issues"]:
        line(f"- {issue['title']} (+{issue['points']}): {issue['advice']}")

    if not data["result"]["issues"]:
        line("- No risk issues were found.")

    line("")

    line("Recommendations", 13, True)

    for text in data["recommendations"]:
        line("- " + text)

    line("")

    line(
        "These are provisional prototype rules for guidance and not a "
        "scientifically validated fraud score. The result does not prove "
        "identity, document genuineness or legal ownership.",
        9
    )

    return Response(
        bytes(pdf.output()),
        mimetype="application/pdf",
        headers={
            "Content-Disposition":
            f"attachment; filename=RentCheck_Assessment_Report_{prop['id']}.pdf"
        }
    )


# ============================ RENTOR: TENANT REQUESTS ============================

@app.route("/tenant-requests")
@role_required("Rentor")
def tenant_requests():
    """Every Rentee who asked for an appointment on one of this Rentor's properties."""

    groups = []

    for item in load_json(APPOINTMENTS_FILE):

        if item.get("landlord_email") != current_user.id:
            continue

        for group in groups:

            if group["property_id"] == item["property_id"]:
                group["items"].append(item)
                break

        else:

            groups.append({
                "property_id": item["property_id"],
                "property_title": item["property_title"],
                "items": [item]
            })

    return render_template("tenant_requests.html", groups=groups)


@app.route("/tenant-report/<int:request_id>")
@role_required("Rentor")
def tenant_report(request_id):

    for item in load_json(APPOINTMENTS_FILE):

        if (
            item["request_id"] == request_id
            and item.get("landlord_email") == current_user.id
        ):
            return render_template("tenant_report.html", item=item)

    abort(404)


# ============================ RENTEE HELPERS ============================

def published_property(pid):
    """A property whose Rentor has finished the report. Only these are shown to Rentees."""

    prop = get_property(pid)

    if prop and prop.get("status") == "published":
        return prop

    return None


def property_area(prop):
    """The area name of a property, taken from its address."""

    address = prop["address"].lower()

    for area in AREAS:

        if area.lower() in address:
            return area

    return prop["address"].split(",")[0].strip()[:30]


def short_title(prop, dash=False):
    """For example "Mirpur 2 bed flat" (or "Mirpur 2-bed flat" when dash=True)."""

    beds = f"{prop['bedrooms']}-bed" if dash else f"{prop['bedrooms']} bed"

    return f"{property_area(prop)} {beds} {TYPE_WORD.get(prop['property_type'], 'home')}"


def risk_level_of(prop):
    """The risk level the Rentor saw in Step 5 (saved with the report)."""

    saved = prop.get("risk")

    if saved:
        return saved["level"]

    return assess_risk(prop, prop.get("identity_status", "Needs Review"))["level"]


def count_matches(value, wanted):
    """"Any" matches everything, "4+" means 4 or more, otherwise the number must be equal."""

    if wanted in ("", "Any"):
        return True

    if wanted.endswith("+"):
        return value >= int(wanted[:-1])

    return value == int(wanted)


def matches_preferences(prop, prefs):

    if prefs["area"] != "Any" and prefs["area"].lower() not in prop["address"].lower():
        return False

    if not count_matches(prop["bedrooms"], prefs["bedrooms"]):
        return False

    if not count_matches(prop["washrooms"], prefs["bathrooms"]):
        return False

    if prefs["property_type"] != "Any" and prop["property_type"] != prefs["property_type"]:
        return False

    if prefs["min_budget"] is not None and prop["rent"] < prefs["min_budget"]:
        return False

    if prefs["max_budget"] is not None and prop["rent"] > prefs["max_budget"]:
        return False

    return True


def page_numbers(current, total):
    """Page buttons such as 1 2 3 ... 10. None means "..."."""

    if total <= 7:
        return list(range(1, total + 1))

    wanted = sorted(
        n for n in {1, total, *range(current - 2, current + 3)}
        if 1 <= n <= total
    )

    pages = []
    previous = 0

    for number in wanted:

        if number - previous > 1:
            pages.append(None)

        pages.append(number)
        previous = number

    return pages


def monthly_total(prop):

    return (
        prop["rent"]
        + prop["service_charge"]
        + prop["utility"]
        + prop["other_charges"]
    )


def initial_total(prop):
    """First month's total bill plus the security deposit."""

    return monthly_total(prop) + prop["deposit"]


def rentee_ready(need_preferences=False):
    """Return a redirect if the Rentee skipped a step, otherwise None."""

    if not identity_done():

        flash(
            "Please complete the identity check first.",
            "warning"
        )

        return redirect(url_for("identity"))

    if need_preferences and not session.get("preferences"):

        flash(
            "Please choose your preferences first.",
            "warning"
        )

        return redirect(url_for("rentee_preferences"))

    return None


# ============================ RENTEE: STEP 2 PREFERENCES ============================

@app.route("/preferences", methods=["GET", "POST"])
@role_required("Rentee")
def rentee_preferences():

    if (redirect_to := rentee_ready()):
        return redirect_to

    values = session.get("preferences", {})

    if request.method == "POST":

        values = {
            "area": request.form.get("area", "Any"),
            "bedrooms": request.form.get("bedrooms", "Any"),
            "bathrooms": request.form.get("bathrooms", "Any"),
            "property_type": request.form.get("property_type", "Any"),
            "min_budget": request.form.get("min_budget", "").strip(),
            "max_budget": request.form.get("max_budget", "").strip()
        }

        low = to_number(values["min_budget"]) if values["min_budget"] else None
        high = to_number(values["max_budget"]) if values["max_budget"] else None

        if values["area"] not in ["Any"] + AREAS:

            flash("Please choose an area from the list.", "danger")

        elif (
            values["bedrooms"] not in BEDROOM_OPTIONS
            or values["bathrooms"] not in BATHROOM_OPTIONS
            or values["property_type"] not in ["Any"] + PROPERTY_TYPES
        ):

            flash("Please choose from the lists.", "danger")

        elif (values["min_budget"] and low is None) or (values["max_budget"] and high is None):

            flash("Budget must be a number (0 or more).", "danger")

        elif low is not None and high is not None and low > high:

            flash(
                "Min budget cannot be more than Max budget.",
                "danger"
            )

        else:

            session["preferences"] = {
                **values,
                "min_budget": low,
                "max_budget": high
            }

            return redirect(url_for("rentee_homes"))

    return render_template(
        "preferences.html",
        steps=RENTEE_STEPS,
        step=2,
        v=values,
        areas=AREAS,
        bedroom_options=BEDROOM_OPTIONS,
        bathroom_options=BATHROOM_OPTIONS,
        types=PROPERTY_TYPES
    )


# ============================ RENTEE: STEP 3 HOMES ============================

@app.route("/homes")
@role_required("Rentee")
def rentee_homes():

    if (redirect_to := rentee_ready(need_preferences=True)):
        return redirect_to

    prefs = session["preferences"]

    matching = [
        prop
        for prop in load_json(PROPERTIES_FILE)
        if prop.get("status") == "published" and matches_preferences(prop, prefs)
    ]

    matching.sort(key=lambda prop: prop["id"], reverse=True)  # newest first

    requested = {
        item["property_id"]
        for item in load_json(APPOINTMENTS_FILE)
        if item.get("tenant_email") == current_user.id
    }

    pages = max(1, -(-len(matching) // HOMES_PER_PAGE))
    page = min(max(request.args.get("page", 1, type=int), 1), pages)

    first = (page - 1) * HOMES_PER_PAGE

    cards = [
        {
            "id": prop["id"],
            "title": short_title(prop),
            "rent": prop["rent"],
            "photo": prop["photos"][0] if prop.get("photos") else None,
            "badge": "Verified" if risk_level_of(prop) == "Low" else "Needs Review",
            "requested": prop["id"] in requested
        }
        for prop in matching[first:first + HOMES_PER_PAGE]
    ]

    return render_template(
        "homes.html",
        steps=RENTEE_STEPS,
        step=3,
        cards=cards,
        total=len(matching),
        page=page,
        pages=pages,
        numbers=page_numbers(page, pages)
    )


@app.route("/request-appointment/<int:property_id>", methods=["POST"])
@role_required("Rentee")
def request_appointment(property_id):
    """Save the Rentee's identity details and the chosen home so the Rentor sees them on Tenant requests."""

    page = request.form.get("page", 1, type=int)

    if (redirect_to := rentee_ready(need_preferences=True)):
        return redirect_to

    prop = published_property(property_id)

    if not prop:

        flash("That home is not available.", "warning")

        return redirect(url_for("rentee_homes"))

    appointments = load_json(APPOINTMENTS_FILE)

    already = any(
        item["property_id"] == property_id
        and item.get("tenant_email") == current_user.id
        for item in appointments
    )

    if already:

        flash(
            "You have already asked for an appointment for this home.",
            "warning"
        )

    else:

        person = session["identity"]

        appointments.append({
            "request_id": max([item["request_id"] for item in appointments] + [0]) + 1,
            "property_id": property_id,
            "property_title": short_title(prop),
            "landlord_email": prop["owner"],
            "tenant_name": person["full_name"],
            "tenant_email": current_user.id,
            "nid_provided": "Yes" if person.get("nid") else "No",
            "phone_provided": "Yes" if person.get("phone") else "No",
            "identity_status": person["status"],
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M")
        })

        save_json(APPOINTMENTS_FILE, appointments)

        flash("Appointment request sent to the landlord!", "success")

    return redirect(url_for("rentee_homes", page=page))


# ============================ RENTEE: STEP 4 PROPERTY CHECK ============================

@app.route("/property-check/<int:property_id>")
@role_required("Rentee")
def rentee_property_check(property_id):

    if (redirect_to := rentee_ready()):
        return redirect_to

    prop = published_property(property_id)

    if not prop:

        flash("That home is not available.", "warning")

        return redirect(url_for("rentee_homes"))

    rows = []

    for key, label in DOC_ROWS:

        info = prop["documents"].get(key)

        rows.append({
            "label": label,
            "have": bool(info),
            "file": info["file"] if info else None
        })

    return render_template(
        "property_check.html",
        steps=RENTEE_STEPS,
        step=4,
        prop=prop,
        heading=short_title(prop, dash=True),
        rows=rows,
        agreement=prop["agreement"],
        level=risk_level_of(prop)
    )


# ============================ RENTEE: STEP 5 RENT REPORT ============================

@app.route("/rent-report/<int:property_id>")
@role_required("Rentee")
def rentee_rent_report(property_id):

    if (redirect_to := rentee_ready()):
        return redirect_to

    prop = published_property(property_id)

    if not prop:

        flash("That home is not available.", "warning")

        return redirect(url_for("rentee_homes"))

    return render_template(
        "rent_report.html",
        steps=RENTEE_STEPS,
        step=5,
        prop=prop,
        monthly=monthly_total(prop),
        initial=initial_total(prop)
    )


@app.route("/rent-report/<int:property_id>/download-pdf")
@role_required("Rentee")
def rentee_rent_report_pdf(property_id):

    if (redirect_to := rentee_ready()):
        return redirect_to

    prop = published_property(property_id)

    if not prop:

        flash("That home is not available.", "warning")

        return redirect(url_for("rentee_homes"))

    def clean(text):
        return str(text).encode("latin-1", "replace").decode("latin-1")

    def money_text(value):
        return "Tk {:,.0f}".format(value)

    pdf = FPDF()
    pdf.add_page()

    def line(text, size=11, bold=False, gap=7):

        pdf.set_font("Helvetica", "B" if bold else "", size)

        pdf.multi_cell(
            0, gap, clean(text),
            new_x="LMARGIN", new_y="NEXT"
        )

    other_label = "Other charges"

    if prop.get("other_charge_description"):
        other_label += f" ({prop['other_charge_description']})"

    line("RentCheck", 20, True, 10)
    line("Rent report", 14, True, 8)
    line(f"Property address: {prop['address']}")
    line(f"Landlord: {prop['landlord_name']}")
    line(f"Tenant: {session['identity']['full_name']}")
    line(f"Date: {datetime.now().strftime('%Y-%m-%d')}")
    line("")

    line("Monthly cost", 13, True)
    line(f"Rent: {money_text(prop['rent'])}")
    line(f"Service charge: {money_text(prop['service_charge'])}")
    line(f"Utility: {money_text(prop['utility'])}")
    line(f"{other_label}: {money_text(prop['other_charges'])}")
    line(f"Total: {money_text(monthly_total(prop))}", bold=True)
    line("")

    line("Initial cost", 13, True)
    line(f"First month: {money_text(monthly_total(prop))}")
    line(f"Deposit: {money_text(prop['deposit'])}")
    line(f"Total: {money_text(initial_total(prop))}", bold=True)
    line("")

    line(
        "These figures come from the landlord's entries. Please confirm all "
        "amounts with the landlord before signing an agreement.",
        9
    )

    return Response(
        bytes(pdf.output()),
        mimetype="application/pdf",
        headers={
            "Content-Disposition":
            "attachment; filename=RentCheck_Cost_Report.pdf"
        }
    )


# ============================ ERROR HANDLERS ============================

@app.errorhandler(404)
def not_found(error):

    return render_template(
        "error.html",
        message="Page not found."
    ), 404


@app.errorhandler(413)
def too_large(error):

    flash(
        "The upload is too large. The total size limit is 16 MB.",
        "danger"
    )

    return redirect(
        request.referrer or url_for("identity")
    )


@app.errorhandler(403)
def forbidden(error):

    return render_template(
        "error.html",
        message="You do not have permission to open this page."
    ), 403


# ============================ RUN APPLICATION ============================

if __name__ == "__main__":

    setup_data_files()

    app.run(debug=True)
