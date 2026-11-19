"""Flask GUI tests against the real MySQL test database."""
import re

import pytest

from xfactor.repository.crud import MODELS
from xfactor.web import create_app


@pytest.fixture()
def client(loaded_db):
    app = create_app()
    app.config.update(TESTING=True, EDIT_PASSWORD=None)
    return app.test_client()


def _csrf(client, path="/"):
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([0-9a-f]+)"', html).group(1)


@pytest.mark.parametrize("path", [
    "/", "/views/v_series_summary", "/views/v_performance_detail?series=6", "/views/v_mentor_stats",
    "/procedures", "/procedures?proc=leaderboard&series=3", "/procedures?proc=journey&act=JLS",
    "/reports/mentor-songs?mentor=Walsh", "/ask", "/login",
])
def test_pages_render(client, path):
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("table", sorted(MODELS))
def test_every_table_lists_and_has_forms(client, table):
    listing = client.get(f"/tables/{table}")
    assert listing.status_code == 200
    assert client.get(f"/tables/{table}/new").status_code == 200
    first_edit = re.search(rf'href="/tables/{table}/([^"/]+)/edit"', listing.get_data(as_text=True))
    assert first_edit, "listing should link to an edit form"
    assert client.get(f"/tables/{table}/{first_edit.group(1)}/edit").status_code == 200


def test_unknown_table_404(client):
    assert client.get("/tables/mysql_user").status_code == 404


def test_crud_through_forms(client):
    token = _csrf(client, "/tables/hometown/new")
    created = client.post("/tables/hometown/new", data={"csrf_token": token, "name": "Testville"},
                          follow_redirects=True)
    assert "Created hometown" in created.get_data(as_text=True)
    page = client.get("/tables/hometown?q=Testville").get_data(as_text=True)
    pk = re.search(r'/tables/hometown/(\d+)/edit', page).group(1)
    updated = client.post(f"/tables/hometown/{pk}/edit", data={"csrf_token": token, "name": "Testburg"},
                          follow_redirects=True)
    assert "Updated hometown" in updated.get_data(as_text=True)
    deleted = client.post(f"/tables/hometown/{pk}/delete", data={"csrf_token": token}, follow_redirects=True)
    assert "Deleted hometown" in deleted.get_data(as_text=True)


def test_constraint_violation_is_shown_not_crashed(client):
    token = _csrf(client, "/tables/series/new")
    response = client.post("/tables/series/new", data={"csrf_token": token, "series_number": "150"})
    assert response.status_code == 200
    assert "CHECK constraint" in response.get_data(as_text=True)
    dup = client.post("/tables/category/new", data={"csrf_token": token, "name": "Boys"})
    assert "UNIQUE constraint" in dup.get_data(as_text=True)


def test_post_without_csrf_is_rejected(client):
    assert client.post("/tables/hometown/new", data={"name": "Nope"}).status_code == 400


def test_edit_password_gates_writes(loaded_db):
    app = create_app()
    app.config.update(TESTING=True, EDIT_PASSWORD="s3cret")
    client = app.test_client()
    assert client.get("/tables/act/new").status_code == 302
    token = _csrf(client, "/login")
    bad = client.post("/login", data={"csrf_token": token, "password": "wrong"})
    assert "Wrong password" in bad.get_data(as_text=True)
    client.post("/login", data={"csrf_token": token, "password": "s3cret"})
    assert client.get("/tables/act/new").status_code == 200


def test_login_redirect_rejects_external_urls(loaded_db):
    app = create_app()
    app.config.update(TESTING=True, EDIT_PASSWORD="pw")
    client = app.test_client()
    token = _csrf(client, "/login")
    response = client.post("/login?next=//evil.example", data={"csrf_token": token, "password": "pw"})
    assert response.headers["Location"] == "/"
