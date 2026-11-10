# Deploy to Render (single public URL)

This deployment serves the React frontend and Flask API from one Render web service. The included Render Blueprint configures a persistent disk for the SQLite database. The persistent disk requires a paid Render service plan.

## Steps
1. Push the contents of this folder to a new GitHub repository (the files `backend/`, `frontend/`, and `render.yaml` must be at the repository root).
2. In Render, choose **New + → Blueprint** and connect that GitHub repository.
3. Review the service named `predictive-cybercrime-analysis` and approve creation. Render reads `render.yaml`, builds React, and starts Flask with Gunicorn.
4. Wait for the deployment to finish. Open the `onrender.com` URL shown by Render. Check `/api/health`; it should return status `ok`.
5. Create a police account from the Render service Shell. Run:
   `python backend/create_police.py`
   Use a demo-only email and a unique temporary password.
6. Test public registration and complaint submission, then sign in to the police portal and open **All Complaints → View prediction** for that exact complaint.

## Important
- Do not upload real victim names, phone numbers, account numbers, bank details, or real complaint records. Use synthetic demo data only.
- The map displays an illustrative candidate locality, not a live suspect location. The confidence score is not a validated probability.
- The persistent disk in this Blueprint is paid. A free ephemeral filesystem can lose SQLite data on restart/redeploy.
- Keep `JWT_SECRET` private. Render generates it from the Blueprint. Never commit `.env`, database files, passwords, or real user data.
- This prototype has not had a professional security review and is not suitable for real police/citizen case handling.
