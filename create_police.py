import os
import sqlite3
import getpass
from werkzeug.security import generate_password_hash

db_path = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(os.path.abspath(__file__)), "cybercrime.db"))
if not os.path.exists(db_path):
    print("Database not found. Run python app.py once, then run this script.")
    raise SystemExit(1)

name = input("Officer name: ").strip()
email = input("Officer email: ").strip().lower()
badge = input("Badge ID: ").strip()
password = getpass.getpass("Temporary password (at least 12 characters): ")

if not name or "@" not in email or not badge or len(password) < 12:
    print("Invalid details. Check the name, email, badge ID and password length.")
    raise SystemExit(1)

database = sqlite3.connect(db_path)
try:
    database.execute(
        "INSERT INTO users(name,email,password,role,badge) VALUES(?,?,?,?,?)",
        (name, email, generate_password_hash(password), "police", badge)
    )
    database.commit()
    print("Police account created successfully.")
except sqlite3.IntegrityError:
    print("This email already exists. Use that account or choose another email.")
finally:
    database.close()
