"""Unit tests for app.core.rbac module."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import ForbiddenError
from app.core.rbac import (
    ALL_ROLES,
    ROLE_DEPT_ADMIN,
    ROLE_PARENT,
    ROLE_SCHOOL_ADMIN,
    ROLE_TEACHER,
    Scope,
    _get_primary_role,
    _get_user_roles,
    check_book_copy_scope,
    check_department_scope,
    check_learner_scope,
    check_school_scope,
    get_user_scope,
    require_role,
    require_scope,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(roles: list[str], department_id=None, school_id=None, user_id=1):
    """Create a mock User with the given roles."""
    user = MagicMock()
    user.id = user_id
    user.department_id = department_id
    user.school_id = school_id

    # Create mock UserRole objects
    mock_roles = []
    for role_name in roles:
        role_obj = MagicMock()
        role_obj.role = role_name
        mock_roles.append(role_obj)
    user.roles = mock_roles

    # Mock school relationship for scope resolution
    if school_id:
        school_mock = MagicMock()
        school_mock.department_id = department_id
        user.school = school_mock
    else:
        user.school = None

    return user


def _make_db():
    """Create a mock DB session."""
    return MagicMock()


# ---------------------------------------------------------------------------
# Tests: _get_user_roles and _get_primary_role
# ---------------------------------------------------------------------------


class TestGetUserRoles:
    """Tests for role extraction helpers."""

    def test_get_user_roles_single_role(self):
        user = _make_user(["DeptAdmin"])
        assert _get_user_roles(user) == ["DeptAdmin"]

    def test_get_user_roles_multiple_roles(self):
        user = _make_user(["DeptAdmin", "SchoolAdmin"])
        assert _get_user_roles(user) == ["DeptAdmin", "SchoolAdmin"]

    def test_get_user_roles_no_roles(self):
        user = _make_user([])
        assert _get_user_roles(user) == []

    def test_get_primary_role_returns_first(self):
        user = _make_user(["Teacher", "Parent"])
        assert _get_primary_role(user) == "Teacher"

    def test_get_primary_role_empty_returns_empty_string(self):
        user = _make_user([])
        assert _get_primary_role(user) == ""


# ---------------------------------------------------------------------------
# Tests: require_role
# ---------------------------------------------------------------------------


class TestRequireRole:
    """Tests for the require_role dependency factory."""

    def test_require_role_allows_matching_role(self):
        """User with matching role passes the check."""
        user = _make_user(["DeptAdmin"], department_id=1)
        checker = require_role("DeptAdmin")
        # Call the inner function directly with the user
        result = checker(current_user=user)
        assert result == user

    def test_require_role_allows_one_of_multiple_roles(self):
        """User with one of multiple allowed roles passes."""
        user = _make_user(["SchoolAdmin"], school_id=1)
        checker = require_role("DeptAdmin", "SchoolAdmin")
        result = checker(current_user=user)
        assert result == user

    def test_require_role_denies_non_matching_role(self):
        """User without matching role gets ForbiddenError."""
        user = _make_user(["Parent"])
        checker = require_role("DeptAdmin", "SchoolAdmin")
        with pytest.raises(ForbiddenError) as exc_info:
            checker(current_user=user)
        assert "Required role(s)" in exc_info.value.detail

    def test_require_role_denies_user_with_no_roles(self):
        """User with no roles gets ForbiddenError."""
        user = _make_user([])
        checker = require_role("DeptAdmin")
        with pytest.raises(ForbiddenError):
            checker(current_user=user)

    def test_require_role_all_four_roles_supported(self):
        """All four roles are recognized."""
        for role in ALL_ROLES:
            user = _make_user([role])
            checker = require_role(role)
            result = checker(current_user=user)
            assert result == user


# ---------------------------------------------------------------------------
# Tests: require_scope
# ---------------------------------------------------------------------------


class TestRequireScope:
    """Tests for the require_scope dependency factory."""

    def test_require_scope_allows_valid_role(self):
        """User with a valid role passes the scope checker."""
        user = _make_user(["DeptAdmin"], department_id=1)
        db = _make_db()
        checker = require_scope("school", "school_id")
        result = checker(current_user=user, db=db)
        assert result == user

    def test_require_scope_denies_no_role(self):
        """User with no valid role gets ForbiddenError."""
        user = _make_user([])
        db = _make_db()
        checker = require_scope("school", "school_id")
        with pytest.raises(ForbiddenError) as exc_info:
            checker(current_user=user, db=db)
        assert "No valid role" in exc_info.value.detail

    def test_require_scope_stores_metadata(self):
        """The scope checker stores resource_type and resource_id_param."""
        checker = require_scope("department", "dept_id")
        assert checker._resource_type == "department"
        assert checker._resource_id_param == "dept_id"


# ---------------------------------------------------------------------------
# Tests: get_user_scope
# ---------------------------------------------------------------------------


class TestGetUserScope:
    """Tests for the get_user_scope dependency."""

    def test_dept_admin_scope(self):
        """DeptAdmin gets department_id in scope."""
        user = _make_user(["DeptAdmin"], department_id=10)
        db = _make_db()
        scope = get_user_scope(current_user=user, db=db)
        assert scope.department_id == 10
        assert scope.school_id is None
        assert scope.learner_ids == []
        assert scope.role == "DeptAdmin"

    def test_school_admin_scope(self):
        """SchoolAdmin gets school_id and department_id in scope."""
        user = _make_user(["SchoolAdmin"], department_id=5, school_id=20)
        db = _make_db()
        scope = get_user_scope(current_user=user, db=db)
        assert scope.school_id == 20
        assert scope.department_id == 5
        assert scope.role == "SchoolAdmin"

    def test_teacher_scope(self):
        """Teacher gets school_id and department_id in scope."""
        user = _make_user(["Teacher"], department_id=3, school_id=15)
        db = _make_db()
        scope = get_user_scope(current_user=user, db=db)
        assert scope.school_id == 15
        assert scope.department_id == 3
        assert scope.role == "Teacher"

    def test_parent_scope(self):
        """Parent gets learner_ids in scope."""
        user = _make_user(["Parent"], user_id=42)
        db = _make_db()

        # Mock the ParentLearner query
        mock_results = [MagicMock(learner_id=100), MagicMock(learner_id=200)]
        db.query.return_value.filter.return_value.all.return_value = mock_results

        scope = get_user_scope(current_user=user, db=db)
        assert scope.learner_ids == [100, 200]
        assert scope.department_id is None
        assert scope.school_id is None
        assert scope.role == "Parent"

    def test_parent_scope_no_learners(self):
        """Parent with no linked learners gets empty learner_ids."""
        user = _make_user(["Parent"], user_id=42)
        db = _make_db()
        db.query.return_value.filter.return_value.all.return_value = []

        scope = get_user_scope(current_user=user, db=db)
        assert scope.learner_ids == []

    def test_no_role_scope(self):
        """User with no role gets empty scope."""
        user = _make_user([])
        db = _make_db()
        scope = get_user_scope(current_user=user, db=db)
        assert scope.department_id is None
        assert scope.school_id is None
        assert scope.learner_ids == []
        assert scope.role == ""


# ---------------------------------------------------------------------------
# Tests: check_department_scope
# ---------------------------------------------------------------------------


class TestCheckDepartmentScope:
    """Tests for check_department_scope utility."""

    def test_dept_admin_same_department_passes(self):
        """DeptAdmin accessing their own department passes."""
        user = _make_user(["DeptAdmin"], department_id=1)
        scope = Scope(department_id=1, role=ROLE_DEPT_ADMIN)
        # Should not raise
        check_department_scope(user, scope, department_id=1)

    def test_dept_admin_different_department_raises(self):
        """DeptAdmin accessing another department raises ForbiddenError."""
        user = _make_user(["DeptAdmin"], department_id=1)
        scope = Scope(department_id=1, role=ROLE_DEPT_ADMIN)
        with pytest.raises(ForbiddenError):
            check_department_scope(user, scope, department_id=2)

    def test_school_admin_same_department_passes(self):
        """SchoolAdmin accessing their school's department passes."""
        user = _make_user(["SchoolAdmin"], department_id=5, school_id=10)
        scope = Scope(department_id=5, school_id=10, role=ROLE_SCHOOL_ADMIN)
        check_department_scope(user, scope, department_id=5)

    def test_school_admin_different_department_raises(self):
        """SchoolAdmin accessing another department raises ForbiddenError."""
        user = _make_user(["SchoolAdmin"], department_id=5, school_id=10)
        scope = Scope(department_id=5, school_id=10, role=ROLE_SCHOOL_ADMIN)
        with pytest.raises(ForbiddenError):
            check_department_scope(user, scope, department_id=99)

    def test_parent_always_raises(self):
        """Parent cannot access department resources."""
        user = _make_user(["Parent"])
        scope = Scope(learner_ids=[1, 2], role=ROLE_PARENT)
        with pytest.raises(ForbiddenError):
            check_department_scope(user, scope, department_id=1)


# ---------------------------------------------------------------------------
# Tests: check_school_scope
# ---------------------------------------------------------------------------


class TestCheckSchoolScope:
    """Tests for check_school_scope utility."""

    def test_dept_admin_school_in_department_passes(self):
        """DeptAdmin accessing a school in their department passes."""
        user = _make_user(["DeptAdmin"], department_id=1)
        scope = Scope(department_id=1, role=ROLE_DEPT_ADMIN)
        db = _make_db()

        # Mock school lookup
        school = MagicMock()
        school.department_id = 1
        db.query.return_value.filter.return_value.first.return_value = school

        check_school_scope(user, scope, school_id=10, db=db)

    def test_dept_admin_school_outside_department_raises(self):
        """DeptAdmin accessing a school outside their department raises ForbiddenError."""
        user = _make_user(["DeptAdmin"], department_id=1)
        scope = Scope(department_id=1, role=ROLE_DEPT_ADMIN)
        db = _make_db()

        school = MagicMock()
        school.department_id = 99  # Different department
        db.query.return_value.filter.return_value.first.return_value = school

        with pytest.raises(ForbiddenError):
            check_school_scope(user, scope, school_id=10, db=db)

    def test_dept_admin_nonexistent_school_raises(self):
        """DeptAdmin accessing a non-existent school raises ForbiddenError."""
        user = _make_user(["DeptAdmin"], department_id=1)
        scope = Scope(department_id=1, role=ROLE_DEPT_ADMIN)
        db = _make_db()
        db.query.return_value.filter.return_value.first.return_value = None

        with pytest.raises(ForbiddenError):
            check_school_scope(user, scope, school_id=999, db=db)

    def test_school_admin_own_school_passes(self):
        """SchoolAdmin accessing their own school passes."""
        user = _make_user(["SchoolAdmin"], school_id=10)
        scope = Scope(school_id=10, role=ROLE_SCHOOL_ADMIN)
        db = _make_db()
        check_school_scope(user, scope, school_id=10, db=db)

    def test_school_admin_other_school_raises(self):
        """SchoolAdmin accessing another school raises ForbiddenError."""
        user = _make_user(["SchoolAdmin"], school_id=10)
        scope = Scope(school_id=10, role=ROLE_SCHOOL_ADMIN)
        db = _make_db()
        with pytest.raises(ForbiddenError):
            check_school_scope(user, scope, school_id=20, db=db)

    def test_teacher_own_school_passes(self):
        """Teacher accessing their own school passes."""
        user = _make_user(["Teacher"], school_id=15)
        scope = Scope(school_id=15, role=ROLE_TEACHER)
        db = _make_db()
        check_school_scope(user, scope, school_id=15, db=db)

    def test_parent_raises(self):
        """Parent cannot access school-level resources."""
        user = _make_user(["Parent"])
        scope = Scope(learner_ids=[1], role=ROLE_PARENT)
        db = _make_db()
        with pytest.raises(ForbiddenError):
            check_school_scope(user, scope, school_id=10, db=db)


# ---------------------------------------------------------------------------
# Tests: check_learner_scope
# ---------------------------------------------------------------------------


class TestCheckLearnerScope:
    """Tests for check_learner_scope utility."""

    def test_dept_admin_learner_in_department_passes(self):
        """DeptAdmin accessing a learner in their department passes."""
        user = _make_user(["DeptAdmin"], department_id=1)
        scope = Scope(department_id=1, role=ROLE_DEPT_ADMIN)
        db = _make_db()

        # Mock: learner -> grade -> school -> department
        # _get_learner_school_id returns school_id
        # _get_school_department_id returns department_id
        # We need to mock db.query calls in sequence
        learner_mock = MagicMock()
        learner_mock.grade_id = 5

        grade_mock = MagicMock()
        grade_mock.school_id = 10

        school_mock = MagicMock()
        school_mock.department_id = 1

        # db.query(Learner).filter(...).first() -> learner_mock
        # db.query(Grade).filter(...).first() -> grade_mock
        # db.query(School).filter(...).first() -> school_mock
        call_count = [0]

        def mock_query(model):
            call_count[0] += 1
            mock_q = MagicMock()
            if call_count[0] == 1:
                mock_q.filter.return_value.first.return_value = learner_mock
            elif call_count[0] == 2:
                mock_q.filter.return_value.first.return_value = grade_mock
            elif call_count[0] == 3:
                mock_q.filter.return_value.first.return_value = school_mock
            return mock_q

        db.query.side_effect = mock_query

        check_learner_scope(user, scope, learner_id=100, db=db)

    def test_dept_admin_learner_outside_department_raises(self):
        """DeptAdmin accessing a learner outside their department raises ForbiddenError."""
        user = _make_user(["DeptAdmin"], department_id=1)
        scope = Scope(department_id=1, role=ROLE_DEPT_ADMIN)
        db = _make_db()

        learner_mock = MagicMock()
        learner_mock.grade_id = 5

        grade_mock = MagicMock()
        grade_mock.school_id = 10

        school_mock = MagicMock()
        school_mock.department_id = 99  # Different department

        call_count = [0]

        def mock_query(model):
            call_count[0] += 1
            mock_q = MagicMock()
            if call_count[0] == 1:
                mock_q.filter.return_value.first.return_value = learner_mock
            elif call_count[0] == 2:
                mock_q.filter.return_value.first.return_value = grade_mock
            elif call_count[0] == 3:
                mock_q.filter.return_value.first.return_value = school_mock
            return mock_q

        db.query.side_effect = mock_query

        with pytest.raises(ForbiddenError):
            check_learner_scope(user, scope, learner_id=100, db=db)

    def test_school_admin_learner_in_school_passes(self):
        """SchoolAdmin accessing a learner in their school passes."""
        user = _make_user(["SchoolAdmin"], school_id=10)
        scope = Scope(school_id=10, role=ROLE_SCHOOL_ADMIN)
        db = _make_db()

        learner_mock = MagicMock()
        learner_mock.grade_id = 5

        grade_mock = MagicMock()
        grade_mock.school_id = 10  # Same school

        call_count = [0]

        def mock_query(model):
            call_count[0] += 1
            mock_q = MagicMock()
            if call_count[0] == 1:
                mock_q.filter.return_value.first.return_value = learner_mock
            elif call_count[0] == 2:
                mock_q.filter.return_value.first.return_value = grade_mock
            return mock_q

        db.query.side_effect = mock_query

        check_learner_scope(user, scope, learner_id=100, db=db)

    def test_school_admin_learner_outside_school_raises(self):
        """SchoolAdmin accessing a learner outside their school raises ForbiddenError."""
        user = _make_user(["SchoolAdmin"], school_id=10)
        scope = Scope(school_id=10, role=ROLE_SCHOOL_ADMIN)
        db = _make_db()

        learner_mock = MagicMock()
        learner_mock.grade_id = 5

        grade_mock = MagicMock()
        grade_mock.school_id = 99  # Different school

        call_count = [0]

        def mock_query(model):
            call_count[0] += 1
            mock_q = MagicMock()
            if call_count[0] == 1:
                mock_q.filter.return_value.first.return_value = learner_mock
            elif call_count[0] == 2:
                mock_q.filter.return_value.first.return_value = grade_mock
            return mock_q

        db.query.side_effect = mock_query

        with pytest.raises(ForbiddenError):
            check_learner_scope(user, scope, learner_id=100, db=db)

    def test_parent_linked_learner_passes(self):
        """Parent accessing a linked learner passes."""
        user = _make_user(["Parent"])
        scope = Scope(learner_ids=[100, 200], role=ROLE_PARENT)
        db = _make_db()
        check_learner_scope(user, scope, learner_id=100, db=db)

    def test_parent_unlinked_learner_raises(self):
        """Parent accessing an unlinked learner raises ForbiddenError."""
        user = _make_user(["Parent"])
        scope = Scope(learner_ids=[100, 200], role=ROLE_PARENT)
        db = _make_db()
        with pytest.raises(ForbiddenError):
            check_learner_scope(user, scope, learner_id=999, db=db)


# ---------------------------------------------------------------------------
# Tests: check_book_copy_scope
# ---------------------------------------------------------------------------


class TestCheckBookCopyScope:
    """Tests for check_book_copy_scope utility."""

    def test_dept_admin_book_copy_in_department_passes(self):
        """DeptAdmin accessing a book copy in their department passes."""
        user = _make_user(["DeptAdmin"], department_id=1)
        scope = Scope(department_id=1, role=ROLE_DEPT_ADMIN)
        db = _make_db()

        book_copy = MagicMock()
        book_copy.school_id = 10

        school = MagicMock()
        school.department_id = 1

        call_count = [0]

        def mock_query(model):
            call_count[0] += 1
            mock_q = MagicMock()
            if call_count[0] == 1:
                mock_q.filter.return_value.first.return_value = book_copy
            elif call_count[0] == 2:
                mock_q.filter.return_value.first.return_value = school
            return mock_q

        db.query.side_effect = mock_query

        check_book_copy_scope(user, scope, book_copy_id=50, db=db)

    def test_dept_admin_book_copy_outside_department_raises(self):
        """DeptAdmin accessing a book copy outside their department raises ForbiddenError."""
        user = _make_user(["DeptAdmin"], department_id=1)
        scope = Scope(department_id=1, role=ROLE_DEPT_ADMIN)
        db = _make_db()

        book_copy = MagicMock()
        book_copy.school_id = 10

        school = MagicMock()
        school.department_id = 99

        call_count = [0]

        def mock_query(model):
            call_count[0] += 1
            mock_q = MagicMock()
            if call_count[0] == 1:
                mock_q.filter.return_value.first.return_value = book_copy
            elif call_count[0] == 2:
                mock_q.filter.return_value.first.return_value = school
            return mock_q

        db.query.side_effect = mock_query

        with pytest.raises(ForbiddenError):
            check_book_copy_scope(user, scope, book_copy_id=50, db=db)

    def test_school_admin_book_copy_in_school_passes(self):
        """SchoolAdmin accessing a book copy in their school passes."""
        user = _make_user(["SchoolAdmin"], school_id=10)
        scope = Scope(school_id=10, role=ROLE_SCHOOL_ADMIN)
        db = _make_db()

        book_copy = MagicMock()
        book_copy.school_id = 10

        db.query.return_value.filter.return_value.first.return_value = book_copy

        check_book_copy_scope(user, scope, book_copy_id=50, db=db)

    def test_school_admin_book_copy_outside_school_raises(self):
        """SchoolAdmin accessing a book copy outside their school raises ForbiddenError."""
        user = _make_user(["SchoolAdmin"], school_id=10)
        scope = Scope(school_id=10, role=ROLE_SCHOOL_ADMIN)
        db = _make_db()

        book_copy = MagicMock()
        book_copy.school_id = 99

        db.query.return_value.filter.return_value.first.return_value = book_copy

        with pytest.raises(ForbiddenError):
            check_book_copy_scope(user, scope, book_copy_id=50, db=db)

    def test_parent_always_raises(self):
        """Parent cannot access book copies directly."""
        user = _make_user(["Parent"])
        scope = Scope(learner_ids=[1], role=ROLE_PARENT)
        db = _make_db()

        book_copy = MagicMock()
        book_copy.school_id = 10

        db.query.return_value.filter.return_value.first.return_value = book_copy

        with pytest.raises(ForbiddenError):
            check_book_copy_scope(user, scope, book_copy_id=50, db=db)

    def test_nonexistent_book_copy_does_not_raise(self):
        """Non-existent book copy does not raise (let endpoint handle 404)."""
        user = _make_user(["DeptAdmin"], department_id=1)
        scope = Scope(department_id=1, role=ROLE_DEPT_ADMIN)
        db = _make_db()
        db.query.return_value.filter.return_value.first.return_value = None

        # Should not raise — endpoint handles 404
        check_book_copy_scope(user, scope, book_copy_id=999, db=db)
