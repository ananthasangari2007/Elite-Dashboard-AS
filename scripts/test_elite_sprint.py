import tempfile, os, re
from pathlib import Path
from app import create_app, db
from app.models import User, Task, EliteSprintSession, EliteSprintBid

class TestConfig:
    SECRET_KEY = 'test-secret'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + str(Path(tempfile.gettempdir()) / 'elite_test.sqlite3')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_TIME_LIMIT = None

db_path = str(Path(tempfile.gettempdir()) / 'elite_test.sqlite3')
if os.path.exists(db_path):
    os.unlink(db_path)

app = create_app(TestConfig)
with app.app_context():
    db.create_all()
    
    admin = User(name='Admin', email='admin@test.com', role='admin', profile_completed=True)
    admin.set_password('Admin@123')
    db.session.add(admin)
    
    student = User(name='Student', email='student@test.com', role='student', profile_completed=True)
    student.set_password('Student@123')
    db.session.add(student)
    db.session.commit()
    
    for i in range(1, 7):
        task = Task(task_code='T%d' % i, title='Task %d' % i, description='test', reward_points=10, task_type='daily', status='active')
        db.session.add(task)
    db.session.commit()
    
    from datetime import date, time, datetime, timedelta
    today = date.today()
    past = datetime.utcnow() - timedelta(hours=2)
    future = datetime.utcnow() + timedelta(hours=2)
    
    session = EliteSprintSession(
        sprint_date=today,
        start_time=time(past.hour, past.minute),
        end_time=time(future.hour, future.minute),
    )
    db.session.add(session)
    db.session.commit()
    
    print('Setup complete')

client = app.test_client()

# Login as admin
resp = client.get('/login/admin')
match = re.search(r'name="csrf_token" value="([^"]+)"', resp.get_data(as_text=True))
token = match.group(1) if match else ''
resp = client.post('/login/admin', data={'csrf_token': token, 'email': 'admin@test.com', 'password': 'Admin@123'}, follow_redirects=True)
print('Admin login: %d' % resp.status_code)

# Test admin route
resp = client.get('/elite-sprint/admin')
print('/elite-sprint/admin: %d' % resp.status_code)
assert resp.status_code == 200, 'Admin route should return 200'
assert b'sprint_start_time' not in resp.data, 'Should not reference sprint_start_time'
assert b'sprint_end_time' not in resp.data, 'Should not reference sprint_end_time'
assert b'now_time' not in resp.data, 'Should not reference now_time'
print('  No broken template variables: OK')

# Test leaderboard route
resp = client.get('/elite-sprint/leaderboard')
print('/elite-sprint/leaderboard: %d' % resp.status_code)
assert resp.status_code == 200, 'Leaderboard route should return 200'

# Test verify route
resp = client.get('/elite-sprint/verify')
print('/elite-sprint/verify: %d' % resp.status_code)
assert resp.status_code == 200, 'Verify route should return 200'

# Test dashboard
resp = client.get('/dashboard/')
print('/dashboard/: %d' % resp.status_code)
assert resp.status_code == 200, 'Dashboard should return 200'

# Test student route
client.get('/logout')
resp = client.get('/login/student')
match = re.search(r'name="csrf_token" value="([^"]+)"', resp.get_data(as_text=True))
token = match.group(1) if match else ''
resp = client.post('/login/student', data={'csrf_token': token, 'email': 'student@test.com', 'password': 'Student@123'}, follow_redirects=True)
print('Student login: %d' % resp.status_code)

resp = client.get('/elite-sprint/student')
print('/elite-sprint/student: %d' % resp.status_code)
assert resp.status_code == 200, 'Student route should return 200'

# Test student submit (POST)
resp = client.get('/elite-sprint/student')
match = re.search(r'name="csrf_token" value="([^"]+)"', resp.get_data(as_text=True))
token = match.group(1) if match else ''
resp = client.post('/elite-sprint/student', data={
    'csrf_token': token,
    'daily_tasks': ['1', '2'],
    'weekly_tasks': ['3', '4'],
    'monthly_tasks': ['5', '6'],
}, follow_redirects=True)
print('Student submit (POST): %d' % resp.status_code)
assert resp.status_code == 200, 'Student submit should return 200'

# Verify the bid was created and locked
with app.app_context():
    s = EliteSprintSession.query.filter_by(sprint_date=today).first()
    stud = User.query.filter_by(email='student@test.com').first()
    bid = EliteSprintBid.query.filter_by(session_id=s.id, student_id=stud.id).first()
    assert bid is not None, 'Bid should exist'
    assert bid.is_locked == True, 'Bid should be locked'
    assert bid.locked_at is not None, 'locked_at should be set'
    assert bid.verification_due_at is not None, 'verification_due_at should be set'
    delta = bid.verification_due_at - bid.locked_at
    assert abs(delta.total_seconds() - 15*3600) < 1, 'verification_due_at should be ~15 hours after locked_at'
    print('  Bid lock: is_locked=%s, locked_at set=%s, verification_due_at set=%s' % (
        bid.is_locked, bid.locked_at is not None, bid.verification_due_at is not None))
    print('  Lock offset: %s hours' % (delta.total_seconds() / 3600))
    
    # Verify student sees locked state
    resp = client.get('/elite-sprint/student')
    html = resp.get_data(as_text=True)
    assert 'Sprint locked until the next sprint session.' in html, 'Should show locked message'
    assert 'Task submission deadline:' in html, 'Should show deadline'
    print('  Locked message + deadline: OK')

# Test leaderboard with data
resp = client.get('/elite-sprint/leaderboard')
print('/elite-sprint/leaderboard (with data): %d' % resp.status_code)
assert resp.status_code == 200, 'Leaderboard should return 200'

# Test verify with data
client.get('/logout')
resp = client.get('/login/admin')
match = re.search(r'name="csrf_token" value="([^"]+)"', resp.get_data(as_text=True))
token = match.group(1) if match else ''
resp = client.post('/login/admin', data={'csrf_token': token, 'email': 'admin@test.com', 'password': 'Admin@123'}, follow_redirects=True)
resp = client.get('/elite-sprint/verify')
print('/elite-sprint/verify (with data): %d' % resp.status_code)
assert resp.status_code == 200, 'Verify route should return 200'

print()
print('ALL CHECKS PASSED')
