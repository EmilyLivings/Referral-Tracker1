from pathlib import Path
import os
import csv
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session

BASE_DIR = Path(__file__).resolve().parent
CSV_FILE = BASE_DIR / "referrals.csv"

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret")  # set SECRET_KEY in Render

@app.route("/")
def index():
    return render_template("index.html")

# Example: simple dashboard that reads the CSV (adjust to your template/columns)
@app.route("/dashboard")
def dashboard():
    rows = []
    if CSV_FILE.exists():
        with CSV_FILE.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    return render_template("dashboard.html", rows=rows)

# Only for local dev; Render uses Gunicorn via Procfile
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)



FIELDNAMES = [
    'candidate_name',
    'referrer_name',
    'role',
    'location',
    'applied_in_ukg',  # ✅ this replaces date_applied
    'submission_date',
    'date_applied',
    'start_date',
    'notes',
    'status',
    'bonus_30_paid',
    'bonus_90_paid'
]


@app.route('/submit', methods=['POST'])
def submit():
    data = request.form.to_dict()

    # Fill in missing fields
    for field in FIELDNAMES:
        if field not in data:
            data[field] = ""

    data['submission_date'] = datetime.today().strftime('%Y-%m-%d')
    data['status'] = 'Submitted'
    data['bonus_30_paid'] = 'No'
    data['bonus_90_paid'] = 'No'
    data['start_date'] = ""

    try:
        with open(CSV_FILE, 'x', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
    except FileExistsError:
        pass

    with open(CSV_FILE, 'a', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writerow(data)

    return render_template('thankyou.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['username'] == 'recruiter' and request.form[
                'password'] == 'password123':
            session['logged_in'] = True
            return redirect('/dashboard')
        else:
            error = 'Invalid credentials'
    return render_template('login.html', error=error)


@app.route('/dashboard', methods=['GET'])
def dashboard():
    if not session.get('logged_in'):
        return redirect('/login')

    sort_by = request.args.get('sort_by', '')
    search_query = request.args.get('search', '').lower()
    location_filter = request.args.get('location', '').lower()
    role_filter = request.args.get('role', '').lower()
    applied_after = request.args.get('applied_after', '')
    start_before = request.args.get('start_before', '')
    candidate_filter = request.args.get('candidate_filter', '').lower()
    referrer_filter = request.args.get('referrer_filter', '').lower()
    status_filter = request.args.get('status_filter', '').lower()

    referrals = []

    with open(CSV_FILE, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Filtering logic
            if location_filter and location_filter not in row['location'].lower():
                continue
            if role_filter and role_filter not in row['role'].lower():
                continue
            if candidate_filter and candidate_filter not in row['candidate_name'].lower():
                continue
            if referrer_filter and referrer_filter not in row['referrer_name'].lower():
                continue
            if status_filter and row['status'].lower() != status_filter:
                continue
            if applied_after and row.get('submission_date') and row['submission_date'] < applied_after:
                continue
            if start_before and row.get('start_date') and row['start_date'] > start_before:
                continue

            referrals.append(row)

    if sort_by and referrals and sort_by in referrals[0]:
        referrals = sorted(referrals, key=lambda x: x[sort_by])

    return render_template(
        'dashboard.html',
        referrals=referrals,
        search=search_query,
        location=location_filter,
        role=role_filter,
        applied_after=applied_after,
        start_before=start_before,
        candidate_filter=candidate_filter,
        referrer_filter=referrer_filter,
        status_filter=status_filter
    )




@app.route('/export', methods=['GET'])
def export():
    if not session.get('logged_in'):
        return redirect('/login')

    # Same filter logic
    search_query = request.args.get('search', '').lower()
    location_filter = request.args.get('location', '').lower()
    role_filter = request.args.get('role', '').lower()
    applied_after = request.args.get('applied_after', '')
    start_before = request.args.get('start_before', '')

    filtered = []

    with open(CSV_FILE, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_location = row.get('location', '').lower()
            row_role = row.get('role', '').lower()
            row_applied = row.get('date_applied', '')
            row_start = row.get('start_date', '')

            match_search = search_query in row['candidate_name'].lower() or search_query in row['referrer_name'].lower()
            match_location = location_filter in row_location if location_filter else True
            match_role = role_filter in row_role if role_filter else True

            match_applied = True
            if applied_after and row_applied:
                try:
                    match_applied = datetime.strptime(row_applied, "%Y-%m-%d") >= datetime.strptime(applied_after, "%Y-%m-%d")
                except:
                    match_applied = False

            match_start = True
            if start_before and row_start:
                try:
                    match_start = datetime.strptime(row_start, "%Y-%m-%d") <= datetime.strptime(start_before, "%Y-%m-%d")
                except:
                    match_start = False

            if match_search and match_location and match_role and match_applied and match_start:
                filtered.append(row)

    # Create CSV response
    def generate():
        fieldnames = filtered[0].keys() if filtered else []
        output = csv.DictWriter(open('filtered_output.csv', 'w', newline=''), fieldnames=fieldnames)
        output.writeheader()
        output.writerows(filtered)

        with open('filtered_output.csv', 'r') as file:
            for line in file:
                yield line

    return app.response_class(generate(), mimetype='text/csv', headers={"Content-Disposition": "attachment; filename=referrals_export.csv"})


@app.route('/lookup', methods=['GET', 'POST'])
def lookup():
    results = []
    if request.method == 'POST':
        name_input = request.form['referrer_name'].strip().lower()

        with open(CSV_FILE, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                referrer_name = row.get('referrer_name', '').strip().lower()

                # Debugging: Show who it's checking
                print(f"Checking against: {referrer_name}")

                # Flexible match: partial + case-insensitive
                if name_input in referrer_name:
                    bonus_status = check_bonus_eligibility(
                        row.get("start_date"))
                    row["Eligible for 30-Day Bonus"] = bonus_status[
                        "eligible_30"]
                    row["Eligible for 90-Day Bonus"] = bonus_status[
                        "eligible_90"]
                    results.append(row)

    return render_template('lookup.html', results=results)


if __name__ == '__main__':
    app.run(debug=True)
from datetime import timedelta


def check_bonus_eligibility(start_date_str):
    if not start_date_str:
        return {"eligible_30": "No", "eligible_90": "No"}

    try:
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    except ValueError:
        return {"eligible_30": "Invalid Date", "eligible_90": "Invalid Date"}

    today = datetime.today()
    eligible_30 = "Yes" if today >= start_date + timedelta(days=30) else "No"
    eligible_90 = "Yes" if today >= start_date + timedelta(days=90) else "No"

    return {"eligible_30": eligible_30, "eligible_90": eligible_90}
