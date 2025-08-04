from flask import Flask, render_template, request, jsonify
import mysql.connector
from datetime import datetime, date

app = Flask(__name__)

def get_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="root",
        database="UAHC-VIS"
    )

def generate_custom_log_id(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM vehicle_log")
    count = cursor.fetchone()[0] + 1
    cursor.close()

    today_str = datetime.now().strftime("%Y%m%d")
    return f"LOG{today_str}-{count:04d}"

@app.route("/")
def index():
    return render_template("index.html")

@app.route('/api/user/<user_id>')
def get_user_data(user_id):
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # Get vehicle for the user
        cursor.execute("SELECT vehicle_id, plate_number, status FROM vehicle WHERE user_id = %s", (user_id,))
        vehicle_data = cursor.fetchone()

        if not vehicle_data:
            cursor.close()
            conn.close()
            return jsonify({'status': 'error', 'message': 'Vehicle not found'}), 404

        vehicle_id = vehicle_data['vehicle_id']
        plate_number = vehicle_data['plate_number']
        vehicle_status = vehicle_data['status']
        today = date.today()
        now = datetime.now().time()

        # 🚫 Don't block expired/pending vehicles anymore — just track status
        # Check report status (if any) for today
        cursor.execute("""
            SELECT status FROM reports 
            WHERE user_id = %s AND vehicle_id = %s AND date = %s 
              AND status IN ('PENDING', 'NONE', 'RESTRICTED')
            ORDER BY id DESC LIMIT 1
        """, (user_id, vehicle_id, today))
        report_status_row = cursor.fetchone()
        report_status = report_status_row['status'] if report_status_row else None

        # Restrict access ONLY if explicitly RESTRICTED or NONE
        if report_status in ('NONE', 'RESTRICTED'):
            cursor.close()
            conn.close()
            return jsonify({
                'status': 'error',
                'message': f'Access denied. Current report status: {report_status}',
                'report_status': report_status
            }), 403

        # Check if user already logged in today without logging out
        cursor.execute("""
            SELECT log_id FROM vehicle_log 
            WHERE user_id = %s AND vehicle_id = %s AND date = %s AND time_out IS NULL
            ORDER BY log_id DESC LIMIT 1
        """, (user_id, vehicle_id, today))
        existing_log = cursor.fetchone()

        if existing_log:
            # Log out
            cursor.execute("""
                UPDATE vehicle_log 
                SET time_out = %s, status = 'Exited' 
                WHERE log_id = %s
            """, (now, existing_log['log_id']))
            action = 'Logged Out'
        else:
            # Log in
            log_id = generate_custom_log_id(conn)
            cursor.execute("""
                INSERT INTO vehicle_log (log_id, user_id, vehicle_id, date, time_in, status)
                VALUES (%s, %s, %s, %s, %s, 'Entered')
            """, (log_id, user_id, vehicle_id, today, now))
            action = 'Logged In'

        conn.commit()

        # Fetch user and latest log info
        cursor.execute("""
            SELECT 
                CONCAT(o.first_name, ' ', o.last_name) AS full_name,
                o.address,
                o.phone,
                %s AS plate_number,
                vl.time_in,
                vl.time_out,
                vl.status
            FROM owner o
            JOIN vehicle_log vl ON o.user_id = vl.user_id
            WHERE o.user_id = %s AND vl.vehicle_id = %s
            ORDER BY vl.log_id DESC
            LIMIT 1
        """, (plate_number, user_id, vehicle_id))
        result = cursor.fetchone()

        cursor.close()
        conn.close()

        if not result:
            return jsonify({'status': 'error', 'message': 'Log retrieval failed'}), 404

        result['action'] = action
        result['report_status'] = report_status if report_status else 'CLEARED'
        result['vehicle_status'] = vehicle_status  # 💡 Include this for frontend display

        return jsonify(result)

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/logs/today')
def get_today_logs():
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        today = date.today()

        # Corrected subquery to get the latest report status per user and vehicle for today
        cursor.execute("""
            SELECT 
            v.plate_number,
            CONCAT(o.first_name, ' ', o.last_name) AS full_name,
            vl.time_in,
            vl.time_out,
            v.status AS vehicle_status,  -- <-- ✅ Add this line
            COALESCE((
                SELECT r.status FROM reports r 
                WHERE r.user_id = vl.user_id 
                AND r.vehicle_id = vl.vehicle_id 
                AND r.date = %s 
                AND r.status IN ('PENDING', 'NONE', 'RESTRICTED')
                LIMIT 1
            ), 'CLEARED') AS report_status
        FROM vehicle_log vl
        JOIN vehicle v ON vl.vehicle_id = v.vehicle_id
        JOIN owner o ON vl.user_id = o.user_id
        WHERE vl.date = %s
        ORDER BY vl.time_in DESC

        """, (today, today))

        logs = cursor.fetchall()
        cursor.close()
        conn.close()

        return jsonify({'status': 'success', 'data': logs})

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5002)

