"""
Unit Tests for Rule-Based Natural Language Query Interpreter (Step 4.1).
Runs independently without external network calls or LLM API keys.
"""

import pytest
from pydantic import ValidationError

from app.api.schemas import ArgoQueryParameters, InterpretationResult
from app.llm.interpreter import QueryInterpreter


@pytest.fixture
def interpreter():
    """Provides a clean instance of QueryInterpreter."""
    return QueryInterpreter()


class TestQueryInterpreterUnit:
    """Unit tests for parameter extraction and domain classification."""

    def test_extract_platform_id(self, interpreter):
        """Verifies extraction of 7-digit ARGO float IDs in different query formats."""
        res1 = interpreter.interpret("Show temperature profiles for float 1900121 in the ocean")
        assert res1.is_valid_query is True
        assert res1.parameters.platform_id == "1900121"

        res2 = interpreter.interpret("Find observations for platform #1900121")
        assert res2.parameters.platform_id == "1900121"

        res3 = interpreter.interpret("What was the salinity of 1900121?")
        assert res3.parameters.platform_id == "1900121"

    def test_extract_cycle_number(self, interpreter):
        """Verifies extraction of dive cycle numbers."""
        res = interpreter.interpret("Show salinity for float 1900121 cycle 2")
        assert res.parameters.cycle_number == 2
        assert res.intent == "query_observations"

        res_hash = interpreter.interpret("Show float 1900121 cycle #3 data")
        assert res_hash.parameters.cycle_number == 3

    def test_extract_depth_range(self, interpreter):
        """Verifies extraction of pressure/depth intervals."""
        res_between = interpreter.interpret("Show float 1900121 temperature between 0 and 500m")
        assert res_between.parameters.min_depth == 0.0
        assert res_between.parameters.max_depth == 500.0

        res_dbar = interpreter.interpret("Check salinity between 10 and 200 dbar for float 1900121")
        assert res_dbar.parameters.min_depth == 10.0
        assert res_dbar.parameters.max_depth == 200.0

        res_surface = interpreter.interpret("Surface temperature for float 1900121")
        assert res_surface.parameters.min_depth == 0.0
        assert res_surface.parameters.max_depth == 10.0

        res_shallow = interpreter.interpret("Shallow water observations for float 1900121")
        assert res_shallow.parameters.min_depth == 0.0
        assert res_shallow.parameters.max_depth == 200.0

        res_deep = interpreter.interpret("What is the deep ocean salinity for float 1900121?")
        assert res_deep.parameters.min_depth == 1000.0

    def test_extract_date_range(self, interpreter):
        """Verifies extraction of date ranges and calendar months."""
        res_month = interpreter.interpret("Show profiles for float 1900121 in November 2002")
        assert res_month.parameters.start_date == "2002-11-01"
        assert res_month.parameters.end_date == "2002-11-30"

        res_iso = interpreter.interpret("Find float 1900121 data from 2002-11-01 to 2002-11-15")
        assert res_iso.parameters.start_date == "2002-11-01"
        assert res_iso.parameters.end_date == "2002-11-15"

        res_year = interpreter.interpret("Argo float data collected during 2002")
        assert res_year.parameters.start_date == "2002-01-01"
        assert res_year.parameters.end_date == "2002-12-31"

    def test_extract_variables(self, interpreter):
        """Verifies extraction of oceanographic measurement parameters."""
        res1 = interpreter.interpret("Show temperature and salinity for float 1900121")
        assert "TEMP" in res1.parameters.variables
        assert "PSAL" in res1.parameters.variables

        res2 = interpreter.interpret("Find pressure at deep ocean depths")
        assert "PRES" in res2.parameters.variables

    def test_extract_geographic_regions(self, interpreter):
        """Verifies mapping of known oceanographic regions to spatial bounding boxes."""
        res_arabian = interpreter.interpret("Find argo float profiles in the Arabian Sea")
        assert res_arabian.parameters.min_lat == 10.0
        assert res_arabian.parameters.max_lat == 25.0
        assert res_arabian.parameters.min_lon == 50.0
        assert res_arabian.parameters.max_lon == 75.0

        res_bay = interpreter.interpret("Argo data in the Bay of Bengal")
        assert res_bay.parameters.min_lat == 5.0
        assert res_bay.parameters.max_lat == 22.0

    def test_dataset_summary_intent(self, interpreter):
        """Verifies detection of dataset catalog and overview requests."""
        res = interpreter.interpret("What data do you have?")
        assert res.is_valid_query is True
        assert res.intent == "summary"

        res_overview = interpreter.interpret("Show dataset overview")
        assert res_overview.intent == "summary"

    def test_out_of_domain_queries(self, interpreter):
        """Verifies graceful rejection of out-of-domain and non-oceanographic prompts."""
        res1 = interpreter.interpret("How do I make chocolate chip cookies?")
        assert res1.is_valid_query is False
        assert res1.intent == "out_of_domain"

        res2 = interpreter.interpret("What is the stock price of Apple?")
        assert res2.is_valid_query is False
        assert res2.intent == "out_of_domain"

        res_empty = interpreter.interpret("   ")
        assert res_empty.is_valid_query is False
        assert res_empty.intent == "out_of_domain"


class TestArgoQueryParametersValidation:
    """Tests for Pydantic schema validation rules on ArgoQueryParameters."""

    def test_valid_parameters(self):
        """Verifies that valid parameter ranges pass validation."""
        params = ArgoQueryParameters(
            platform_id="1900121",
            cycle_number=1,
            min_lat=-15.0,
            max_lat=0.0,
            min_lon=50.0,
            max_lon=65.0,
            min_depth=0.0,
            max_depth=500.0,
            variables=["TEMP", "PSAL"],
        )
        assert params.platform_id == "1900121"
        assert params.min_depth == 0.0

    def test_invalid_latitude_bounds(self):
        """Verifies ValueError when min_lat > max_lat."""
        with pytest.raises(ValidationError) as exc:
            ArgoQueryParameters(min_lat=20.0, max_lat=10.0)
        assert "min_lat cannot be greater than max_lat" in str(exc.value)

    def test_invalid_depth_bounds(self):
        """Verifies ValueError when min_depth > max_depth."""
        with pytest.raises(ValidationError) as exc:
            ArgoQueryParameters(min_depth=500.0, max_depth=100.0)
        assert "min_depth cannot be greater than max_depth" in str(exc.value)
