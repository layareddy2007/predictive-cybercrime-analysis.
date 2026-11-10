# Predictive Cybercrime Analysis — Dual Portal Demo

This is a local educational prototype with separate Public and Police portals.

## Important correction
The backend now stores the JWT `sub` claim as a string. PyJWT 2.10+ requires this. The previous numeric subject caused valid login tokens to be rejected by protected endpoints, which led to `Login required` during complaint submission and dashboard loading.

## Police prediction map
The police Overview and Risk analysis pages include an OpenStreetMap-based map with broad candidate cash-out hotspot markers. In **All complaints**, every row has a **View prediction** action. Selecting it opens that specific complaint's details and a map centered on that complaint's stored candidate area. This is an individual complaint view, not just a general hotspot map.

This is a transparent educational heuristic using a small set of illustrative Hyderabad locality coordinates. It does **not** locate a suspect, access ATM/bank data, or produce a validated probability. Do not present it as a real-world prediction model.

## Requirements
- Python 3.10+
- Node.js and npm
- VS Code (recommended)

## 1. Start backend
Open a terminal in the project folder:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

If PowerShell blocks activation, use Command Prompt and run `venv\Scripts\activate.bat`. Keep this terminal open.

Check in your browser: `http://127.0.0.1:5000/api/health`

Expected JSON: `{"message":"Cybercrime API is running","status":"ok"}`

## 2. Create a police demo account
Open a second terminal:

```powershell
cd backend
python create_police.py
```

Enter an officer name, email, badge ID, and a unique temporary password of at least 12 characters. The password is hidden while typing; that is normal. Do not use a real personal password.

## 3. Start frontend
Open a third terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:5173` (or the exact URL Vite prints).

## 4. Test
- Public: create a public account, log in, submit a synthetic complaint, and open My complaints.
- Police: choose Police, log in with the account created above, open All complaints, click **View prediction** for each complaint to see its individual candidate-area map, and update a demo status.
- My Account shows the account details returned by the login API.

## If you already have an old database
The corrected backend can use the existing `backend/cybercrime.db`. The token fix does not require deleting it. After replacing the code, stop and restart Flask, then log in again. If a stale browser token remains, use Logout first or clear site data for the local app and sign in again.

## Demo limitations and safety
- Risk values are illustrative rules, not a trained or validated predictive model.
- Included complaint rows are synthetic examples.
- This is not connected to bank systems, NCRP/I4C, ATM feeds, or live police systems.
- Do not enter real victim information or real banking details.
- Public risk information is aggregated; detailed complaint records are restricted to the police role by backend checks.
- Before any real deployment, obtain authorization and a professional security review. Configure a strong secret through `JWT_SECRET`, HTTPS, secure session/token handling, rate limiting, audit logging, data encryption, access reviews, and retention policies.

## Public deployment
See `DEPLOY_RENDER.md` for deployment to Render as one public website and API. The `render.yaml` blueprint uses a persistent disk (paid plan) so demo complaints and accounts survive restarts.
