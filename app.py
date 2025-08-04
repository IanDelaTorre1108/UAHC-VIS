from flask import Flask, render_template, request, send_from_directory, jsonify
from werkzeug.utils import secure_filename
from werkzeug.serving import make_ssl_devcert
import mysql.connector
import os
import uuid
from datetime import datetime

app = Flask(__name__)

def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="UAHC-VIS"
    )

if not os.path.exists('ssl_cert.crt') or not os.path.exists('ssl_cert.key'):
    make_ssl_devcert('ssl_cert', host='localhost')  # Adjust path if needed

# Set the upload directories for profile pictures and violation images
BASE_UPLOAD_FOLDER = 'uploads'
PROFILE_FOLDER = os.path.join(BASE_UPLOAD_FOLDER, 'profile')
VIOLATION_FOLDER = os.path.join(BASE_UPLOAD_FOLDER, 'violations')

os.makedirs(PROFILE_FOLDER, exist_ok=True)
os.makedirs(VIOLATION_FOLDER, exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def generate_report_id():
    return str(uuid.uuid4())

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/scanner')
def scanner():
    return render_template('scanner.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/contact')
def contact():
    return render_template('contact.html')


@app.route('/uploads/profile/<filename>')
def uploaded_profile(filename):
    return send_from_directory(PROFILE_FOLDER, secure_filename(filename))


@app.route('/uploads/violations/<filename>')
def uploaded_violation(filename):
    return send_from_directory(VIOLATION_FOLDER, secure_filename(filename))


@app.route('/api/user/<user_id>')
def get_user_data(user_id):
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
                SELECT 
                    CONCAT(o.first_name, ' ', o.last_name) AS full_name,
                    v.vehicle_id,  -- Add a comma here to separate fields
                    o.address,
                    o.phone,
                    o.profile_pic,
                    e.name AS emergency_name,
                    e.phone AS emergency_phone
                FROM owner o
                LEFT JOIN emergency e ON o.user_id = e.user_id
                LEFT JOIN vehicle v ON o.user_id = v.user_id  -- Assuming the owner has a relationship with vehicle
                WHERE o.user_id = %s
            """, (user_id,))

        
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if not result:
            return jsonify({'status': 'error', 'message': 'User not found'}), 404

        return jsonify(result)

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/report_violation', methods=['POST'])
def report_violation():
    report_id = generate_report_id()
    try:
        violation_type = request.form['violation']
        vehicle_id = request.form['vehicle_id']
        user_id = request.form['user_id']
        status = 'PENDING'
        report_date = datetime.now().strftime('%Y-%m-%d')

        violation_image = request.files.get('violation_image')
        if not violation_image or not allowed_file(violation_image.filename):
            return jsonify({'status': 'error', 'message': 'Invalid image file'}), 400

        # Securely save the violation image
        violation_image_filename = str(uuid.uuid4()) + '.' + violation_image.filename.rsplit('.', 1)[1].lower()
        violation_image_path = os.path.join(VIOLATION_FOLDER, violation_image_filename)
        violation_image.save(violation_image_path)

        # Store report in the database
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO reports (report_id, violation, vehicle_id, user_id, image, status, date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (report_id, violation_type, vehicle_id, user_id, violation_image_filename, status, report_date))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'status': 'success', 'message': 'Violation reported successfully'})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001, ssl_context=("ssl_cert.crt", "ssl_cert.key"))


