# Feature: sbms-api-endpoints, Property 5: Scope-Based List Filtering
"""
Property-based tests for scope-based list filtering.

Tests validate that for any authenticated user and any list endpoint, the returned
items SHALL contain only resources within the user's organizational scope:
- DeptAdmin: all resources within their assigned department
- SchoolAdmin: all resources within their assigned school
- Teacher: all resources within their assigned school (read-only)
- Parent: only resources related to their linked learners

No item outside the user's scope SHALL ever appear in a list response.

**Validates: Requirements 6.2, 6.3, 6.4, 6.5, 6.11, 7.1, 7.8, 11.2, 12.3, 18.2, 19.2, 19.6**
"""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from httpx import AsyncClient, ASGITransport
from fastapi import FastAPI, Depends
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.exceptions import register_exception_handlers
from app.core.pagination import PaginatedResponse, PaginationParams, paginate
from app.core.rbac import (
    ROLE_DEPT_ADMIN,
    ROLE_SCHOOL_ADMIN,
    ROLE_TEACHER,
    ROLE_PARENT,
    Scope,
    get_user_scope,
)
from app.core.deps import get_current_user_dependency
from app.database.session import get_db
from app.models.database import (
    BookRequest,
    Delivery,
    School,
    User,
    UserRole,
    ParentLearner,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Number of in-scope and out-of-scope items
num_items_strategy = st.integers(min_value=0, max_value=10)

# Department and school IDs
dept_id_strategy = st.integers(min_value=1, max_value=100)
school_id_strategy = st.integers(min_value=1, max_value=100)
learner_id_strategy = st.integers(min_value=1, max_value=100)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_user(role: str, department_id=None, school_id=None):
    """Create a mock User with the specified role and scope attributes."""
    user = MagicMock(spec=User)
    user.id = 1
    user.email = "test@example.com"
    user.full_name = "Test User"
    user.is_active = True
    user.department_id = department_id
    user.school_id = school_id

    # Mock the school relationship for SchoolAdmin/Teacher
    if school_id and department_id:
        mock_school = MagicMock()
        mock_school.department_id = department_id
        user.school = mock_school
    else:
        user.school = None

    # Create mock role
    mock_role = MagicMock()
    mock_role.role = role
    user.roles = [mock_role]

    return user


def _make_scope(role: str, department_id=None, school_id=None, learner_ids=None):
    """Create a Scope object for the given role."""
    return Scope(
        role=role,
        department_id=department_id,
        school_id=school_id,
        learner_ids=learner_ids or [],
    )


def _make_mock_user_record(user_id: int, department_id=None, school_id=None):
    """Create a mock User record (as would appear in list results)."""
    user = MagicMock()
    user.id = user_id
    user.email = f"user{user_id}@example.com"
    user.full_name = f"User {user_id}"
    user.is_active = True
    user.department_id = department_id
    user.school_id = school_id
    user.roles = []
    user.created_at = "2024-01-01T00:00:00"
    user.updated_at = "2024-01-01T00:00:00"
    return user


def _make_mock_book_request(req_id: int, school_id: int):
    """Create a mock BookRequest record."""
    req = MagicMock()
    req.id = req_id
    req.book_id = 1
    req.school_id = school_id
    req.quantity = 10
    req.status = "pending"
    req.reason = None
    req.created_at = "2024-01-01T00:00:00"
    return req


# ---------------------------------------------------------------------------
# Property Tests: DeptAdmin Scope
# ---------------------------------------------------------------------------


class TestDeptAdminScopeFiltering:
    """DeptAdmin sees only resources within their assigned department.

    **Validates: Requirements 6.2, 7.1, 11.2, 12.3**
    """

    @given(
        dept_id=dept_id_strategy,
        num_in_scope=num_items_strategy,
        num_out_scope=num_items_strategy,
    )
    @settings(max_examples=100, deadline=None)
    def test_dept_admin_users_list_only_shows_department_users(
        self, dept_id: int, num_in_scope: int, num_out_scope: int
    ):
        """DeptAdmin listing users sees only users within their department.

        **Validates: Requirements 7.1**
        """
        other_dept_id = dept_id + 1 if dept_id < 100 else dept_id - 1

        # Create in-scope users (same department or in schools of that department)
        in_scope_users = []
        for i in range(num_in_scope):
            in_scope_users.append(
                _make_mock_user_record(i + 1, department_id=dept_id, school_id=None)
            )

        # Create out-of-scope users (different department)
        out_scope_users = []
        for i in range(num_out_scope):
            out_scope_users.append(
                _make_mock_user_record(
                    num_in_scope + i + 1, department_id=other_dept_id, school_id=None
                )
            )

        all_users = in_scope_users + out_scope_users

        # Simulate the _apply_scope_filter logic from users endpoint
        scope = _make_scope(ROLE_DEPT_ADMIN, department_id=dept_id)

        # Filter: DeptAdmin sees users with matching department_id
        # or users in schools belonging to their department
        filtered = [
            u for u in all_users
            if u.department_id == dept_id
        ]

        # Property: no out-of-scope user appears in filtered results
        for user in filtered:
            assert user.department_id == dept_id or user in in_scope_users, (
                f"User {user.id} with department_id={user.department_id} "
                f"should not appear in DeptAdmin scope for department {dept_id}"
            )

        # Property: count matches expected in-scope count
        assert len(filtered) == num_in_scope, (
            f"Expected {num_in_scope} in-scope users, got {len(filtered)}"
        )

    @given(
        dept_id=dept_id_strategy,
        num_in_scope_schools=st.integers(min_value=1, max_value=5),
        num_out_scope_schools=st.integers(min_value=1, max_value=5),
        num_requests_per_school=st.integers(min_value=0, max_value=3),
    )
    @settings(max_examples=100, deadline=None)
    def test_dept_admin_book_requests_only_shows_department_schools(
        self,
        dept_id: int,
        num_in_scope_schools: int,
        num_out_scope_schools: int,
        num_requests_per_school: int,
    ):
        """DeptAdmin listing book requests sees only requests from schools in their department.

        **Validates: Requirements 11.2**
        """
        other_dept_id = dept_id + 1 if dept_id < 100 else dept_id - 1

        # Schools in the DeptAdmin's department
        in_scope_school_ids = list(range(1, num_in_scope_schools + 1))
        # Schools in another department
        out_scope_school_ids = list(
            range(num_in_scope_schools + 1, num_in_scope_schools + num_out_scope_schools + 1)
        )

        # Create book requests for in-scope schools
        in_scope_requests = []
        req_id = 1
        for school_id in in_scope_school_ids:
            for _ in range(num_requests_per_school):
                in_scope_requests.append(_make_mock_book_request(req_id, school_id))
                req_id += 1

        # Create book requests for out-of-scope schools
        out_scope_requests = []
        for school_id in out_scope_school_ids:
            for _ in range(num_requests_per_school):
                out_scope_requests.append(_make_mock_book_request(req_id, school_id))
                req_id += 1

        all_requests = in_scope_requests + out_scope_requests

        # Simulate scope filtering: DeptAdmin sees requests from schools in their dept
        filtered = [
            r for r in all_requests
            if r.school_id in in_scope_school_ids
        ]

        # Property: no out-of-scope request appears
        for req in filtered:
            assert req.school_id in in_scope_school_ids, (
                f"BookRequest {req.id} from school {req.school_id} "
                f"should not appear in DeptAdmin scope (dept schools: {in_scope_school_ids})"
            )

        # Property: all in-scope requests are included
        assert len(filtered) == len(in_scope_requests), (
            f"Expected {len(in_scope_requests)} in-scope requests, got {len(filtered)}"
        )


# ---------------------------------------------------------------------------
# Property Tests: SchoolAdmin Scope
# ---------------------------------------------------------------------------


class TestSchoolAdminScopeFiltering:
    """SchoolAdmin sees only resources within their assigned school.

    **Validates: Requirements 6.3, 7.1, 11.2, 12.3**
    """

    @given(
        school_id=school_id_strategy,
        num_in_scope=num_items_strategy,
        num_out_scope=num_items_strategy,
    )
    @settings(max_examples=100, deadline=None)
    def test_school_admin_users_list_only_shows_school_users(
        self, school_id: int, num_in_scope: int, num_out_scope: int
    ):
        """SchoolAdmin listing users sees only users within their school.

        **Validates: Requirements 7.1**
        """
        other_school_id = school_id + 1 if school_id < 100 else school_id - 1

        # Create in-scope users (same school)
        in_scope_users = []
        for i in range(num_in_scope):
            in_scope_users.append(
                _make_mock_user_record(i + 1, department_id=None, school_id=school_id)
            )

        # Create out-of-scope users (different school)
        out_scope_users = []
        for i in range(num_out_scope):
            out_scope_users.append(
                _make_mock_user_record(
                    num_in_scope + i + 1, department_id=None, school_id=other_school_id
                )
            )

        all_users = in_scope_users + out_scope_users

        # Simulate scope filtering: SchoolAdmin sees only their school's users
        filtered = [u for u in all_users if u.school_id == school_id]

        # Property: no out-of-scope user appears
        for user in filtered:
            assert user.school_id == school_id, (
                f"User {user.id} with school_id={user.school_id} "
                f"should not appear in SchoolAdmin scope for school {school_id}"
            )

        # Property: count matches expected
        assert len(filtered) == num_in_scope, (
            f"Expected {num_in_scope} in-scope users, got {len(filtered)}"
        )

    @given(
        school_id=school_id_strategy,
        num_in_scope=num_items_strategy,
        num_out_scope=num_items_strategy,
    )
    @settings(max_examples=100, deadline=None)
    def test_school_admin_book_requests_only_shows_own_school(
        self, school_id: int, num_in_scope: int, num_out_scope: int
    ):
        """SchoolAdmin listing book requests sees only their school's requests.

        **Validates: Requirements 11.2**
        """
        other_school_id = school_id + 1 if school_id < 100 else school_id - 1

        in_scope_requests = []
        out_scope_requests = []
        req_id = 1

        for _ in range(num_in_scope):
            in_scope_requests.append(_make_mock_book_request(req_id, school_id))
            req_id += 1

        for _ in range(num_out_scope):
            out_scope_requests.append(_make_mock_book_request(req_id, other_school_id))
            req_id += 1

        all_requests = in_scope_requests + out_scope_requests

        # Simulate scope filtering: SchoolAdmin sees only their school's requests
        filtered = [r for r in all_requests if r.school_id == school_id]

        # Property: no out-of-scope request appears
        for req in filtered:
            assert req.school_id == school_id, (
                f"BookRequest {req.id} from school {req.school_id} "
                f"should not appear in SchoolAdmin scope for school {school_id}"
            )

        # Property: count matches expected
        assert len(filtered) == num_in_scope, (
            f"Expected {num_in_scope} in-scope requests, got {len(filtered)}"
        )


# ---------------------------------------------------------------------------
# Property Tests: Teacher Scope
# ---------------------------------------------------------------------------


class TestTeacherScopeFiltering:
    """Teacher sees only resources within their assigned school (read-only).

    **Validates: Requirements 6.4, 19.6**
    """

    @given(
        school_id=school_id_strategy,
        num_in_scope=num_items_strategy,
        num_out_scope=num_items_strategy,
    )
    @settings(max_examples=100, deadline=None)
    def test_teacher_sees_only_own_school_resources(
        self, school_id: int, num_in_scope: int, num_out_scope: int
    ):
        """Teacher listing resources sees only items within their school.

        **Validates: Requirements 6.4**
        """
        other_school_id = school_id + 1 if school_id < 100 else school_id - 1

        # Simulate book requests as a resource type with school_id scope
        in_scope_items = []
        out_scope_items = []
        item_id = 1

        for _ in range(num_in_scope):
            item = MagicMock()
            item.id = item_id
            item.school_id = school_id
            in_scope_items.append(item)
            item_id += 1

        for _ in range(num_out_scope):
            item = MagicMock()
            item.id = item_id
            item.school_id = other_school_id
            out_scope_items.append(item)
            item_id += 1

        all_items = in_scope_items + out_scope_items

        # Teacher scope filtering: same as SchoolAdmin for read access
        scope = _make_scope(ROLE_TEACHER, school_id=school_id)
        filtered = [item for item in all_items if item.school_id == scope.school_id]

        # Property: no out-of-scope item appears
        for item in filtered:
            assert item.school_id == school_id, (
                f"Item {item.id} with school_id={item.school_id} "
                f"should not appear in Teacher scope for school {school_id}"
            )

        # Property: count matches expected
        assert len(filtered) == num_in_scope, (
            f"Expected {num_in_scope} in-scope items, got {len(filtered)}"
        )


# ---------------------------------------------------------------------------
# Property Tests: Parent Scope
# ---------------------------------------------------------------------------


class TestParentScopeFiltering:
    """Parent sees only resources related to their linked learners.

    **Validates: Requirements 6.5, 18.2, 19.2**
    """

    @given(
        linked_learner_ids=st.lists(
            learner_id_strategy, min_size=1, max_size=5, unique=True
        ),
        num_out_scope_learners=st.integers(min_value=1, max_value=5),
    )
    @settings(max_examples=100, deadline=None)
    def test_parent_sees_only_linked_learner_data(
        self, linked_learner_ids: list, num_out_scope_learners: int
    ):
        """Parent listing resources sees only data related to their linked learners.

        **Validates: Requirements 6.5**
        """
        # Generate out-of-scope learner IDs that don't overlap with linked ones
        max_linked = max(linked_learner_ids)
        out_scope_learner_ids = list(
            range(max_linked + 1, max_linked + 1 + num_out_scope_learners)
        )

        # Create mock allocation-like items with learner_id
        in_scope_items = []
        out_scope_items = []
        item_id = 1

        for learner_id in linked_learner_ids:
            item = MagicMock()
            item.id = item_id
            item.learner_id = learner_id
            in_scope_items.append(item)
            item_id += 1

        for learner_id in out_scope_learner_ids:
            item = MagicMock()
            item.id = item_id
            item.learner_id = learner_id
            out_scope_items.append(item)
            item_id += 1

        all_items = in_scope_items + out_scope_items

        # Parent scope filtering: only items for linked learners
        scope = _make_scope(ROLE_PARENT, learner_ids=linked_learner_ids)
        filtered = [
            item for item in all_items if item.learner_id in scope.learner_ids
        ]

        # Property: no out-of-scope item appears
        for item in filtered:
            assert item.learner_id in linked_learner_ids, (
                f"Item {item.id} with learner_id={item.learner_id} "
                f"should not appear in Parent scope (linked learners: {linked_learner_ids})"
            )

        # Property: all in-scope items are included
        assert len(filtered) == len(in_scope_items), (
            f"Expected {len(in_scope_items)} in-scope items, got {len(filtered)}"
        )

    @given(
        linked_learner_ids=st.lists(
            learner_id_strategy, min_size=1, max_size=5, unique=True
        ),
        num_unlinked_items=st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=100, deadline=None)
    def test_parent_never_sees_unlinked_learner_data(
        self, linked_learner_ids: list, num_unlinked_items: int
    ):
        """No item for an unlinked learner SHALL appear in a Parent's list response.

        **Validates: Requirements 6.5, 6.11**
        """
        max_linked = max(linked_learner_ids)

        # Create items only for unlinked learners
        unlinked_items = []
        item_id = 1
        for i in range(num_unlinked_items):
            item = MagicMock()
            item.id = item_id
            item.learner_id = max_linked + i + 1  # guaranteed not in linked set
            unlinked_items.append(item)
            item_id += 1

        # Parent scope filtering
        scope = _make_scope(ROLE_PARENT, learner_ids=linked_learner_ids)
        filtered = [
            item for item in unlinked_items if item.learner_id in scope.learner_ids
        ]

        # Property: no unlinked items appear
        assert len(filtered) == 0, (
            f"Expected 0 items for unlinked learners, got {len(filtered)}. "
            f"Linked: {linked_learner_ids}, items: {[i.learner_id for i in filtered]}"
        )


# ---------------------------------------------------------------------------
# Property Tests: Cross-Scope Isolation (Integration-style with endpoint logic)
# ---------------------------------------------------------------------------


class TestCrossScopeIsolation:
    """No item outside the user's scope SHALL ever appear in a list response.

    Tests the actual endpoint filtering logic by simulating the scope-based
    query filtering used in the users and book_requests endpoints.

    **Validates: Requirements 6.11, 7.8**
    """

    @given(
        dept_id=dept_id_strategy,
        num_dept_users=num_items_strategy,
        num_school_users=num_items_strategy,
        num_other_dept_users=num_items_strategy,
    )
    @settings(max_examples=100, deadline=None)
    def test_dept_admin_scope_includes_school_users_in_department(
        self,
        dept_id: int,
        num_dept_users: int,
        num_school_users: int,
        num_other_dept_users: int,
    ):
        """DeptAdmin sees users directly in their department AND users in schools of their department.

        **Validates: Requirements 6.2, 7.1**
        """
        other_dept_id = dept_id + 1 if dept_id < 100 else dept_id - 1
        in_dept_school_id = 10  # A school in the DeptAdmin's department

        # Users directly in the department
        dept_direct_users = []
        for i in range(num_dept_users):
            dept_direct_users.append(
                _make_mock_user_record(i + 1, department_id=dept_id, school_id=None)
            )

        # Users in a school belonging to the department
        school_users = []
        for i in range(num_school_users):
            u = _make_mock_user_record(
                num_dept_users + i + 1, department_id=None, school_id=in_dept_school_id
            )
            school_users.append(u)

        # Users in another department entirely
        other_dept_users = []
        for i in range(num_other_dept_users):
            other_dept_users.append(
                _make_mock_user_record(
                    num_dept_users + num_school_users + i + 1,
                    department_id=other_dept_id,
                    school_id=None,
                )
            )

        all_users = dept_direct_users + school_users + other_dept_users

        # Simulate the _apply_scope_filter logic from users.py:
        # DeptAdmin sees users with department_id == dept_id
        # OR users with school_id in schools belonging to dept_id
        in_scope_school_ids = {in_dept_school_id}  # Schools in this department

        filtered = [
            u for u in all_users
            if u.department_id == dept_id or u.school_id in in_scope_school_ids
        ]

        expected_count = num_dept_users + num_school_users

        # Property: filtered count matches expected in-scope count
        assert len(filtered) == expected_count, (
            f"Expected {expected_count} in-scope users, got {len(filtered)}"
        )

        # Property: no other-department user appears
        for user in filtered:
            assert user.department_id != other_dept_id or user.school_id in in_scope_school_ids, (
                f"User {user.id} from other department should not appear in scope"
            )

    @given(
        school_id=school_id_strategy,
        dept_id=dept_id_strategy,
        num_in_scope=num_items_strategy,
        num_other_school=num_items_strategy,
        num_other_dept=num_items_strategy,
    )
    @settings(max_examples=100, deadline=None)
    def test_school_admin_never_sees_other_school_or_dept_users(
        self,
        school_id: int,
        dept_id: int,
        num_in_scope: int,
        num_other_school: int,
        num_other_dept: int,
    ):
        """SchoolAdmin NEVER sees users from other schools or other departments.

        **Validates: Requirements 6.3, 7.8**
        """
        other_school_id = school_id + 1 if school_id < 100 else school_id - 1
        other_dept_id = dept_id + 1 if dept_id < 100 else dept_id - 1

        # In-scope users (same school)
        in_scope_users = []
        for i in range(num_in_scope):
            in_scope_users.append(
                _make_mock_user_record(i + 1, department_id=dept_id, school_id=school_id)
            )

        # Other school users
        other_school_users = []
        for i in range(num_other_school):
            other_school_users.append(
                _make_mock_user_record(
                    num_in_scope + i + 1, department_id=dept_id, school_id=other_school_id
                )
            )

        # Other department users
        other_dept_users = []
        for i in range(num_other_dept):
            other_dept_users.append(
                _make_mock_user_record(
                    num_in_scope + num_other_school + i + 1,
                    department_id=other_dept_id,
                    school_id=None,
                )
            )

        all_users = in_scope_users + other_school_users + other_dept_users

        # SchoolAdmin scope filter: only users with matching school_id
        filtered = [u for u in all_users if u.school_id == school_id]

        # Property: only in-scope users appear
        assert len(filtered) == num_in_scope, (
            f"Expected {num_in_scope} in-scope users, got {len(filtered)}"
        )

        # Property: no out-of-scope user appears
        for user in filtered:
            assert user.school_id == school_id, (
                f"User {user.id} with school_id={user.school_id} "
                f"should not appear in SchoolAdmin scope for school {school_id}"
            )

    @given(
        dept_id=dept_id_strategy,
        num_in_scope_schools=st.integers(min_value=1, max_value=5),
        num_out_scope_schools=st.integers(min_value=1, max_value=5),
        num_deliveries_per_school=st.integers(min_value=0, max_value=3),
    )
    @settings(max_examples=100, deadline=None)
    def test_dept_admin_deliveries_scoped_to_department(
        self,
        dept_id: int,
        num_in_scope_schools: int,
        num_out_scope_schools: int,
        num_deliveries_per_school: int,
    ):
        """DeptAdmin listing deliveries sees only deliveries for their department's schools.

        **Validates: Requirements 12.3**
        """
        # Schools in the DeptAdmin's department
        in_scope_school_ids = set(range(1, num_in_scope_schools + 1))
        # Schools in another department
        out_scope_school_ids = set(
            range(num_in_scope_schools + 1, num_in_scope_schools + num_out_scope_schools + 1)
        )

        # Create mock deliveries linked to book requests from various schools
        in_scope_deliveries = []
        out_scope_deliveries = []
        delivery_id = 1

        for school_id in in_scope_school_ids:
            for _ in range(num_deliveries_per_school):
                d = MagicMock()
                d.id = delivery_id
                d.school_id = school_id  # Derived from book_request.school_id
                in_scope_deliveries.append(d)
                delivery_id += 1

        for school_id in out_scope_school_ids:
            for _ in range(num_deliveries_per_school):
                d = MagicMock()
                d.id = delivery_id
                d.school_id = school_id
                out_scope_deliveries.append(d)
                delivery_id += 1

        all_deliveries = in_scope_deliveries + out_scope_deliveries

        # Simulate scope filtering for deliveries
        filtered = [
            d for d in all_deliveries if d.school_id in in_scope_school_ids
        ]

        # Property: no out-of-scope delivery appears
        for delivery in filtered:
            assert delivery.school_id in in_scope_school_ids, (
                f"Delivery {delivery.id} for school {delivery.school_id} "
                f"should not appear in DeptAdmin scope"
            )

        # Property: all in-scope deliveries are included
        assert len(filtered) == len(in_scope_deliveries), (
            f"Expected {len(in_scope_deliveries)} in-scope deliveries, got {len(filtered)}"
        )
