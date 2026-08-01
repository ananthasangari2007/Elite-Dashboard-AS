import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import create_app


def csrf_token(html):
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, html[:500]
    return match.group(1)


def login(client, portal, email, password):
    response = client.get(f"/login/{portal}")
    token = csrf_token(response.get_data(as_text=True))
    return client.post(
        f"/login/{portal}",
        data={"csrf_token": token, "email": email, "password": password},
        follow_redirects=True,
    )


def main():
    app = create_app()
    app.config["WTF_CSRF_TIME_LIMIT"] = None
    client = app.test_client()

    assert client.get("/").status_code == 200
    login(client, "admin", "admin@elite.edu", "Admin@123")
    admin_pages = [
        "/dashboard/",
        "/students/",
        "/tasks/",
        "/tasks/daily",
        "/tasks/weekly",
        "/tasks/monthly",
        "/submissions/pending",
        "/support/admin",
        "/exports/excel",
    ]
    for page in admin_pages:
        assert client.get(page).status_code == 200, page

    client.get("/logout")
    login(client, "student", "student@elite.edu", "Student@123")
    student_pages = ["/dashboard/", "/tasks/", "/submissions/status", "/support/contact", "/profile/"]
    for page in student_pages:
        assert client.get(page, follow_redirects=True).status_code == 200, page

    print("pages-ok")


if __name__ == "__main__":
    main()
