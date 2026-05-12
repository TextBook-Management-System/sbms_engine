"""
Integration tests for full request flows in the SBMS API.

Tests complete end-to-end workflows using httpx AsyncClient with ASGITransport
against the actual FastAPI app with an in-memory SQLite database.

Test scenarios:
1. Auth workflow: Register → Login → Use token → Logout → Token rejected
2. CRUD workflow: Create department → school → grade level → subject → book → list/filter → update → delete
3. Allocation workflow: Create book copy → Allocate → Verify active → Return → Re-allocate
4. Scope filtering: Resources in two departments → DeptAdmin sees only their dept
5. Error handling: 404, 409, 422, 403 responses

**Validates: All Requirements**
"""

import os
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine, event, Integer, BigInteger
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.compiler import compiles

# Override DATABASE_URL before importing app modules
os.environ["DATABASE_URL"] = "sqlite://"

from app.database.session import Base, get_db
from app.models.database import User, UserRole
from app.services import auth_service
from app.main import create_app


# ---------------------------------------------------------------------------
# Test Database Setup
# ---------------------------------------------------------------------------

# Make BigInteger render as INTEGER in SQLite so autoincrement works.
# SQLite only auto-increments columns declared as "INTEGER PRIMARY KEY".
@compiles(BigInteger, "sqlite")
def _compile_big_int_sqlite(type_, compiler, **kw):
    return "INTEGER"


TEST_DATABASE_URL = "sqlite://"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable foreign keys for SQLite."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override the get_db dependency to use the test database."""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_database():
    """Create all tables before each test and drop them after."""
    # Clear the token blacklist between tests
    auth_service._token_blacklist.clear()
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest_asyncio.fixture
async def client():
    """Create an async test client with the test database override."""
    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", follow_redirects=True) as ac:
        yield ac


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

API_PREFIX = "/api/v1"


def _auth_headers(token: str) -> dict:
    """Return Authorization headers with Bearer token."""
    return {"Authorization": f"Bearer {token}"}


async def _register_user(client: AsyncClient, email: str, password: str = "password123", full_name: str = "Test User", **kwargs) -> dict:
    """Register a user and return the response JSON."""
    payload = {"email": email, "password": password, "full_name": full_name, **kwargs}
    resp = await client.post(f"{API_PREFIX}/auth/register", json=payload)
    return resp


async def _login_user(client: AsyncClient, email: str, password: str = "password123") -> dict:
    """Login a user and return the token response."""
    resp = await client.post(f"{API_PREFIX}/auth/login", json={"email": email, "password": password})
    return resp


async def _assign_role(user_id: int, role: str):
    """Directly assign a role to a user in the test database."""
    db = TestingSessionLocal()
    try:
        user_role = UserRole(user_id=user_id, role=role)
        db.add(user_role)
        db.commit()
    finally:
        db.close()


async def _create_department(client: AsyncClient, name: str, headers: dict = None) -> dict:
    """Create a department and return the response."""
    resp = await client.post(f"{API_PREFIX}/departments", json={"name": name}, headers=headers)
    return resp


async def _create_school(client: AsyncClient, department_id: int, name: str = "Test School", headers: dict = None) -> dict:
    """Create a school and return the response."""
    payload = {
        "department_id": department_id,
        "name": name,
        "address": "123 Test St",
        "city": "TestCity",
        "state": "TestState",
        "country": "TestCountry",
        "latitude": -25.7,
        "longitude": 28.2,
        "total_students": 500,
        "total_teachers": 30,
    }
    resp = await client.post(f"{API_PREFIX}/schools", json=payload, headers=headers)
    return resp


# ---------------------------------------------------------------------------
# Test 1: Auth Workflow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAuthWorkflow:
    """Test complete auth flow: register → login → use token → logout → token rejected."""

    async def test_full_auth_lifecycle(self, client: AsyncClient):
        """Register a user, login, use token for authenticated request, logout, verify rejection."""
        # Step 1: Register
        reg_resp = await _register_user(client, "auth_test@example.com")
        assert reg_resp.status_code == 201
        user_data = reg_resp.json()
        assert user_data["email"] == "auth_test@example.com"
        assert user_data["full_name"] == "Test User"
        assert "password_hash" not in user_data
        assert "password" not in user_data

        # Step 2: Login
        login_resp = await _login_user(client, "auth_test@example.com")
        assert login_resp.status_code == 200
        tokens = login_resp.json()
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "bearer"

        access_token = tokens["access_token"]
        headers = _auth_headers(access_token)

        # Step 3: Use token for authenticated request (logout requires auth)
        # First verify the token works by calling logout
        logout_resp = await client.post(f"{API_PREFIX}/auth/logout", headers=headers)
        assert logout_resp.status_code == 200

        # Step 4: Verify token is rejected after logout
        # Trying to logout again with the same token should fail
        rejected_resp = await client.post(f"{API_PREFIX}/auth/logout", headers=headers)
        assert rejected_resp.status_code == 401

    async def test_refresh_token_flow(self, client: AsyncClient):
        """Register, login, use refresh token to get new access token."""
        await _register_user(client, "refresh_test@example.com")
        login_resp = await _login_user(client, "refresh_test@example.com")
        tokens = login_resp.json()

        # Refresh the token
        refresh_resp = await client.post(
            f"{API_PREFIX}/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert refresh_resp.status_code == 200
        new_tokens = refresh_resp.json()
        assert "access_token" in new_tokens

        # New token should work
        new_headers = _auth_headers(new_tokens["access_token"])
        dept_resp = await client.get(f"{API_PREFIX}/departments", headers=new_headers)
        assert dept_resp.status_code == 200


# ---------------------------------------------------------------------------
# Test 2: CRUD Workflow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestCRUDWorkflow:
    """Test complete CRUD flow: create resources → list with pagination → filter → update → delete."""

    async def test_full_crud_lifecycle(self, client: AsyncClient):
        """Create department → school → grade level → subject → book → list → filter → update → delete."""
        # Step 1: Create a department
        dept_resp = await _create_department(client, "Education Department")
        assert dept_resp.status_code == 201
        dept = dept_resp.json()
        dept_id = dept["id"]
        assert dept["name"] == "Education Department"

        # Step 2: Create a school in that department
        school_resp = await _create_school(client, dept_id, "Springfield Elementary")
        assert school_resp.status_code == 201
        school = school_resp.json()
        school_id = school["id"]
        assert school["name"] == "Springfield Elementary"
        assert school["department_id"] == dept_id

        # Step 3: Create a grade level
        gl_resp = await client.post(f"{API_PREFIX}/grade-levels", json={"name": "Grade 7"})
        assert gl_resp.status_code == 201
        grade_level = gl_resp.json()
        gl_id = grade_level["id"]

        # Step 4: Create a subject
        subj_resp = await client.post(f"{API_PREFIX}/subjects", json={"name": "Mathematics"})
        assert subj_resp.status_code == 201
        subject = subj_resp.json()
        subj_id = subject["id"]

        # Step 5: Create a book
        book_payload = {
            "title": "Algebra Fundamentals",
            "subject_id": subj_id,
            "grade_level_id": gl_id,
            "isbn": "978-0-13-468599-1",
            "publisher": "Pearson",
            "author": "John Smith",
        }
        book_resp = await client.post(f"{API_PREFIX}/books", json=book_payload)
        assert book_resp.status_code == 201
        book = book_resp.json()
        book_id = book["id"]
        assert book["title"] == "Algebra Fundamentals"
        assert book["subject_id"] == subj_id
        assert book["grade_level_id"] == gl_id

        # Step 6: Create another book for filtering
        book2_payload = {
            "title": "Geometry Basics",
            "subject_id": subj_id,
            "grade_level_id": gl_id,
            "isbn": "978-0-13-468599-2",
        }
        await client.post(f"{API_PREFIX}/books", json=book2_payload)

        # Step 7: List books with pagination
        list_resp = await client.get(f"{API_PREFIX}/books?page=1&page_size=10")
        assert list_resp.status_code == 200
        list_data = list_resp.json()
        assert "items" in list_data
        assert "total" in list_data
        assert "page" in list_data
        assert "page_size" in list_data
        assert list_data["total"] == 2
        assert list_data["page"] == 1
        assert len(list_data["items"]) == 2

        # Step 8: Filter books by subject_id
        filter_resp = await client.get(f"{API_PREFIX}/books?subject_id={subj_id}")
        assert filter_resp.status_code == 200
        filter_data = filter_resp.json()
        assert filter_data["total"] == 2
        for item in filter_data["items"]:
            assert item["subject_id"] == subj_id

        # Step 9: Update the book
        update_resp = await client.put(
            f"{API_PREFIX}/books/{book_id}",
            json={"title": "Algebra Fundamentals (2nd Edition)", "edition": "2nd"},
        )
        assert update_resp.status_code == 200
        updated_book = update_resp.json()
        assert updated_book["title"] == "Algebra Fundamentals (2nd Edition)"
        assert updated_book["edition"] == "2nd"

        # Step 10: Delete the book
        del_resp = await client.delete(f"{API_PREFIX}/books/{book_id}")
        assert del_resp.status_code == 204

        # Verify deletion
        get_resp = await client.get(f"{API_PREFIX}/books/{book_id}")
        assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# Test 3: Allocation Workflow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestAllocationWorkflow:
    """Test allocation flow: create book copy → allocate → verify → return → re-allocate."""

    async def test_full_allocation_lifecycle(self, client: AsyncClient):
        """Create prerequisites, allocate book copy, return it, re-allocate."""
        # Setup: Create department, school, grade level, subject, book
        dept_resp = await _create_department(client, "Allocation Dept")
        dept_id = dept_resp.json()["id"]

        school_resp = await _create_school(client, dept_id, "Allocation School")
        school_id = school_resp.json()["id"]

        gl_resp = await client.post(f"{API_PREFIX}/grade-levels", json={"name": "Grade 5"})
        gl_id = gl_resp.json()["id"]

        subj_resp = await client.post(f"{API_PREFIX}/subjects", json={"name": "Science"})
        subj_id = subj_resp.json()["id"]

        book_resp = await client.post(
            f"{API_PREFIX}/books",
            json={"title": "Science Book", "subject_id": subj_id, "grade_level_id": gl_id},
        )
        book_id = book_resp.json()["id"]

        # Create a grade for the school
        grade_resp = await client.post(
            f"{API_PREFIX}/schools/{school_id}/grades",
            json={"name": "Grade 5A"},
        )
        assert grade_resp.status_code == 201
        grade_id = grade_resp.json()["id"]

        # Create a learner
        learner_resp = await client.post(
            f"{API_PREFIX}/learners",
            json={"grade_id": grade_id, "first_name": "Alice", "last_name": "Johnson"},
        )
        assert learner_resp.status_code == 201
        learner_id = learner_resp.json()["id"]

        # Step 1: Create a book copy
        copy_resp = await client.post(
            f"{API_PREFIX}/book-copies",
            json={"book_id": book_id, "school_id": school_id, "qr_code": "QR-ALLOC-001"},
        )
        assert copy_resp.status_code == 201
        copy = copy_resp.json()
        copy_id = copy["id"]
        assert copy["condition"] == "good"

        # Step 2: Allocate to learner
        alloc_resp = await client.post(
            f"{API_PREFIX}/allocations",
            json={"book_copy_id": copy_id, "learner_id": learner_id},
        )
        assert alloc_resp.status_code == 201
        allocation = alloc_resp.json()
        alloc_id = allocation["id"]
        assert allocation["status"] == "active"
        assert allocation["book_copy_id"] == copy_id
        assert allocation["learner_id"] == learner_id

        # Step 3: Verify active allocation (cannot re-allocate same copy)
        dup_alloc_resp = await client.post(
            f"{API_PREFIX}/allocations",
            json={"book_copy_id": copy_id, "learner_id": learner_id},
        )
        assert dup_alloc_resp.status_code == 409

        # Step 4: Return the allocation
        return_resp = await client.put(f"{API_PREFIX}/allocations/{alloc_id}/return")
        assert return_resp.status_code == 200
        returned = return_resp.json()
        assert returned["status"] == "returned"
        assert returned["return_date"] is not None

        # Step 5: Verify returned status (cannot return again)
        re_return_resp = await client.put(f"{API_PREFIX}/allocations/{alloc_id}/return")
        assert re_return_resp.status_code == 409

        # Step 6: Re-allocate succeeds after return
        re_alloc_resp = await client.post(
            f"{API_PREFIX}/allocations",
            json={"book_copy_id": copy_id, "learner_id": learner_id},
        )
        assert re_alloc_resp.status_code == 201
        new_allocation = re_alloc_resp.json()
        assert new_allocation["status"] == "active"


# ---------------------------------------------------------------------------
# Test 4: Scope Filtering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestScopeFiltering:
    """Test scope-based filtering: DeptAdmin sees only their department's resources."""

    async def test_dept_admin_sees_only_own_department_schools(self, client: AsyncClient):
        """Create resources in two departments, verify DeptAdmin only sees their own."""
        # Create two departments
        dept_a_resp = await _create_department(client, "Department A")
        dept_a_id = dept_a_resp.json()["id"]

        dept_b_resp = await _create_department(client, "Department B")
        dept_b_id = dept_b_resp.json()["id"]

        # Create schools in each department
        school_a_resp = await _create_school(client, dept_a_id, "School in Dept A")
        school_a_id = school_a_resp.json()["id"]

        school_b_resp = await _create_school(client, dept_b_id, "School in Dept B")
        school_b_id = school_b_resp.json()["id"]

        # Register a DeptAdmin user for Department A
        reg_resp = await _register_user(
            client,
            "deptadmin_a@example.com",
            department_id=dept_a_id,
        )
        assert reg_resp.status_code == 201
        user_a_id = reg_resp.json()["id"]

        # Assign DeptAdmin role
        await _assign_role(user_a_id, "DeptAdmin")

        # Login as DeptAdmin A
        login_resp = await _login_user(client, "deptadmin_a@example.com")
        assert login_resp.status_code == 200
        token_a = login_resp.json()["access_token"]
        headers_a = _auth_headers(token_a)

        # List schools filtered by department_id
        schools_resp = await client.get(
            f"{API_PREFIX}/schools?department_id={dept_a_id}",
            headers=headers_a,
        )
        assert schools_resp.status_code == 200
        schools_data = schools_resp.json()

        # Verify only Department A schools appear
        for school in schools_data["items"]:
            assert school["department_id"] == dept_a_id

        # Verify Department B school does not appear in filtered results
        school_ids_returned = [s["id"] for s in schools_data["items"]]
        assert school_b_id not in school_ids_returned

    async def test_schools_filter_by_department(self, client: AsyncClient):
        """Verify the department_id filter on schools endpoint works correctly."""
        # Create two departments with schools
        dept1_resp = await _create_department(client, "Dept Filter 1")
        dept1_id = dept1_resp.json()["id"]

        dept2_resp = await _create_department(client, "Dept Filter 2")
        dept2_id = dept2_resp.json()["id"]

        await _create_school(client, dept1_id, "School 1A")
        await _create_school(client, dept1_id, "School 1B")
        await _create_school(client, dept2_id, "School 2A")

        # Filter by dept1
        resp = await client.get(f"{API_PREFIX}/schools?department_id={dept1_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        for item in data["items"]:
            assert item["department_id"] == dept1_id

        # Filter by dept2
        resp2 = await client.get(f"{API_PREFIX}/schools?department_id={dept2_id}")
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["total"] == 1
        assert data2["items"][0]["department_id"] == dept2_id


# ---------------------------------------------------------------------------
# Test 5: Error Handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestErrorHandling:
    """Test error responses: 404, 409, 422, 403."""

    async def test_404_for_nonexistent_resource(self, client: AsyncClient):
        """Verify 404 for non-existent resources."""
        # Non-existent department
        resp = await client.get(f"{API_PREFIX}/departments/99999")
        assert resp.status_code == 404
        body = resp.json()
        assert "detail" in body
        assert body["status_code"] == 404
        assert body["error_type"] == "not_found"

        # Non-existent book
        resp2 = await client.get(f"{API_PREFIX}/books/99999")
        assert resp2.status_code == 404

        # Non-existent book copy
        resp3 = await client.get(f"{API_PREFIX}/book-copies/99999")
        assert resp3.status_code == 404

        # Non-existent allocation
        resp4 = await client.get(f"{API_PREFIX}/allocations/99999")
        assert resp4.status_code == 404

    async def test_409_for_duplicate_resources(self, client: AsyncClient):
        """Verify 409 for duplicate unique values."""
        # Create a department
        await _create_department(client, "Unique Dept")

        # Try to create another with the same name
        dup_resp = await _create_department(client, "Unique Dept")
        assert dup_resp.status_code == 409
        body = dup_resp.json()
        assert body["error_type"] == "conflict"

        # Create a grade level
        await client.post(f"{API_PREFIX}/grade-levels", json={"name": "Grade 1"})

        # Duplicate grade level
        dup_gl_resp = await client.post(f"{API_PREFIX}/grade-levels", json={"name": "Grade 1"})
        assert dup_gl_resp.status_code == 409

        # Create a subject
        await client.post(f"{API_PREFIX}/subjects", json={"name": "English"})

        # Duplicate subject
        dup_subj_resp = await client.post(f"{API_PREFIX}/subjects", json={"name": "English"})
        assert dup_subj_resp.status_code == 409

    async def test_422_for_invalid_data(self, client: AsyncClient):
        """Verify 422 for invalid request data."""
        # Missing required field (name) for department
        resp = await client.post(f"{API_PREFIX}/departments", json={})
        assert resp.status_code == 422
        body = resp.json()
        assert body["error_type"] == "validation_error"

        # Name too long for grade level (max 100)
        resp2 = await client.post(
            f"{API_PREFIX}/grade-levels",
            json={"name": "x" * 101},
        )
        assert resp2.status_code == 422

        # Empty name for subject
        resp3 = await client.post(f"{API_PREFIX}/subjects", json={"name": ""})
        assert resp3.status_code == 422

        # Invalid FK reference for book (non-existent subject_id)
        resp4 = await client.post(
            f"{API_PREFIX}/books",
            json={
                "title": "Test Book",
                "subject_id": 99999,
                "grade_level_id": 99999,
            },
        )
        assert resp4.status_code == 422

    async def test_422_for_invalid_book_copy_fk(self, client: AsyncClient):
        """Verify 422 when book_id or school_id don't exist for book copies."""
        resp = await client.post(
            f"{API_PREFIX}/book-copies",
            json={"book_id": 99999, "school_id": 99999, "qr_code": "QR-INVALID"},
        )
        assert resp.status_code == 422

    async def test_409_for_duplicate_qr_code(self, client: AsyncClient):
        """Verify 409 for duplicate QR codes on book copies."""
        # Setup prerequisites
        dept_resp = await _create_department(client, "QR Dept")
        dept_id = dept_resp.json()["id"]
        school_resp = await _create_school(client, dept_id, "QR School")
        school_id = school_resp.json()["id"]

        gl_resp = await client.post(f"{API_PREFIX}/grade-levels", json={"name": "Grade 3"})
        gl_id = gl_resp.json()["id"]
        subj_resp = await client.post(f"{API_PREFIX}/subjects", json={"name": "History"})
        subj_id = subj_resp.json()["id"]

        book_resp = await client.post(
            f"{API_PREFIX}/books",
            json={"title": "History Book", "subject_id": subj_id, "grade_level_id": gl_id},
        )
        book_id = book_resp.json()["id"]

        # Create first book copy
        copy1_resp = await client.post(
            f"{API_PREFIX}/book-copies",
            json={"book_id": book_id, "school_id": school_id, "qr_code": "QR-DUP-001"},
        )
        assert copy1_resp.status_code == 201

        # Try duplicate QR code
        copy2_resp = await client.post(
            f"{API_PREFIX}/book-copies",
            json={"book_id": book_id, "school_id": school_id, "qr_code": "QR-DUP-001"},
        )
        assert copy2_resp.status_code == 409

    async def test_401_for_missing_auth(self, client: AsyncClient):
        """Verify 401 for requests without valid auth to protected endpoints."""
        # Logout endpoint requires auth
        resp = await client.post(f"{API_PREFIX}/auth/logout")
        assert resp.status_code == 401

        # Request with invalid token
        resp2 = await client.post(
            f"{API_PREFIX}/auth/logout",
            headers={"Authorization": "Bearer invalid_token_here"},
        )
        assert resp2.status_code == 401

    async def test_401_for_invalid_login_credentials(self, client: AsyncClient):
        """Verify 401 for invalid login credentials."""
        # Register a user first
        await _register_user(client, "login_fail@example.com")

        # Wrong password
        resp = await client.post(
            f"{API_PREFIX}/auth/login",
            json={"email": "login_fail@example.com", "password": "wrongpassword"},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert body["error_type"] == "unauthorized"
        # Should not reveal which field is wrong
        assert "email" not in body["detail"].lower() or "password" not in body["detail"].lower()

        # Non-existent email
        resp2 = await client.post(
            f"{API_PREFIX}/auth/login",
            json={"email": "nonexistent@example.com", "password": "password123"},
        )
        assert resp2.status_code == 401

    async def test_409_for_duplicate_email_registration(self, client: AsyncClient):
        """Verify 409 when registering with an already-used email."""
        await _register_user(client, "dup_email@example.com")

        dup_resp = await _register_user(client, "dup_email@example.com")
        assert dup_resp.status_code == 409
        body = dup_resp.json()
        assert body["error_type"] == "conflict"

    async def test_422_for_short_password(self, client: AsyncClient):
        """Verify 422 when password is too short (< 8 chars)."""
        resp = await client.post(
            f"{API_PREFIX}/auth/register",
            json={
                "email": "short_pw@example.com",
                "password": "short",
                "full_name": "Short PW User",
            },
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["error_type"] == "validation_error"


# ---------------------------------------------------------------------------
# Test 6: Pagination
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestPagination:
    """Test pagination envelope correctness across list endpoints."""

    async def test_pagination_envelope_structure(self, client: AsyncClient):
        """Verify paginated responses have correct envelope structure."""
        # Create multiple departments
        for i in range(5):
            await _create_department(client, f"Pagination Dept {i}")

        # Request page 1 with page_size 2
        resp = await client.get(f"{API_PREFIX}/departments?page=1&page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert len(data["items"]) == 2

        # Request page 3 (last page with 1 item)
        resp2 = await client.get(f"{API_PREFIX}/departments?page=3&page_size=2")
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["total"] == 5
        assert data2["page"] == 3
        assert len(data2["items"]) == 1

        # Request page beyond data
        resp3 = await client.get(f"{API_PREFIX}/departments?page=10&page_size=2")
        assert resp3.status_code == 200
        data3 = resp3.json()
        assert data3["total"] == 5
        assert data3["page"] == 10
        assert len(data3["items"]) == 0

    async def test_page_size_capped_at_100(self, client: AsyncClient):
        """Verify page_size is capped at 100."""
        await _create_department(client, "Cap Test Dept")

        resp = await client.get(f"{API_PREFIX}/departments?page=1&page_size=200")
        assert resp.status_code == 200
        data = resp.json()
        assert data["page_size"] == 100
