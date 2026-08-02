from app import db
from app.models import PointRule, Submission, Task


TASK_CATALOG = {
    "daily": [
        ("TD001", "Programming", "Solve 2 LeetCode/HackerRank problems", 5),
        ("TD002", "GitHub", "Push code/commit", 10),
        ("TD003", "AI Learning", "Learn one AI concept / tool (30 min)", 10),
        ("TD004", "Communication", "Practice English/GD for 20 minutes", 10),
        ("TD005", "Aptitude", "Solve 10 aptitude questions", 5),
        ("TD006", "Technical Reading", "Read one technical article", 5),
        ("TD007", "LinkedIn", "Engage with one technical post", 5),
        ("TD008", "Documentation", "Update project diary/report", 5),
        ("TD009", "Project", "Spend at least 30 minutes on project", 5),
        ("TD010", "Course Progress", "Doing Assessment for each course", 5),
        ("TD011", "Course Progress", "Complete one course module", 40),
        ("TD012", "Assessment", "Pass weekly assessment/quiz", 30),
        ("TD013", "Hands-on Lab", "Complete one lab/activity", 30),
        ("TD014", "Reflection", "Submit course learning summary", 20),
    ],
    "weekly": [
        ("TW001", "Project", "Submit weekly project progress", 40),
        ("TW002", "Prototype", "Prototype/Feature completion", 50),
        ("TW003", "Unit Test", "Complete Weekly Unit Test", 30),
        ("TW004", "Coding", "Maintain 7-day coding streak", 40),
        ("TW005", "GitHub", "Minimum 7 meaningful commits", 30),
        ("TW006", "AI Tools", "Explore one AI tool and submit summary", 25),
        ("TW007", "Research", "Literature survey/technical article", 25),
        ("TW008", "Internship", "Company research & skill mapping", 20),
        ("TW009", "Resume", "Resume improvement", 20),
        ("TW010", "Communication", "GD/Seminar participation", 25),
        ("TW011", "Social Media", "LinkedIn technical post", 15),
        ("TW012", "Documentation", "Weekly report submission", 20),
        ("TW013", "Networking", "Connect with 5 professionals", 15),
        ("TW014", "Startup", "Startup case study analysis", 20),
        ("TW015", "Course Progress", "Completing & getting sign for 1 lab experiment per course", 5),
        ("TW016", "Skill", "Clearing atleast 1-core or programming skill, 1- aptitude,1-communication", 50),
        ("TW017", "Activity", "Individual Activity Points - Solving ELITE problems", 50),
        ("TW018", "Group Activity", "Each Person", 50),
    ],
    "monthly": [
        ("TM001", "Achievement", "Winning Badges in Leetcode", 100),
        ("TM002", "Achievement", "Winning Top % above 75-80", 50),
        ("TM003", "Achievement", "Winning Top % above 80", 100),
        ("TM004", "Achievement", "Winning Grant Amount", 1000),
        ("TM005", "Achievement", "Participating One Hackathons", 50),
        ("TM006", "Achievement", "Participation & Winning in Hackathons", 100),
        ("TM007", "project", "Functional prototype/demo", 150),
        ("TM008", "Competition", "Participate in Hackathon/Contest", 100),
        ("TM009", "Achievement", "Win/Shortlist in competition", 200),
        ("TM010", "Certification", "Complete certification", 150),
        ("TM011", "Research", "Submit paper/article", 200),
        ("TM012", "GitHub", "30-day contribution streak", 100),
        ("TM013", "LeetCode", "Solve 100 problems", 150),
        ("TM014", "Placement", "Complete Mock Interview", 75),
        ("TM015", "Internship", "Internship/Training completed", 200),
        ("TM016", "Branding", "Publish 4 LinkedIn posts", 50),
        ("TM017", "AI", "Complete AI mini-project", 150),
        ("TM018", "Patent", "Patent disclosure submission", 300),
        ("TM019", "Funding", "Submit proposal", 200),
        ("TM020", "LeetCode", "30 -days streak maintenance", 50),
    ],
}


BONUS_RULES = [
    ("BONUS001", "Achievement", "Daily Top Performer", 20),
    ("BONUS002", "Achievement", "Weekly Top Performer", 75),
    ("BONUS003", "Achievement", "Monthly Top Performer", 200),
    ("BONUS004", "Achievement", "30-Day Attendance", 50),
    ("BONUS005", "Achievement", "Helping another ELITE member", 20),
    ("BONUS006", "Achievement", "Conducting a technical session", 50),
    ("BONUS007", "Achievement", "Open Source Contribution", 100),
    ("BONUS008", "Achievement", "Paper Accepted", 300),
    ("BONUS009", "Achievement", "Patent Published", 500),
    ("BONUS010", "Achievement", "Internship Offer", 300),
    ("BONUS011", "Achievement", "Placement Offer (>10 LPA)", 500),
]


PENALTY_RULES = [
    ("PENALTY001", "Activity", "Daily task not updated", -5),
    ("PENALTY002", "Activity", "Weekly target missed", -20),
    ("PENALTY003", "Activity", "Monthly review absent", -50),
    ("PENALTY004", "Activity", "Plagiarism", -100),
    ("PENALTY005", "Activity", "Fake submission", -150),
    ("PENALTY006", "Activity", "Missing project review", -50),
]


LEVEL_RULES = [
    ("LEVEL001", "Level", "0-500: Beginner", 0),
    ("LEVEL002", "Level", "501-1,500: Explorer", 501),
    ("LEVEL003", "Level", "1,501-3,000: Innovator", 1501),
    ("LEVEL004", "Level", "3,001-5,000: AI Professional", 3001),
    ("LEVEL005", "Level", "5,001-8,000: ELITE Achiever", 5001),
    ("LEVEL006", "Level", "8,001-12,000: ELITE Champion", 8001),
    ("LEVEL007", "Level", "Above 12,000: Hall of Fame", 12001),
]


def seed_task_catalog(created_by=None):
    remove_trial_tasks()

    for stream, rows in TASK_CATALOG.items():
        for code, category, title, points in rows:
            task = Task.query.filter_by(task_code=code).first()
            if task is None:
                task = Task(task_code=code)
                db.session.add(task)
            task.category = category
            task.title = title
            task.description = title
            task.instructions = "Upload proof of completion for admin approval."
            task.reference_links = ""
            task.reward_points = points
            task.task_type = stream
            task.status = "active"
            task.start_at = None
            task.due_at = None
            task.deadline_at = None
            if created_by and not task.created_by:
                task.created_by = created_by

    for stream, rows in {
        "bonus": BONUS_RULES,
        "penalty": PENALTY_RULES,
        "level": LEVEL_RULES,
    }.items():
        for code, category, title, points in rows:
            rule = PointRule.query.filter_by(code=code).first()
            if rule is None:
                rule = PointRule(code=code)
                db.session.add(rule)
            rule.stream = stream
            rule.category = category
            rule.title = title
            rule.points = points

    db.session.commit()


def remove_trial_tasks():
    trial_titles = {
        "Backend Smoke Test Task",
        "Trial Task",
        "Test Task",
        "Submit the leetcode proof of weekly contest",
    }
    trial_tasks = Task.query.filter(Task.title.in_(trial_titles)).all()
    for task in trial_tasks:
        Submission.query.filter_by(task_id=task.id).delete()
        db.session.delete(task)
