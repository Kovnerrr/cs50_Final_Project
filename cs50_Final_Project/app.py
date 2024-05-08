from cs50 import SQL
from flask import Flask, render_template, request, session, redirect
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

# boilerplate
app = Flask('__name__')

# configure
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

db = SQL('sqlite:///email.db')


@app.route('/')
def index():
    # Check if the user_id is present in the session and redirect to login if not
    if 'user_id' not in session or session['user_id'] is None:
        return redirect("/login")

    # Retrieve user details from the database using the user_id stored in the session
    user_records = db.execute('SELECT * FROM users WHERE id = ?', session['user_id'])

    # Check if user_records is empty (i.e., no user found with the given ID)
    if not user_records:
        # Clear the session as it contains invalid user_id and redirect to login page
        session.clear()
        return redirect("/login")

    # Extract the user's name from the query result
    actual_name = user_records[0]['name'].title()

    received = db.execute(
        'SELECT mails.id, mails.message, mails.date, users.name FROM mails JOIN users ON users.id = mails.sender_id WHERE mails.receiver_id = ?', session['user_id'])
    return render_template('index.html', actual_name=actual_name, received=received)


@app.route('/login', methods=['GET', 'POST'])
def login():
    session.clear()

    if request.method == 'GET':
        return render_template('login.html')
    else:
        name = request.form.get('name')
        password = request.form.get('password')
        user = db.execute('SELECT * FROM users WHERE name = ?', name)

        # validation
        if not name or not password:
            return render_template('login.html', error='Fill in all fields')
        # check if the user is in the database
        elif not user:
            return render_template('login.html', error='The user does not exist')
        # check if passwords match
        elif len(user) != 1 or not check_password_hash(user[0]["password"], password):
            return render_template('login.html', error='Wrong password')

        session['user_id'] = user[0]['id']

        return redirect('/')


@app.route('/register', methods=['GET', 'POST'])
def register():
    session.clear()

    if request.method == 'GET':
        return render_template('register.html')

    else:
        name = request.form.get('name')
        password = request.form.get('password')
        confirmation = request.form.get('confirm-password')
        users = db.execute('SELECT * FROM users WHERE name = ?', name)

        # validation
        if not name or not password or not confirmation:
            return render_template('register.html', error='Fill in all fields')
        elif password != confirmation:
            return render_template('register.html', error='The passwords don\'t match')
        # check if user already exists
        elif users:
            return render_template('register.html', error='The username already exists')
        # len limit
        elif len(name) > 12:
            return render_template('register.html', error='The maximum number of characters is 12')

        # insert into database and give cookie
        db.execute('INSERT INTO users(name, password) VALUES(?, ?)',
                   name, generate_password_hash(password))

        session['user_id'] = db.execute('SELECT * FROM users WHERE name = ?', name)[0]['id']

        return redirect('/')


@app.route('/send', methods=['GET', 'POST'])
def send():
    if session.get("user_id") == None:
        return redirect("/login")
    actual_name = db.execute('SELECT * FROM users WHERE id = ?',
                             session['user_id'])[0]['name'].title()

    if request.method == 'GET':
        return render_template('send.html', actual_name=actual_name)
    else:
        name = request.form.get('username')
        message = request.form.get('message')
        users = db.execute('SELECT * FROM users WHERE name = ?', name)

        # validation
        if not name:
            return render_template('send.html', actual_name=actual_name, error1='Fill the field')
        elif not message:
            return render_template('send.html', actual_name=actual_name, error2='Fill the field')
        elif not users:
            return render_template('send.html', actual_name=actual_name, error1='The user does not exist')
        # len message
        elif len(message) > 100:
            return render_template('send.html', actual_name=actual_name, error2='The maximum number of characters is 100')

        # insert info into emails
        sender_id = session['user_id']
        receiver_id = users[0]['id']
        text = message
        date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        db.execute('INSERT INTO mails(sender_id, receiver_id, message, date) VALUES(?, ?, ?, ?)',
                   sender_id, receiver_id, text, date)

        return redirect('/')


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    if session.get("user_id") == None:
        return redirect("/login")
    actual_name = db.execute('SELECT * FROM users WHERE id = ?',
                             session['user_id'])[0]['name'].title()

    if request.method == 'GET':
        return render_template('settings.html', actual_name=actual_name)
    else:
        actualUser = db.execute('SELECT * from users WHERE id = ?', session['user_id'])

        # identify if that is the username form
        if 'new-username' in request.form:
            newName = request.form.get('new-username')
            users = db.execute('SELECT * FROM users WHERE name = ?', newName)

            # validation
            if not newName:
                return render_template('settings.html', actual_name=actual_name, error1='Fill the field')
            elif users:
                return render_template('settings.html', actual_name=actual_name, error1='User already exists')

            # change database
            db.execute('UPDATE users SET name = ? WHERE id = ?', newName, session['user_id'])

            return redirect('/')

        # identify if that is the password form
        else:
            oldPassword = request.form.get('old-password')
            newPassword = request.form.get('new-password')

            # validation
            if not oldPassword or not newPassword:
                return render_template('settings.html', actual_name=actual_name, error2='Fill all fields')
            elif not check_password_hash(actualUser[0]["password"], oldPassword):
                return render_template('settings.html', actual_name=actual_name, error2='Wrong password')
            elif oldPassword == newPassword:
                return render_template('settings.html', actual_name=actual_name, error2='The passwords are the same')

            # change database
            db.execute('UPDATE users SET password = ? WHERE id = ?',
                       generate_password_hash(newPassword), session['user_id'])

            return redirect('/')


@app.route('/reply/<int:email_id>', methods=['GET', 'POST'])
def reply(email_id):
    if 'user_id' not in session:
        return redirect("/login")

    original_email = db.execute('SELECT * FROM mails WHERE id = ?', email_id)
    if not original_email:
        return "Original message not found", 404  # Better error handling

    if request.method == 'GET':
        return render_template('reply.html', original_message=original_email[0], email_id=email_id)

    else:
        reply_message = request.form.get('message')
        if not reply_message:
            return render_template('reply.html', original_message=original_email[0], error="Please enter a reply message")

        sender_id = session['user_id']
        receiver_id = original_email[0]['sender_id']
        date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        db.execute('INSERT INTO mails(sender_id, receiver_id, message, date, reply_to_id) VALUES(?, ?, ?, ?, ?)',
                   sender_id, receiver_id, reply_message, date, email_id)

        return redirect('/')

@app.route('/delete/<int:email_id>', methods=['POST'])
def delete_email(email_id):
    if 'user_id' not in session:
        return redirect("/login")

    email = db.execute('SELECT * FROM mails WHERE id = ?', email_id)
    if not email:
        return "Message not found", 404

    if email[0]['receiver_id'] != session['user_id']:
        return "You do not have permission to delete this message", 403

    db.execute('DELETE FROM mails WHERE id = ?', email_id)
    return redirect('/')
