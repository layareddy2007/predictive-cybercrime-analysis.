import os
import sqlite3
import datetime
from functools import wraps

import jwt
from flask import Flask, request, jsonify, g
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

ROOT = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("DATABASE_PATH", os.path.join(ROOT, "cybercrime.db"))
SECRET = os.environ.get("JWT_SECRET", "CHANGE-THIS-DEMO-SECRET-BEFORE-DEPLOYMENT")

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})

def conn():
    if "db" not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(_error):
    database = g.pop("db", None)
    if database is not None:
        database.close()

def init_db():
    database = sqlite3.connect(DB)
    database.execute("PRAGMA foreign_keys = ON")
    database.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('public','police')),
        badge TEXT
    );
    CREATE TABLE IF NOT EXISTS complaints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        description TEXT NOT NULL,
        city TEXT NOT NULL,
        area TEXT NOT NULL,
        amount REAL NOT NULL DEFAULT 0,
        incident_date TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Submitted',
        risk INTEGER NOT NULL DEFAULT 25,
        predicted_area TEXT,
        predicted_lat REAL,
        predicted_lng REAL,
        prediction_confidence INTEGER,
        created TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    """)
    # Safe schema migration for an existing local demo database.
    existing = {row[1] for row in database.execute("PRAGMA table_info(complaints)")}
    for column, definition in [
        ("predicted_area", "TEXT"),
        ("predicted_lat", "REAL"),
        ("predicted_lng", "REAL"),
        ("prediction_confidence", "INTEGER")
    ]:
        if column not in existing:
            database.execute(f"ALTER TABLE complaints ADD COLUMN {column} {definition}")

    # Synthetic records for demonstration only; inserted only once.
    count = database.execute("SELECT COUNT(*) FROM complaints").fetchone()[0]
    if count == 0:
        row = database.execute(
            "SELECT id FROM users WHERE email=?",
            ("citizen.demo@example.test",)
        ).fetchone()
        if row:
            user_id = row[0]
        else:
            cur = database.execute(
                "INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",
                ("Demo Citizen", "citizen.demo@example.test",
                 generate_password_hash("DemoPublic123!"), "public")
            )
            user_id = cur.lastrowid
        demo_rows = [
            ("UPI fraud", "Synthetic demo complaint", "Hyderabad", "Madhapur",
             12000, "2026-11-02", "Under Review", 78),
            ("Investment scam", "Synthetic demo complaint", "Hyderabad",
             "Kukatpally", 45000, "2026-11-04", "Submitted", 64),
            ("Phishing", "Synthetic demo complaint", "Hyderabad", "Ameerpet",
             3500, "2026-11-06", "Submitted", 42)
        ]
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        for item in demo_rows:
            database.execute("""
                INSERT INTO complaints
                (user_id,category,description,city,area,amount,incident_date,
                 status,risk,created)
                VALUES(?,?,?,?,?,?,?,?,?,?)
            """, (user_id, *item, now))
    database.commit()
    database.close()

def make_token(user):
    # PyJWT 2.10+ requires the JWT "sub" claim to be a string.
    payload = {
        "sub": str(user["id"]),
        "role": user["role"],
        "exp": datetime.datetime.now(datetime.timezone.utc)
               + datetime.timedelta(hours=6)
    }
    return jwt.encode(payload, SECRET, algorithm="HS256")

def require(role=None):
    def decorator(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return jsonify(error="Login required. Please sign in again."), 401
            raw_token = header[len("Bearer "):].strip()
            try:
                payload = jwt.decode(raw_token, SECRET, algorithms=["HS256"])
                user_id = int(payload["sub"])
                user = conn().execute(
                    "SELECT id,name,email,role,badge FROM users WHERE id=?",
                    (user_id,)
                ).fetchone()
                if not user or user["role"] != payload.get("role"):
                    raise ValueError("Invalid account")
            except (jwt.InvalidTokenError, ValueError, KeyError, TypeError):
                return jsonify(error="Login required. Your session may have expired; please sign in again."), 401

            if role and user["role"] != role:
                return jsonify(error="This account is not authorized for this page."), 403

            g.user = user
            return function(*args, **kwargs)
        return wrapped
    return decorator

# Initialize the database on the first request. This also works under Gunicorn.
_db_ready = False

@app.before_request
def ensure_database():
    global _db_ready
    if not _db_ready:
        os.makedirs(os.path.dirname(DB) or ".", exist_ok=True)
        init_db()
        _db_ready = True

# Serve the compiled React application from the same public Render service.
FRONTEND_DIST = os.path.abspath(os.path.join(ROOT, "..", "frontend", "dist"))

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_frontend(path):
    from flask import send_from_directory
    if path.startswith("api/"):
        return jsonify(error="Not found"), 404
    requested = os.path.abspath(os.path.join(FRONTEND_DIST, path))
    if path and requested.startswith(FRONTEND_DIST + os.sep) and os.path.isfile(requested):
        return send_from_directory(FRONTEND_DIST, path)
    index_file = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.isfile(index_file):
        return send_from_directory(FRONTEND_DIST, "index.html")
    return "Frontend build not found. Check the Render build command.", 503

@app.get("/api/health")
def health():
    return jsonify(status="ok", message="Cybercrime API is running")

@app.post("/api/register")
def register():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if not name or "@" not in email or len(password) < 8:
        return jsonify(error="Enter your name, a valid email and a password of at least 8 characters."), 400

    try:
        cur = conn().execute(
            "INSERT INTO users(name,email,password,role) VALUES(?,?,?,?)",
            (name, email, generate_password_hash(password), "public")
        )
        conn().commit()
        user = conn().execute(
            "SELECT id,name,email,role,badge FROM users WHERE id=?",
            (cur.lastrowid,)
        ).fetchone()
        return jsonify(token=make_token(dict(user)), user=dict(user)), 201
    except sqlite3.IntegrityError:
        return jsonify(error="This email is already registered. Please log in."), 409

@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    role = data.get("role")
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if role not in ("public", "police"):
        return jsonify(error="Select Public or Police."), 400

    user = conn().execute(
        "SELECT * FROM users WHERE email=?", (email,)
    ).fetchone()

    if (not user or user["role"] != role or
            not check_password_hash(user["password"], password)):
        return jsonify(error="Invalid email, password or account type."), 401

    safe_user = {
        "id": user["id"], "name": user["name"], "email": user["email"],
        "role": user["role"], "badge": user["badge"]
    }
    return jsonify(token=make_token(safe_user), user=safe_user)

# Approximate locality centroids for an educational map demo.
# These are broad area markers, NOT a person's live or verified location.
HOTSPOTS = {
    "madhapur": ("Madhapur (candidate cash-out area)", 17.4483, 78.3915),
    "kukatpally": ("Kukatpally (candidate cash-out area)", 17.4849, 78.4138),
    "ameerpet": ("Ameerpet (candidate cash-out area)", 17.4375, 78.4483),
    "secunderabad": ("Secunderabad (candidate cash-out area)", 17.4399, 78.4983),
    "gachibowli": ("Gachibowli (candidate cash-out area)", 17.4401, 78.3489),
    "lb nagar": ("LB Nagar (candidate cash-out area)", 17.3457, 78.5522),
    "dilsukhnagar": ("Dilsukhnagar (candidate cash-out area)", 17.3687, 78.5247),
    "hitech city": ("HITEC City (candidate cash-out area)", 17.4435, 78.3772),
}

def predict_demo_cashout(city, area, category, amount):
    """Transparent demo heuristic: maps the reported locality to a broad candidate area.
    It does not track or identify a suspect and is not a validated ML prediction.
    """
    key = str(area or "").strip().lower()
    if key in HOTSPOTS:
        label, lat, lng = HOTSPOTS[key]
        confidence = 55
    else:
        # Use a broad Hyderabad city-center marker when the locality is unknown.
        label, lat, lng = ("Hyderabad (unverified candidate area)", 17.3850, 78.4867)
        confidence = 25
    if category in ("UPI fraud", "Bank transfer fraud", "Investment scam"):
        confidence += 5
    if float(amount or 0) >= 50000:
        confidence += 5
    return label, lat, lng, min(confidence, 65)

def calculate_demo_risk(category, amount):
    # Illustrative demo score only; not a trained or validated prediction model.
    base = 25
    if category in ("UPI fraud", "Bank transfer fraud", "Investment scam"):
        base += 25
    if amount >= 50000:
        base += 25
    elif amount >= 10000:
        base += 15
    elif amount > 0:
        base += 5
    return min(95, base)

@app.post("/api/complaints")
@require("public")
def create_complaint():
    data = request.get_json(silent=True) or {}
    required_fields = ("category", "description", "city", "area", "incident_date")
    if any(not str(data.get(field, "")).strip() for field in required_fields):
        return jsonify(error="Please complete all required complaint fields."), 400
    if len(str(data["description"]).strip()) < 15:
        return jsonify(error="Please describe the incident in at least 15 characters."), 400
    try:
        amount = float(data.get("amount") or 0)
        if amount < 0:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify(error="Amount must be zero or a positive number."), 400

    risk = calculate_demo_risk(data["category"], amount)
    predicted_area, predicted_lat, predicted_lng, confidence = predict_demo_cashout(
        data["city"], data["area"], data["category"], amount
    )
    cursor = conn().execute("""
        INSERT INTO complaints
        (user_id,category,description,city,area,amount,incident_date,
         status,risk,predicted_area,predicted_lat,predicted_lng,
         prediction_confidence,created)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        g.user["id"], str(data["category"]).strip(),
        str(data["description"]).strip(), str(data["city"]).strip(),
        str(data["area"]).strip(), amount, str(data["incident_date"]),
        "Submitted", risk, predicted_area, predicted_lat, predicted_lng,
        confidence, datetime.datetime.now(datetime.timezone.utc).isoformat()
    ))
    conn().commit()
    return jsonify(message="Complaint submitted successfully",
                   complaint_id=cursor.lastrowid), 201

@app.get("/api/my-complaints")
@require("public")
def my_complaints():
    rows = conn().execute("""
        SELECT id,category,city,area,incident_date,status
        FROM complaints WHERE user_id=? ORDER BY id DESC
    """, (g.user["id"],)).fetchall()
    return jsonify(complaints=[dict(row) for row in rows])

@app.get("/api/public/risk-areas")
@require("public")
def public_risk_areas():
    rows = conn().execute("""
        SELECT city,area,COUNT(*) AS complaints,
        CASE WHEN AVG(risk)>=70 THEN 'High'
             WHEN AVG(risk)>=45 THEN 'Medium' ELSE 'Low' END AS risk_level
        FROM complaints GROUP BY city,area
    """).fetchall()
    return jsonify(risk_areas=[dict(row) for row in rows])

@app.get("/api/police/dashboard")
@require("police")
def police_dashboard():
    metrics = conn().execute("""
        SELECT COUNT(*) AS total,
        SUM(CASE WHEN status='Submitted' THEN 1 ELSE 0 END) AS submitted,
        COALESCE(SUM(amount),0) AS reported_amount
        FROM complaints
    """).fetchone()
    areas = conn().execute("""
        SELECT city,area,COUNT(*) AS complaints,
        ROUND(AVG(risk)) AS risk_score,
        COALESCE(SUM(amount),0) AS reported_amount
        FROM complaints GROUP BY city,area ORDER BY risk_score DESC
    """).fetchall()
    return jsonify(
        metrics={key: (metrics[key] or 0) for key in metrics.keys()},
        risk_areas=[dict(row) for row in areas]
    )

@app.get("/api/police/complaints")
@require("police")
def police_complaints():
    rows = conn().execute("""
        SELECT c.id,c.category,c.description,c.city,c.area,c.amount,
        c.incident_date,c.status,c.risk,c.predicted_area,c.predicted_lat,
        c.predicted_lng,c.prediction_confidence,u.name AS reporter_name,
        u.email AS reporter_email
        FROM complaints c JOIN users u ON c.user_id=u.id
        ORDER BY c.id DESC
    """).fetchall()
    return jsonify(complaints=[dict(row) for row in rows])

@app.get("/api/police/predictions")
@require("police")
def police_predictions():
    rows = conn().execute("""
        SELECT id,city,area,category,predicted_area,predicted_lat,
               predicted_lng,prediction_confidence,risk,status
        FROM complaints
        WHERE predicted_lat IS NOT NULL AND predicted_lng IS NOT NULL
        ORDER BY id DESC
    """).fetchall()
    return jsonify(predictions=[dict(row) for row in rows])

@app.patch("/api/police/complaints/<int:complaint_id>")
@require("police")
def update_complaint(complaint_id):
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    allowed = ("Submitted", "Under Review", "Resolved", "Closed")
    if status not in allowed:
        return jsonify(error="Invalid complaint status."), 400
    cursor = conn().execute(
        "UPDATE complaints SET status=? WHERE id=?",
        (status, complaint_id)
    )
    conn().commit()
    if cursor.rowcount == 0:
        return jsonify(error="Complaint not found."), 404
    return jsonify(message="Complaint status updated.")

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=False)
