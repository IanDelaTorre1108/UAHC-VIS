from flask import Flask, render_template, request, send_from_directory, jsonify, redirect, flash, url_for, session
from collections import defaultdict
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from functools import wraps

import os
import mysql.connector
import string
import random

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
BASE_UPLOAD_FOLDER = '../uploads'
PROFILE_FOLDER = os.path.join(BASE_UPLOAD_FOLDER, 'profile')
VIOLATION_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'uploads', 'violations'))

# ID_FOLDER = os.path.join(BASE_UPLOAD_FOLDER, 'id')
# LICENSE_FOLDER = os.path.join(BASE_UPLOAD_FOLDER, 'license')

os.makedirs(PROFILE_FOLDER, exist_ok=True)
os.makedirs(VIOLATION_FOLDER, exist_ok=True)


# os.makedirs(ID_FOLDER, exist_ok=True)
# os.makedirs(LICENSE_FOLDER, exist_ok=True)


app = Flask(__name__)

app.secret_key = 'UAHC-VIS'

def generated_user_id(length=6):
    characters = string.ascii_uppercase + string.digits
    return 'USR' + ''.join(random.choices(characters, k=length))

def generated_vehicle_id(length=9):
    characters = string.ascii_uppercase + string.digits
    return 'VHC' + ''.join(random.choices(characters, k=length))

def generate_gatepass(length=3):
    try:
        with open("gatepass_counter.txt", "r") as file:
            number = int(file.read())
    except FileNotFoundError:
        number = 0

    number += 1

    with open("gatepass_counter.txt", "w") as file:
        file.write(str(number))

    return f"GP{str(number).zfill(length)}"

def generated_emergency_id(length=5):
    characters = string.ascii_uppercase + string.digits
    return 'EMR' + ''.join(random.choices(characters, k=length))

def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="UAHC-VIS"
    )

def vehicle_count():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM vehicle')
    count = cursor.fetchone()[0] 
    cursor.close()
    conn.close()
    return count

def today_log():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM vehicle_log WHERE DATE(date) = CURDATE() AND status ="ENTERED" ')
    vehicle_log_count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return vehicle_log_count

def pending_reports():
	conn = get_db_connection()
	cursor = conn.cursor()
	cursor.execute('SELECT COUNT(*) FROM reports WHERE status = "PENDING"')
	pending_reports = cursor.fetchone()[0]
	cursor.close()
	conn.close()
	return pending_reports

def get_notifications():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT user_id FROM owner ORDER BY id DESC LIMIT 5")
    new_users = cursor.fetchall()

    cursor.execute("""
        SELECT vehicle_id, status, date, time_in, time_out
        FROM vehicle_log
        ORDER BY id DESC LIMIT 5
    """)
    vehicle_logs = cursor.fetchall()

    cursor.execute("""
        SELECT vehicle_id, violation, date 
        FROM reports 
        ORDER BY id DESC LIMIT 5
    """)
    reports = cursor.fetchall()

    cursor.close()
    conn.close()

    notifications = []

    for row in new_users:
        user_id = row[0]
        notifications.append(f"User {user_id} registered to the system.")

    for row in vehicle_logs:
        vehicle_id, status, date, time_in, time_out = row
        if status:
            if status.lower() == "in":
                notifications.append(f"Vehicle {vehicle_id} entered the campus.")
            elif status.lower() == "out":
                notifications.append(f"Vehicle {vehicle_id} exited the campus.")
        else:
            notifications.append(f"Vehicle {vehicle_id} had unknown status.")

    for row in reports:
        vehicle_id, violation, date = row
        notifications.append(f"Vehicle {vehicle_id} reported for {violation}.")

    return notifications

def update_vehicle_status():
    db = get_db_connection()
    cursor = db.cursor()

    today_date = datetime.now().date()

    cursor.execute("""
        UPDATE vehicle 
        SET status = 'Expired' 
        WHERE expiration_date < %s AND status = 'Active'
    """, (today_date,))

    db.commit()
    cursor.close()
    db.close()


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        # Match exact username/password from DB
        cursor.execute("SELECT * FROM admin WHERE username = %s AND password = %s", (username, password))
        user = cursor.fetchone()

        if user:
            session['admin_username'] = user['username']
            flash('Login successful.')
            result = redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.')
            result = redirect(url_for('index'))

        cursor.close()
        conn.close()
        return result

    return render_template('index.html')



@app.route('/dashboard')
def dashboard():
    if 'admin_username' not in session:
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get vehicle logs grouped by date
    cursor.execute("SELECT DATE(date), COUNT(*) FROM vehicle_log GROUP BY DATE(date) ORDER BY date ASC")
    vehicle_logs = cursor.fetchall()

    # Get reports grouped by date
    cursor.execute("SELECT DATE(date), COUNT(*) FROM reports GROUP BY DATE(date) ORDER BY date ASC")
    reports = cursor.fetchall()

    cursor.close()
    conn.close()

    raw_dates = [row[0] for row in vehicle_logs]
    vehicles_data = [row[1] for row in vehicle_logs]
    formatted_dates = [d.strftime("%b %d") for d in raw_dates]

    reports_dict = {row[0]: row[1] for row in reports}
    reports_data = [reports_dict.get(d, 0) for d in raw_dates]

    total_vehicles = vehicle_count()
    logs_today = today_log()
    reported_pending = pending_reports()
    notifications = get_notifications()

    return render_template(
        'dashboard.html',
        vehicle_count=total_vehicles,
        logs_today=logs_today,
        reported_pending=reported_pending,
        labels=formatted_dates,
        vehicle_data=vehicles_data,
        report_data=reports_data,
        notifications=notifications
    )

@app.route('/manage_vehicle')
def manage_vehicle():

    if 'admin_username' not in session:
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
    SELECT o.user_id, o.first_name, o.last_name, o.address, o.phone, o.profile_pic,
        v.vehicle_id, v.gate_pass, v.plate_number, v.vehicle_type, v.status,
        e.name AS emergency_name, e.phone AS emergency_phone
    FROM owner o
    JOIN vehicle v ON v.user_id = o.user_id
    JOIN emergency e ON e.user_id = o.user_id
""")
    
    owners = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('manage_vehicle.html', owners=owners)

@app.route('/vehicle')
def vehicle():
	conn = get_db_connection()
	cursor = conn.cursor(dictionary=True)

	cursor.execute("""SELECT v.vehicle_id, v.user_id, v.plate_number, v.vehicle_type, v.brand, v.color, v.driver_license, o.first_name, o.last_name, o.email
        FROM vehicle v
        JOIN owner o ON v.user_id = o.user_id
    """)

	vehicles = cursor.fetchall()

	cursor.close()
	conn.close()
    

	return render_template('vehicle.html', vehicles=vehicles)

@app.route('/vehicle_log')
def vehicle_log():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("SELECT DISTINCT DATE(date) AS log_date FROM vehicle_log ORDER BY log_date DESC")
    date_rows = cursor.fetchall()
    dates = [row['log_date'].strftime('%Y-%m-%d') for row in date_rows]

    selected_date = request.args.get('date', datetime.today().strftime('%Y-%m-%d'))

    cursor.execute("""
        SELECT v.plate_number, o.first_name, o.last_name, vl.time_in, vl.time_out 
        FROM vehicle_log vl
        JOIN vehicle v ON vl.vehicle_id = v.vehicle_id
        JOIN owner o ON vl.user_id = o.user_id
        WHERE DATE(vl.date) = %s
    """, (selected_date,))
    logs = cursor.fetchall()

    log_count = len(logs)

    formatted_date = datetime.strptime(selected_date, '%Y-%m-%d').strftime('%A, %B %d, %Y')

    cursor.close()
    conn.close()

    return render_template(
        'vehicle_log.html',
        logs=logs,
        dates=dates,
        selected_date=selected_date,
        formatted_date=formatted_date,
        log_count=log_count
    )

@app.route('/reported')
def reported():

    if 'admin_username' not in session:
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Get all distinct report dates (for dropdown)
    cursor.execute("""
        SELECT DISTINCT DATE(date) AS report_date
        FROM reports
        WHERE status IN ('PENDING', 'RESTRICTED')
        ORDER BY report_date DESC
    """)
    date_rows = cursor.fetchall()
    dates = [row['report_date'].strftime('%Y-%m-%d') for row in date_rows]

    # Get selected date from query parameters
    selected_date = request.args.get('date')
    formatted_date = None

    # Validate date
    if selected_date:
        try:
            datetime.strptime(selected_date, '%Y-%m-%d')
            formatted_date = datetime.strptime(selected_date, '%Y-%m-%d').strftime('%A, %B %d, %Y')
        except ValueError:
            selected_date = None  # fallback to show all

    # Base query: only PENDING or RESTRICTED
    query = """
        SELECT v.plate_number, o.first_name, o.last_name, r.image,
               r.status, r.violation, r.id, r.date
        FROM reports r
        JOIN vehicle v ON r.vehicle_id = v.vehicle_id
        JOIN owner o ON r.user_id = o.user_id
        WHERE r.status IN ('PENDING', 'RESTRICTED')
    """

    params = ()

    if selected_date:
        query += " AND DATE(r.date) = %s"
        params = (selected_date,)

    query += " ORDER BY r.date DESC"

    cursor.execute(query, params)
    report = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        'reported.html',
        dates=dates,
        selected_date=selected_date,
        formatted_date=formatted_date,
        report=report,
        report_count=len(report)
    )

@app.route('/registration', methods=['GET', 'POST'])
def registration():
    if 'admin_username' not in session:
        return redirect(url_for('index'))

    if request.method == "POST":
        db = get_db_connection()
        cursor = db.cursor()

        # Get the plate number first to check existence
        plate_number = request.form.get('plate_number', '').strip()

        # Check if plate number already exists
        cursor.execute("SELECT COUNT(*) FROM vehicle WHERE plate_number = %s", (plate_number,))
        exists = cursor.fetchone()[0]

        if exists:
            cursor.close()
            db.close()
            # Return JSON to be handled by JS (AJAX)
            return jsonify({'status': 'error', 'message': 'Plate number already exists!'})

        # Plate number does not exist, continue with registration
        user_id = generated_user_id()
        vehicle_id = generated_vehicle_id()
        gatepass = generate_gatepass()
        emergency_id = generated_emergency_id()

        last_name = request.form.get('last_name', '').strip()
        first_name = request.form.get('first_name', '').strip()
        middle_name = request.form.get('middle_name', '').strip()
        address = request.form.get('address', '').strip()
        phone = request.form.get('phone', '').strip()
        birthday = request.form.get('birthday', '').strip()
        place_of_birth = request.form.get('place_of_birth', '').strip()
        gender = request.form.get('gender', '').strip()
        civil_status = request.form.get('civil_status', '').strip()

        emergency_contact_name = request.form.get('emergency_contact_name', '').strip()
        emergency_contact_number = request.form.get('emergency_contact_number', '').strip()

        license_no = request.form.get('license_no', '').strip()
        license_type = request.form.get('license_type', '').strip()
        vehicle_type = request.form.get('vehicle_type', '').strip()
        color = request.form.get('color', '').strip()
        brand = request.form.get('brand', '').strip()
        franchise_no = request.form.get('franchise_no', '').strip()
        if franchise_no == '':
            franchise_no = None
        else:
            franchise_no = int(franchise_no)
        association = request.form.get('association', '').strip()

        profile_pic_file = request.files.get('profile_pic')
        profile_pic_filename = ''

        if profile_pic_file and allowed_file(profile_pic_file.filename):
            profile_pic_filename = f"{user_id}_{secure_filename(profile_pic_file.filename)}"
            profile_pic_file.save(os.path.join(PROFILE_FOLDER, profile_pic_filename))

        if first_name and last_name:
            # User Table Insert (with status as active)
            user_query = """
                INSERT INTO owner (user_id, last_name, first_name, middle_name, address, phone, 
                                   birthday, place_of_birth, gender, civil_status, profile_pic, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            user_val = (user_id, last_name, first_name, middle_name, address, phone, birthday, place_of_birth, 
                        gender, civil_status, profile_pic_filename, "active")
            cursor.execute(user_query, user_val)

            # Emergency Table Insert
            emergency_query = """
                INSERT INTO emergency (emergency_id, user_id, name, phone) 
                VALUES (%s, %s, %s, %s)
            """
            emergency_val = (emergency_id, user_id, emergency_contact_name, emergency_contact_number)
            cursor.execute(emergency_query, emergency_val)

            # Vehicle Table Insert (with expiration_date and status set to 1 year from now)
            vehicle_query = """
                INSERT INTO vehicle (vehicle_id, user_id, gate_pass, license_number, license_type, 
                                     vehicle_type, color, brand, plate_number, franchise_no, association, 
                                     expiration_date, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            # Calculate expiration_date as 1 year from today (only date, no time)
            expiration_date = (datetime.now() + timedelta(days=365)).date()  # `.date()` to remove time part
            status = "Active"  # Default status is active when registering a vehicle
            vehicle_val = (vehicle_id, user_id, gatepass, license_no, license_type, vehicle_type, 
                           color, brand, plate_number, franchise_no, association, expiration_date, status)
            cursor.execute(vehicle_query, vehicle_val)

            db.commit()

        cursor.close()
        db.close()

        return jsonify({'status': 'success', 'message': 'Registration successful!'})

    return render_template("registration.html")


@app.route('/settings')
def settings():
    if 'admin_username' not in session:
        return redirect(url_for('index'))
    
    return render_template('settings.html')

@app.route('/uploads/violations/<filename>')
def uploaded_violation_image(filename):
    return send_from_directory(VIOLATION_FOLDER, filename)

@app.route('/uploads/profile/<filename>')
def uploaded_profile(filename):
    safe_filename = secure_filename(filename)
    return send_from_directory(PROFILE_FOLDER, safe_filename)

@app.route('/owner_qr/<int:user_id>')
def owner_qr(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    print(f"Fetching data for user_id: {user_id}")  # Debug print
    cursor.execute("""
        SELECT o.first_name, o.last_name, o.address, o.phone, v.vehicle_type, v.plate_number, e.name AS emergency_name, e.phone AS emergency_phone
        FROM owner o
        JOIN vehicle v ON o.user_id = v.user_id
        LEFT JOIN emergency e ON e.user_id = o.user_id
        WHERE o.user_id = %s
    """, (user_id,))
    owner = cursor.fetchone()
    cursor.close()
    conn.close()
    print(f"Query result: {owner}")  # Debug print
    if owner:
        return jsonify(owner)
    else:
        return jsonify({"error": "Owner not found"}), 404

@app.route('/get_owner/<user_id>')
def get_owner(user_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT o.*, v.*, e.name AS emergency_name, e.phone AS emergency_phone
        FROM owner o
        JOIN vehicle v ON v.user_id = o.user_id
        LEFT JOIN emergency e ON e.user_id = o.user_id
        WHERE o.user_id = %s
    """, (user_id,))
    data = cursor.fetchone()
    cursor.close()
    conn.close()
    return jsonify(data)

@app.route('/renew_vehicle', methods=['POST'])
def renew_vehicle():
    data = request.get_json()
    user_id = data.get('user_id')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Add 365 days from today
        new_expiration = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')

        # Update the vehicle table for that user
        cursor.execute("""
            UPDATE vehicle
            SET status = 'Active',
                expiration_date = %s
            WHERE user_id = %s
        """, (new_expiration, user_id))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/update_owner', methods=['POST'])
def update_owner():
    user_id = request.form.get('user_id')
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    middle_name = request.form.get('middle_name')
    address = request.form.get('address')
    phone = request.form.get('phone')
    birthday = request.form.get('birthday')
    place_of_birth = request.form.get('place_of_birth')
    gender = request.form.get('gender')
    civil_status = request.form.get('civil_status')

    emergency_name = request.form.get('emergency_contact_name')
    emergency_phone = request.form.get('emergency_contact_number')

    license_no = request.form.get('license_no')
    expiry = request.form.get('expiry')
    license_type = request.form.get('license_type')
    vehicle_type = request.form.get('vehicle_type')
    color = request.form.get('color')
    brand = request.form.get('brand')
    plate_number = request.form.get('plate_number')
    franchise_no = request.form.get('franchise_no') or None
    association = request.form.get('association')

    profile_pic_file = request.files.get('profile_pic')
    profile_pic_filename = None

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get old profile_pic to optionally delete
    cursor.execute("SELECT profile_pic FROM owner WHERE user_id = %s", (user_id,))
    old_pic = cursor.fetchone()
    old_profile_pic = old_pic[0] if old_pic else None

    # Save new profile picture if uploaded
    if profile_pic_file and allowed_file(profile_pic_file.filename):
        profile_pic_filename = f"{user_id}_{secure_filename(profile_pic_file.filename)}"
        profile_pic_path = os.path.join(PROFILE_FOLDER, profile_pic_filename)
        profile_pic_file.save(profile_pic_path)

        # Optional: Delete old file
        if old_profile_pic:
            old_path = os.path.join(PROFILE_FOLDER, old_profile_pic)
            if os.path.exists(old_path):
                os.remove(old_path)

        # Update profile picture
        cursor.execute("""
            UPDATE owner
            SET profile_pic=%s
            WHERE user_id=%s
        """, (profile_pic_filename, user_id))

    # Update owner info
    cursor.execute("""
        UPDATE owner
        SET first_name=%s, last_name=%s, middle_name=%s,
            address=%s, phone=%s, birthday=%s,
            place_of_birth=%s, gender=%s, civil_status=%s
        WHERE user_id=%s
    """, (first_name, last_name, middle_name, address, phone, birthday,
        place_of_birth, gender, civil_status, user_id))

    # Update emergency contact
    cursor.execute("""
        UPDATE emergency
        SET name=%s, phone=%s
        WHERE user_id=%s
    """, (emergency_name, emergency_phone, user_id))

    # Update vehicle info
    cursor.execute("""
        UPDATE vehicle
        SET license_number=%s, expiry=%s, license_type=%s,
            vehicle_type=%s, color=%s, brand=%s, plate_number=%s,
            franchise_no=%s, association=%s
        WHERE user_id=%s
    """, (license_no, expiry, license_type, vehicle_type, color, brand,
        plate_number, franchise_no, association, user_id))

    conn.commit()
    cursor.close()
    conn.close()

    return redirect('/manage_vehicle')

@app.route('/delete_owner/<user_id>', methods=['DELETE'])
def delete_owner(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Delete emergency contact
        cursor.execute("DELETE FROM emergency WHERE user_id = %s", (user_id,))
        # Delete vehicle
        cursor.execute("DELETE FROM vehicle WHERE user_id = %s", (user_id,))
        # Delete owner
        cursor.execute("DELETE FROM owner WHERE user_id = %s", (user_id,))

        conn.commit()
        return '', 204  # Success with no content
    except Exception as e:
        print("Error deleting owner:", e)
        conn.rollback()
        return 'Error deleting owner', 500
    finally:
        cursor.close()
        conn.close()

@app.route('/approve_report/<int:report_id>', methods=['POST'])
def approve_report(report_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE reports SET status = 'APPROVED' WHERE id = %s", (report_id,))
        conn.commit()
        return '', 204  # No content, success
    except Exception as e:
        conn.rollback()
        return str(e), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/restrict_report/<int:report_id>', methods=['POST'])
def restrict_report(report_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE reports SET status = 'RESTRICTED' WHERE id = %s", (report_id,))
        conn.commit()
        return '', 204
    except Exception as e:
        conn.rollback()
        return str(e), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/logout')
def logout():
    session.pop('admin_username', None)
    flash("Logged out successfully.")
    return redirect(url_for('index')) 

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5003)
