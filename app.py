from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
from datetime import date

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Used to manage sessions securely

# ✅ Connect to MySQL Database
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="medtrack_db"
)
cursor = db.cursor(dictionary=True)

# ✅ Home Page
@app.route('/')
def home():
    return render_template('home.html')

# ✅ Login Page
@app.route('/login')
def login():
    return render_template('login.html')

# ✅ Handle Existing User Login
@app.route('/login-existing', methods=['POST'])
def login_existing():
    email = request.form['email']
    password = request.form['password']
    cursor.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, password))
    user = cursor.fetchone()
    if user:
        session['username'] = user['name']
        session['email'] = user['email']
        return redirect(url_for('dashboard'))
    else:
        return "Invalid credentials. <a href='/login'>Try again</a>"

# ✅ Register New User
@app.route('/register', methods=['POST'])
def register():
    name = request.form['name']
    email = request.form['email']
    password = request.form['password']
    cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
    if cursor.fetchone():
        return "User already exists. <a href='/login'>Login</a>"
    cursor.execute("INSERT INTO users (name, email, password) VALUES (%s, %s, %s)", (name, email, password))
    db.commit()
    return f"User {name} registered successfully. <a href='/login'>Login now</a>"

# ✅ Dashboard: View Medications, Reminders, Progress, Doctor Info
@app.route('/dashboard')
def dashboard():
    if 'email' not in session:
        return redirect(url_for('login'))

    username = session['username']
    user_email = session['email']

    # All medications for the user
    cursor.execute("SELECT * FROM medications WHERE user_email = %s", (user_email,))
    all_meds = cursor.fetchall()

    # Today's medication reminders
    today = date.today().isoformat()
    cursor.execute("""
        SELECT * FROM medications 
        WHERE user_email = %s AND start_date <= %s AND end_date >= %s
    """, (user_email, today, today))
    todays_meds = cursor.fetchall()

    # Calculate progress (completed doses)
    cursor.execute("SELECT COUNT(*) AS total FROM medications WHERE user_email = %s AND start_date <= %s AND end_date >= %s",
                   (user_email, today, today))
    total_doses = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(*) AS completed FROM dose_log WHERE user_email = %s", (user_email,))
    completed_doses = cursor.fetchone()['completed']

    progress_percent = int((completed_doses / total_doses) * 100) if total_doses > 0 else 0

    # Get doctor info
    cursor.execute("SELECT * FROM doctors WHERE user_email = %s", (user_email,))
    doctor = cursor.fetchone()

    return render_template('dashboard.html', username=username, medications=all_meds,
                           reminders=todays_meds, progress=progress_percent, doctor=doctor)

# ✅ Add New Medicine
@app.route('/add-medicine', methods=['GET', 'POST'])
def add_medicine():
    if 'email' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        medicine_name = request.form['medicine_name']
        dose_count = request.form['dose_count']
        dose_time = request.form['dose_time']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        frequency = request.form['frequency']
        user_email = session['email']

        cursor.execute("""
            INSERT INTO medications (user_email, medicine_name, dose_count, dose_time, start_date, end_date, frequency)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (user_email, medicine_name, dose_count, dose_time, start_date, end_date, frequency))
        db.commit()
        return redirect(url_for('dashboard'))

    return render_template('add_medicine.html')

# ✅ User Profile
@app.route('/user')
def user_profile():
    if 'email' not in session:
        return redirect(url_for('login'))
    return render_template('user_profile.html', username=session.get('username'), email=session.get('email'))


# ✅ Mark a Dose as Completed
@app.route('/complete-dose/<int:med_id>', methods=['POST'])
def complete_dose(med_id):
    if 'email' not in session:
        return redirect(url_for('login'))

    user_email = session['email']
    cursor.execute("INSERT INTO dose_log (user_email, medicine_id) VALUES (%s, %s)", (user_email, med_id))
    db.commit()
    return redirect(url_for('dashboard'))

# ✅ Edit Existing Medicine
@app.route('/edit-medicine/<int:medicine_id>', methods=['GET', 'POST'])
def edit_medicine(medicine_id):
    if 'email' not in session:
        return redirect(url_for('login'))

    user_email = session['email']

    if request.method == 'POST':
        medicine_name = request.form['medicine_name']
        dose_count = request.form['dose_count']
        dose_time = request.form['dose_time']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        frequency = request.form['frequency']

        cursor.execute("""
            UPDATE medications
            SET medicine_name = %s, dose_count = %s, dose_time = %s, start_date = %s, end_date = %s, frequency = %s
            WHERE id = %s AND user_email = %s
        """, (medicine_name, dose_count, dose_time, start_date, end_date, frequency, medicine_id, user_email))
        db.commit()
        return redirect(url_for('dashboard'))

    cursor.execute("SELECT * FROM medications WHERE id = %s AND user_email = %s", (medicine_id, user_email))
    medicine = cursor.fetchone()

    if not medicine:
        return "Medicine not found or access denied."

    return render_template('edit_medicine.html', medicine=medicine)

# ✅ Delete a Medicine
@app.route('/delete-medicine/<int:medicine_id>', methods=['POST'])
def delete_medicine(medicine_id):
    if 'email' not in session:
        return redirect(url_for('login'))

    user_email = session['email']
    cursor.execute("DELETE FROM medications WHERE id = %s AND user_email = %s", (medicine_id, user_email))
    db.commit()
    return redirect(url_for('dashboard'))

# ✅ Add or Update Doctor Info
@app.route('/doctor-info', methods=['GET', 'POST'])
def doctor_info():
    if 'email' not in session:
        return redirect(url_for('login'))

    user_email = session['email']

    if request.method == 'POST':
        name = request.form['name']
        specialization = request.form['specialization']
        phone = request.form['phone']
        email = request.form['email']
        next_checkup_date = request.form['next_checkup_date']

        cursor.execute("SELECT * FROM doctors WHERE user_email = %s", (user_email,))
        existing = cursor.fetchone()

        if existing:
            cursor.execute("""
                UPDATE doctors SET name = %s, specialization = %s, phone = %s, email = %s, next_checkup_date = %s
                WHERE user_email = %s
            """, (name, specialization, phone, email, next_checkup_date, user_email))
        else:
            cursor.execute("""
                INSERT INTO doctors (user_email, name, specialization, phone, email, next_checkup_date)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (user_email, name, specialization, phone, email, next_checkup_date))

        db.commit()
        return redirect(url_for('dashboard'))

    cursor.execute("SELECT * FROM doctors WHERE user_email = %s", (user_email,))
    doctor = cursor.fetchone()

    return render_template('doctor_form.html', doctor=doctor)

# ✅ Logout – End Session
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# ✅ Run the App
if __name__ == "__main__":
    app.run(debug=True)
