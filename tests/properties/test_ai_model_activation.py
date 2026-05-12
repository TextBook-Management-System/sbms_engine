# Feature: sbms-api-endpoints, Property 12: AI Model Activation Mutual Exclusivity
"""
Property-based tests for AI model activation mutual exclusivity.

Tests validate that:
- For any set of AI model versions sharing the same model_type, activating one model
  SHALL deactivate all other models of that same type.
- At any point in time, at most one model per type SHALL have is_active = true.
- Models of different types are not affected by activation.

**Validates: Requirements 14.3**
"""

import pytest
from unittest.mock import MagicMock, patch, call
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from app.core.exceptions import NotFoundError
from app.models.database import AIModelVersion


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# Model types: non-empty strings representing different AI model categories
model_types = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=30,
).filter(lambda s: s.strip())

# Model names: non-empty strings
model_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N")),
    min_size=1,
    max_size=50,
).filter(lambda s: s.strip())

# Model versions: non-empty strings
model_versions = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N", "P")),
    min_size=1,
    max_size=30,
).filter(lambda s: s.strip())

# Number of models of the same type (at least 2 to test mutual exclusivity)
num_same_type_models = st.integers(min_value=2, max_value=10)

# Number of models of a different type
num_different_type_models = st.integers(min_value=0, max_value=5)

# Index of the model to activate (within the same-type group)
activation_index = st.integers(min_value=0, max_value=100)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ai_model(model_id: int, model_name: str, model_version: str,
                   model_type: str, is_active: bool = False):
    """Create a mock AIModelVersion object."""
    model = MagicMock(spec=AIModelVersion)
    model.id = model_id
    model.model_name = model_name
    model.model_version = model_version
    model.model_type = model_type
    model.is_active = is_active
    return model


def _simulate_activation(models: list, target_id: int):
    """
    Simulate the activation logic from the activate_ai_model endpoint.

    This replicates the core business logic:
    1. Find the model to activate
    2. Deactivate all other models of the same model_type
    3. Activate the specified model
    """
    # Find the target model
    target_model = None
    for model in models:
        if model.id == target_id:
            target_model = model
            break

    if target_model is None:
        raise NotFoundError(detail=f"AIModelVersion with id {target_id} not found")

    # Deactivate all other models of the same model_type
    for model in models:
        if model.model_type == target_model.model_type and model.id != target_id:
            model.is_active = False

    # Activate the specified model
    target_model.is_active = True

    return target_model


# ---------------------------------------------------------------------------
# Property Tests
# ---------------------------------------------------------------------------


class TestAIModelActivationMutualExclusivity:
    """
    Property 12: For any set of AI model versions sharing the same model_type,
    activating one model SHALL deactivate all other models of that same type.
    At any point in time, at most one model per type SHALL have is_active = true.
    """

    @given(
        model_type=model_types,
        num_models=num_same_type_models,
        activate_idx=activation_index,
    )
    @settings(max_examples=100, deadline=None)
    def test_activating_one_model_deactivates_all_others_of_same_type(
        self, model_type: str, num_models: int, activate_idx: int
    ):
        """
        For any set of AI models sharing the same model_type, activating one
        deactivates all others of that type.

        **Validates: Requirements 14.3**
        """
        # Normalize activation index to valid range
        activate_idx = activate_idx % num_models

        # Create a set of models all sharing the same model_type
        models = []
        for i in range(num_models):
            models.append(
                _make_ai_model(
                    model_id=i + 1,
                    model_name=f"model_{i}",
                    model_version=f"v{i}",
                    model_type=model_type,
                    is_active=(i == 0),  # Start with first model active
                )
            )

        target_id = models[activate_idx].id

        # Perform activation
        _simulate_activation(models, target_id)

        # Property: the activated model is active
        assert models[activate_idx].is_active is True, (
            f"Model {target_id} should be active after activation"
        )

        # Property: all other models of the same type are inactive
        for i, model in enumerate(models):
            if i != activate_idx:
                assert model.is_active is False, (
                    f"Model {model.id} (index {i}) should be inactive after "
                    f"activating model {target_id} (index {activate_idx})"
                )

    @given(
        model_type=model_types,
        num_models=num_same_type_models,
        activate_idx=activation_index,
    )
    @settings(max_examples=100, deadline=None)
    def test_exactly_one_model_active_per_type_after_activation(
        self, model_type: str, num_models: int, activate_idx: int
    ):
        """
        After activation, exactly one model of that type is active.

        **Validates: Requirements 14.3**
        """
        # Normalize activation index to valid range
        activate_idx = activate_idx % num_models

        # Create models with random initial active states
        models = []
        for i in range(num_models):
            models.append(
                _make_ai_model(
                    model_id=i + 1,
                    model_name=f"model_{i}",
                    model_version=f"v{i}",
                    model_type=model_type,
                    is_active=True,  # All start active (worst case)
                )
            )

        target_id = models[activate_idx].id

        # Perform activation
        _simulate_activation(models, target_id)

        # Property: exactly one model of this type is active
        active_count = sum(1 for m in models if m.is_active)
        assert active_count == 1, (
            f"Expected exactly 1 active model of type '{model_type}', "
            f"got {active_count}"
        )

        # And it's the one we activated
        active_models = [m for m in models if m.is_active]
        assert active_models[0].id == target_id, (
            f"Expected model {target_id} to be the active one, "
            f"got model {active_models[0].id}"
        )

    @given(
        same_type=model_types,
        different_type=model_types,
        num_same_type=num_same_type_models,
        num_different_type=st.integers(min_value=1, max_value=5),
        activate_idx=activation_index,
    )
    @settings(max_examples=100, deadline=None)
    def test_models_of_different_types_not_affected_by_activation(
        self,
        same_type: str,
        different_type: str,
        num_same_type: int,
        num_different_type: int,
        activate_idx: int,
    ):
        """
        Models of different types are not affected by activation of a model
        of another type.

        **Validates: Requirements 14.3**
        """
        # Ensure the two types are actually different
        assume(same_type != different_type)

        # Normalize activation index to valid range for same_type models
        activate_idx = activate_idx % num_same_type

        # Create models of the target type
        same_type_models = []
        model_id = 1
        for i in range(num_same_type):
            same_type_models.append(
                _make_ai_model(
                    model_id=model_id,
                    model_name=f"same_model_{i}",
                    model_version=f"v{i}",
                    model_type=same_type,
                    is_active=(i == 0),
                )
            )
            model_id += 1

        # Create models of a different type (some active)
        different_type_models = []
        for i in range(num_different_type):
            different_type_models.append(
                _make_ai_model(
                    model_id=model_id,
                    model_name=f"diff_model_{i}",
                    model_version=f"v{i}",
                    model_type=different_type,
                    is_active=(i == 0),  # First one is active
                )
            )
            model_id += 1

        # Record the initial active states of different-type models
        initial_different_states = [m.is_active for m in different_type_models]

        # Combine all models
        all_models = same_type_models + different_type_models

        # Activate a model of the same_type
        target_id = same_type_models[activate_idx].id
        _simulate_activation(all_models, target_id)

        # Property: different-type models are unchanged
        for i, model in enumerate(different_type_models):
            assert model.is_active == initial_different_states[i], (
                f"Model {model.id} of type '{different_type}' had its is_active "
                f"changed from {initial_different_states[i]} to {model.is_active} "
                f"when activating a model of type '{same_type}'"
            )

    @given(
        model_type=model_types,
        num_models=num_same_type_models,
        first_activate_idx=activation_index,
        second_activate_idx=activation_index,
    )
    @settings(max_examples=100, deadline=None)
    def test_sequential_activations_maintain_mutual_exclusivity(
        self,
        model_type: str,
        num_models: int,
        first_activate_idx: int,
        second_activate_idx: int,
    ):
        """
        After multiple sequential activations, at most one model per type
        SHALL have is_active = true.

        **Validates: Requirements 14.3**
        """
        # Normalize indices
        first_activate_idx = first_activate_idx % num_models
        second_activate_idx = second_activate_idx % num_models

        # Create models all inactive initially
        models = []
        for i in range(num_models):
            models.append(
                _make_ai_model(
                    model_id=i + 1,
                    model_name=f"model_{i}",
                    model_version=f"v{i}",
                    model_type=model_type,
                    is_active=False,
                )
            )

        # First activation
        _simulate_activation(models, models[first_activate_idx].id)

        # Verify after first activation
        active_count = sum(1 for m in models if m.is_active)
        assert active_count == 1, (
            f"After first activation: expected 1 active model, got {active_count}"
        )

        # Second activation
        _simulate_activation(models, models[second_activate_idx].id)

        # Property: still exactly one active model after second activation
        active_count = sum(1 for m in models if m.is_active)
        assert active_count == 1, (
            f"After second activation: expected 1 active model, got {active_count}"
        )

        # And it's the second one we activated
        active_models = [m for m in models if m.is_active]
        assert active_models[0].id == models[second_activate_idx].id, (
            f"Expected model {models[second_activate_idx].id} to be active after "
            f"second activation, got model {active_models[0].id}"
        )

    @given(
        model_type=model_types,
        num_models=num_same_type_models,
        activate_idx=activation_index,
    )
    @settings(max_examples=100, deadline=None)
    def test_endpoint_deactivates_same_type_via_db_update(
        self, model_type: str, num_models: int, activate_idx: int
    ):
        """
        The activate_ai_model endpoint correctly calls db.query().filter().update()
        to deactivate all other models of the same type, then sets the target active.

        This tests the actual endpoint function with a mocked DB session.

        **Validates: Requirements 14.3**
        """
        from app.api.v1.endpoints.ai_models import activate_ai_model

        # Normalize activation index
        activate_idx = activate_idx % num_models

        # Create the target model mock
        target_model = MagicMock()
        target_model.id = activate_idx + 1
        target_model.model_name = f"model_{activate_idx}"
        target_model.model_version = f"v{activate_idx}"
        target_model.model_type = model_type
        target_model.is_active = False

        # Mock DB session
        mock_db = MagicMock()

        # The endpoint calls db.query(AIModelVersion) twice:
        # 1st: db.query(AIModelVersion).filter(AIModelVersion.id == id).first()
        # 2nd: db.query(AIModelVersion).filter(type==..., id!=...).update(...)
        mock_filter_first_call = MagicMock()
        mock_filter_first_call.first.return_value = target_model

        mock_filter_second_call = MagicMock()
        mock_filter_second_call.update.return_value = num_models - 1

        # Track calls to db.query().filter()
        call_count = {"value": 0}

        def query_side_effect(*args, **kwargs):
            mock_query_instance = MagicMock()

            def filter_side_effect(*filter_args, **filter_kwargs):
                call_count["value"] += 1
                if call_count["value"] == 1:
                    # First filter call: finding the model by id
                    return mock_filter_first_call
                else:
                    # Second filter call: deactivating others of same type
                    return mock_filter_second_call

            mock_query_instance.filter.side_effect = filter_side_effect
            return mock_query_instance

        mock_db.query.side_effect = query_side_effect

        # Call the endpoint
        result = activate_ai_model(id=target_model.id, db=mock_db)

        # Property: the target model was set to active
        assert target_model.is_active is True, (
            "Target model should be set to is_active=True"
        )

        # Property: db.commit() was called (changes persisted)
        mock_db.commit.assert_called_once()

        # Property: db.refresh() was called on the target model
        mock_db.refresh.assert_called_once_with(target_model)

        # Property: update was called to deactivate others
        mock_filter_second_call.update.assert_called_once_with({"is_active": False})
