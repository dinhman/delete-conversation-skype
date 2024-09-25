from flask import Flask, render_template, request, redirect, url_for, session, flash, copy_current_request_context
import os
import schedule
import time
from skpy import Skype
import logging
import threading
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Configure log file path
log_file_path = 'skype.log'
# Configure logging
logging.basicConfig(
    filename=log_file_path,
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(message)s'
)

# Configure database path
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///D:/Delete-conversation/users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# User Profile Model
class UserProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    skype_user = db.Column(db.String(100), unique=True, nullable=False)
    skype_pwd = db.Column(db.String(100), nullable=False)

# Schedule History Model
class ScheduleHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    skype_user = db.Column(db.String(100), nullable=False)
    delete_username = db.Column(db.String(100), nullable=False)
    scheduled_time = db.Column(db.String(5), nullable=False)  # Store in HH:MM format

# Create the database and tables
with app.app_context():
    db.create_all()

@app.route('/')
def home():
    return redirect(url_for('auth'))  # Redirect to auth page

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        valid_username = "aclq"
        valid_password = "#aclq"

        logging.info(f"Auth attempt for user: {username}")

        if username == valid_username and password == valid_password:
            logging.info(f"Auth successful for user: {username}")
            return redirect(url_for('login'))  # Ensure 'login' is defined
        else:
            logging.warning(f"Auth failed for user: {username}")
            flash('Tên người dùng hoặc mật khẩu không hợp lệ.', 'error')

    return render_template('auth.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        skype_user = request.form['username']
        skype_pwd = request.form['password']
        
        try:
            # Attempt to log in
            sk = Skype(skype_user, skype_pwd)

            # Check if the user already exists
            existing_user = UserProfile.query.filter_by(skype_user=skype_user).first()
            if not existing_user:
                # Create a new user profile
                new_user = UserProfile(skype_user=skype_user, skype_pwd=skype_pwd)
                db.session.add(new_user)
                db.session.commit()
                flash('Profile created successfully!', 'success')
            else:
                flash('Profile already exists, using existing credentials.', 'info')

            session['skype_user'] = skype_user
            session['skype_pwd'] = skype_pwd
            flash('Đăng nhập thành công!', 'success')
            return redirect(url_for('delete_user'))
        except Exception as e:
            flash('Đăng nhập thất bại! Vui lòng kiểm tra lại thông tin.', 'error')
            logging.error(f"Login failed for user {skype_user}: {e}")
    
    return render_template('login.html')

@app.route('/delete_user', methods=['GET', 'POST'])
def delete_user():
    skype_user = session.get('skype_user')
    skype_pwd = session.get('skype_pwd')
    schedule_history = ScheduleHistory.query.filter_by(skype_user=skype_user).all()  # Get schedule history for current user

    if request.method == 'POST':
        delete_username = request.form['delete_username']
        action = request.form['action']

        if action == 'delete_now':
            success = delete_conversation(skype_user, skype_pwd, delete_username)
            if success:
                flash('Cuộc trò chuyện đã được xóa ngay lập tức.', 'success')
            else:
                flash('Không thể xóa cuộc trò chuyện. Kiểm tra lại ID người dùng.', 'error')
        elif action == 'schedule':
            scheduled_time = request.form['scheduled_time']
            
            # Save schedule to the database
            new_schedule = ScheduleHistory(
                skype_user=skype_user,
                delete_username=delete_username,
                scheduled_time=scheduled_time
            )
            db.session.add(new_schedule)
            db.session.commit()

            # Schedule the deletion
            @copy_current_request_context
            def scheduled_task():
                delete_conversation(skype_user, skype_pwd, delete_username)

            schedule.every().day.at(scheduled_time).do(scheduled_task)
            flash(f'Cuộc trò chuyện sẽ được xóa vào lúc {scheduled_time} mỗi ngày.', 'success')

    return render_template('delete_user.html', schedule_history=schedule_history)

def delete_conversation(skype_user, skype_pwd, delete_username):
    try:
        sk = Skype(skype_user, skype_pwd)
        chat = sk.contacts[delete_username].chat

        if chat:
            chat.delete()
            logging.info(f"Successfully deleted conversation with {delete_username}.")
            return True
        else:
            logging.error(f"No chat found with {delete_username}.")
            return False
    except Exception as e:
        logging.error(f"Could not delete conversation with {delete_username}: {e}")
        return False

@app.route('/delete_schedule/<int:schedule_id>', methods=['POST'])
def delete_schedule(schedule_id):
    schedule_to_delete = ScheduleHistory.query.get(schedule_id)
    if schedule_to_delete:
        # Remove the scheduled job if it exists
        schedule.clear(schedule_id)  # Remove from the scheduler
        db.session.delete(schedule_to_delete)
        db.session.commit()
        flash('Lịch trình đã được xóa thành công!', 'success')
    else:
        flash('Không tìm thấy lịch trình.', 'error')
    return redirect(url_for('delete_user'))

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('skype_user', None)  # Remove the user from the session
    session.pop('skype_pwd', None)    # Remove the password from the session
    flash('Đã đăng xuất thành công!', 'success')
    return redirect(url_for('auth'))  # Redirect to auth page

# Keep the script running
def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    scheduler_thread = threading.Thread(target=run_scheduler)
    scheduler_thread.start()
    app.run(debug=True)
