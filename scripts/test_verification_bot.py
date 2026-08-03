import tempfile, os, re
from pathlib import Path
from app import create_app, db
from app.models import (
    User, Task, EliteSprintSession, EliteSprintBid,
    EliteSprintBidTask, PointTransaction, Submission,
    SprintVerificationResult,
)
from app.services.elite_sprint import (
    process_expired_sprint_verifications,
    _verify_single_bid,
    get_sprint_leaderboard,
)
from datetime import date, time, datetime, timedelta

class TestConfig:
    SECRET_KEY = 'test-secret'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + str(Path(tempfile.gettempdir()) / 'elite_verify_test.sqlite3')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_TIME_LIMIT = None

db_path = str(Path(tempfile.gettempdir()) / 'elite_verify_test.sqlite3')
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
    
    tasks = []
    for i in range(1, 7):
        task = Task(task_code='T%d' % i, title='Task %d' % i, description='test', reward_points=10, task_type='daily', status='active')
        db.session.add(task)
        tasks.append(task)
    db.session.commit()
    
    # Create a sprint session that ended 20 hours ago
    today = date.today()
    past_date = today - timedelta(days=1)
    session = EliteSprintSession(
        sprint_date=past_date,
        start_time=time(8, 0),
        end_time=time(10, 0),
    )
    db.session.add(session)
    db.session.commit()
    
    # Create a locked bid (past verification deadline)
    # Student bid on tasks 1, 2, 3, 4
    bid = EliteSprintBid(
        session_id=session.id,
        student_id=student.id,
        is_locked=True,
        locked_at=datetime.utcnow() - timedelta(hours=20),
        verification_due_at=datetime.utcnow() - timedelta(hours=5),  # past due
    )
    db.session.add(bid)
    db.session.flush()
    
    for tid in [1, 2, 3, 4]:
        bt = EliteSprintBidTask(bid_id=bid.id, task_id=tid, category='daily')
        db.session.add(bt)
    db.session.commit()
    
    print('Test 1: Student submits tasks 1, 2, 3 but NOT 4 (golden star case)')
    # Student submitted tasks 1, 2, 3 (missing 4)
    for tid in [1, 2, 3]:
        sub = Submission(
            student_id=student.id,
            task_id=tid,
            description='test',
            proof_url='http://example.com',
            status='approved',
            submission_date=past_date,
            submitted_at=datetime.utcnow() - timedelta(hours=10),
        )
        db.session.add(sub)
    db.session.commit()
    
    # Run verification
    process_expired_sprint_verifications()
    
    student2 = User.query.filter_by(email='student@test.com').first()
    bid2 = EliteSprintBid.query.filter_by(session_id=session.id, student_id=student2.id).first()
    
    print('  is_verified: %s' % bid2.is_verified)
    print('  has_golden_star: %s' % bid2.has_golden_star)
    print('  penalty_points: %s' % bid2.penalty_points)
    print('  has_active_sprint_penalty: %s' % student2.has_active_sprint_penalty)
    
    assert bid2.is_verified == True, 'Bid should be verified'
    assert bid2.has_golden_star == False, 'Should not have golden star (missing task 4)'
    assert bid2.penalty_points == 10, 'Should have 10 penalty points (task 4 = 10 points)'
    assert student2.has_active_sprint_penalty == True, 'Student should have active sprint penalty'
    
    # Check PointTransaction
    pt = PointTransaction.query.filter(
        PointTransaction.student_id == student2.id,
        PointTransaction.type == 'penalty',
    ).first()
    assert pt is not None, 'Should have a penalty PointTransaction'
    assert pt.points == -10, 'Points should be -10'
    print('  PointTransaction: points=%s, type=%s' % (pt.points, pt.type))
    
    # Check SprintVerificationResult
    svr = SprintVerificationResult.query.filter_by(session_id=session.id, student_id=student2.id).first()
    assert svr is not None, 'Should have a SprintVerificationResult'
    assert svr.earned_golden_star == False
    print('  SprintVerificationResult: earned_golden_star=%s, penalty_points=%s' % (svr.earned_golden_star, svr.penalty_points))
    
    print()
    print('Test 2: Golden star case (all tasks submitted including extra)')
    # Submit task 4 as well, and task 5 (extra)
    sub4 = Submission(
        student_id=student2.id,
        task_id=4,
        description='test',
        proof_url='http://example.com',
        status='approved',
        submission_date=past_date,
        submitted_at=datetime.utcnow() - timedelta(hours=8),
    )
    sub5 = Submission(
        student_id=student2.id,
        task_id=5,
        description='test extra',
        proof_url='http://example.com',
        status='approved',
        submission_date=past_date,
        submitted_at=datetime.utcnow() - timedelta(hours=8),
    )
    db.session.add(sub4)
    db.session.add(sub5)
    db.session.commit()
    
    # Reset the bid
    bid2.is_verified = False
    bid2.has_golden_star = False
    bid2.penalty_points = 0
    bid2.verified_at = None
    student2.has_active_sprint_penalty = False
    db.session.commit()
    
    # Delete old verification result and point transaction
    db.session.delete(pt)
    db.session.delete(svr)
    db.session.commit()
    
    process_expired_sprint_verifications()
    
    student3 = User.query.filter_by(email='student@test.com').first()
    bid3 = EliteSprintBid.query.filter_by(session_id=session.id, student_id=student3.id).first()
    
    print('  is_verified: %s' % bid3.is_verified)
    print('  has_golden_star: %s' % bid3.has_golden_star)
    print('  golden_stars on student: %s' % student3.golden_stars)
    
    assert bid3.is_verified == True, 'Bid should be verified'
    assert bid3.has_golden_star == True, 'Should have golden star (all tasks submitted)'
    assert student3.golden_stars == 1, 'Student should have 1 golden star'
    
    print()
    print('Test 3: Leaderboard')
    leaderboard = get_sprint_leaderboard()
    print('  Entries: %d' % len(leaderboard))
    for row in leaderboard:
        print('  %s: %s tasks, golden_star=%s, badge=%s' % (row['student_name'], row['total_tasks'], row['golden_star'], row['badge']))
    assert len(leaderboard) >= 1, 'Should have at least 1 entry'
    assert leaderboard[0]['student_name'] == 'Student', 'Should show our student'
    
    print()
    print('ALL VERIFICATION BOT TESTS PASSED')
