from flask import Flask, render_template, request, redirect, url_for, session
import boto3
from datetime import date
import uuid

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Initialize DynamoDB and SNS clients
dynamodb = boto3.resource('dynamodb', region_name='us-east-')
sns = boto3.client('sns', region_name='us-east-1')

# Table references
users_table = dynamodb.Table('users')
med_table = dynamodb.Table('medications')
dose_table = dynamodb.Table('dose_log')
doc_table = dynamodb.Table('doctors')

# ✅ Home Page
@app.route('/')
def home():
    return render_template('home.html')

# ✅ Login Page
@app.route('/login')
def login():
    return render_template('login.html')

# ✅ Register New User
@app.route('/register', methods=['POST'])
def register():
    name = request.form['name']
    email = request.form['email']
    password = request.form['password']

    user = users_table.get_item(Key={'email': email}).get('Item')
    if user:
        return "User already exists. <a href='/login'>Login</a>"

    users_table.put_item(Item={
        'email': email,
        'name': name,
        'password': password
    })
    return f"User {name} registered successfully. <a href='/login'>Login now</a>"

# ✅ Handle Existing User Login
@app.route('/login-existing', methods=['POST'])
def login_existing():
    email = request.form['email']
    password = request.form['password']

    user = users_table.get_item(Key={'email': email}).get('Item')
    if user and user['password'] == password:
        session['username'] = user['name']
        session['email'] = user['email']
        return redirect(url_for('dashboard'))
    return "Invalid credentials. <a href='/login'>Try again</a>"

# ✅ Dashboard
@app.route('/dashboard')
def dashboard():
    if 'email' not in session:
        return redirect(url_for('login'))

    email = session['email']
    username = session['username']
    today = date.today().isoformat()

    meds = med_table.scan(
        FilterExpression="user_email = :e",
        ExpressionAttributeValues={":e": email}
    )['Items']

    todays_meds = [m for m in meds if m['start_date'] <= today and m['end_date'] >= today]

    total_doses = len(todays_meds)
    completed_doses = dose_table.scan(
        FilterExpression="user_email = :e",
        ExpressionAttributeValues={":e": email}
    )['Count']
    progress = int((completed_doses / total_doses) * 100) if total_doses > 0 else 0

    doc = doc_table.get_item(Key={'user_email': email}).get('Item')

    return render_template("dashboard.html", username=username, medications=meds,
                           reminders=todays_meds, progress=progress, doctor=doc)

# ✅ Add New Medicine
@app.route('/add-medicine', methods=['GET', 'POST'])
def add_medicine():
    if 'email' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        med_id = str(uuid.uuid4())
        data = {
            'id': med_id,
            'user_email': session['email'],
            'medicine_name': request.form['medicine_name'],
            'dose_count': request.form['dose_count'],
            'dose_time': request.form['dose_time'],
            'start_date': request.form['start_date'],
            'end_date': request.form['end_date'],
            'frequency': request.form['frequency']
        }
        med_table.put_item(Item=data)
        return redirect(url_for('dashboard'))

    return render_template('add_medicine.html')

# ✅ Edit Existing Medicine
@app.route('/edit-medicine/<string:medicine_id>', methods=['GET', 'POST'])
def edit_medicine(medicine_id):
    if 'email' not in session:
        return redirect(url_for('login'))

    email = session['email']
    if request.method == 'POST':
        update_expr = "SET medicine_name=:n, dose_count=:dc, dose_time=:dt, start_date=:sd, end_date=:ed, frequency=:f"
        expr_vals = {
            ':n': request.form['medicine_name'],
            ':dc': request.form['dose_count'],
            ':dt': request.form['dose_time'],
            ':sd': request.form['start_date'],
            ':ed': request.form['end_date'],
            ':f': request.form['frequency']
        }
        med_table.update_item(
            Key={'id': medicine_id, 'user_email': email},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_vals
        )
        return redirect(url_for('dashboard'))

    med = med_table.get_item(Key={'id': medicine_id, 'user_email': email}).get('Item')
    if not med:
        return "Medicine not found or access denied."
    return render_template('edit_medicine.html', medicine=med)

# ✅ Delete Medicine
@app.route('/delete-medicine/<string:medicine_id>', methods=['POST'])
def delete_medicine(medicine_id):
    if 'email' not in session:
        return redirect(url_for('login'))
    med_table.delete_item(Key={'id': medicine_id, 'user_email': session['email']})
    return redirect(url_for('dashboard'))

# ✅ Mark Dose as Completed
@app.route('/complete-dose/<string:med_id>', methods=['POST'])
def complete_dose(med_id):
    if 'email' not in session:
        return redirect(url_for('login'))
    dose_table.put_item(Item={
        'id': str(uuid.uuid4()),
        'user_email': session['email'],
        'medicine_id': med_id,
        'date': date.today().isoformat()
    })

    # Optional: send email notification using SNS
    user_email = session['email']
    try:
        sns.publish(
            TopicArn='arn:aws:sns:ap-south-1:YOUR_ACCOUNT_ID:YourTopic',
            Subject="Dose Completed",
            Message=f"You completed your dose for medicine ID: {med_id}",
        )
    except Exception as e:
        print("SNS Error:", e)

    return redirect(url_for('dashboard'))

# ✅ User Profile
@app.route('/user')
def user_profile():
    if 'email' not in session:
        return redirect(url_for('login'))
    return render_template('user_profile.html', username=session['username'], email=session['email'])

# ✅ Add or Update Doctor Info
@app.route('/doctor-info', methods=['GET', 'POST'])
def doctor_info():
    if 'email' not in session:
        return redirect(url_for('login'))

    email = session['email']
    if request.method == 'POST':
        doc_table.put_item(Item={
            'user_email': email,
            'name': request.form['name'],
            'specialization': request.form['specialization'],
            'phone': request.form['phone'],
            'email': request.form['email'],
            'next_checkup_date': request.form['next_checkup_date']
        })
        return redirect(url_for('dashboard'))

    doctor = doc_table.get_item(Key={'user_email': email}).get('Item')
    return render_template('doctor_form.html', doctor=doctor)

# ✅ Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# ✅ Run
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0',port=5000)