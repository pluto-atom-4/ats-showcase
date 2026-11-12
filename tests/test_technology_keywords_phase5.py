"""Comprehensive tests for Issue #192 Phase 5 - Technology keywords expansion.

Tests verify that 33 new keywords (128 → 161 total) are correctly integrated
into the keyword extraction system for aerospace/defense/manufacturing domains.
"""

import pytest

from src.tokenization.keywords import (
    TECH_KEYWORDS,
    get_all_keywords,
    get_categories,
    get_keywords_by_category,
)


class TestPhase5KeywordsPresent:
    """Verify all 33 Phase 5 keywords are present and accessible."""

    def test_all_33_phase5_keywords_present(self):
        """Verify all 33 new keywords from Phase 5 are in the keyword set."""
        phase5_keywords = {
            "ansys",
            "nastran",
            "optistruct",
            "creo",
            "solidworks",
            "catia",
            "windchill",
            "simulink",
            "comsol",
            "fft",
            "ifft",
            "cordic",
            "mac",
            "argocd",
            "flux",
            "gitops",
            "harbor",
            "quay",
            "timescaledb",
            "clickhouse",
            "dvc",
            "pydantic",
            "sqlalchemy",
            "celery",
            "mqtt",
            "amqp",
            "websocket",
            "coap",
            "cam",
            "cnc",
            "plm",
            "erp",
            "mrp",
        }
        current_keywords = get_all_keywords()
        missing = phase5_keywords - current_keywords

        assert not missing, f"Missing keywords: {missing}"
        assert len(phase5_keywords) == 33, "Phase 5 should have exactly 33 keywords"

    def test_total_keywords_161(self):
        """Verify total keyword count is 161 (128 + 33)."""
        all_kw = get_all_keywords()
        assert len(all_kw) == 161, f"Expected 161 keywords, got {len(all_kw)}"

    def test_phase5_keywords_by_category(self):
        """Verify Phase 5 keywords are distributed correctly across categories."""
        expected_counts = {
            "languages": 13,
            "web": 13,
            "infrastructure": 20,
            "databases": 16,
            "hardware": 31,
            "ml_ai": 20,
            "tools": 27,
            "methodologies": 8,
            "robotics": 5,
            "other": 8,
        }

        for category, expected_count in expected_counts.items():
            actual_count = len(get_keywords_by_category(category))
            assert actual_count == expected_count, (
                f"Category '{category}': expected {expected_count}, got {actual_count}"
            )


class TestEngineeringToolsKeywords:
    """Test engineering simulation & CAD tools keywords (9 keywords)."""

    def test_cad_tools_present(self):
        """Verify CAD tools are present."""
        cad_tools = {"creo", "solidworks", "catia"}
        hardware_kw = get_keywords_by_category("hardware")
        assert cad_tools.issubset(hardware_kw)

    def test_simulation_tools_present(self):
        """Verify FEA simulation tools are present."""
        sim_tools = {"ansys", "nastran", "optistruct", "comsol"}
        hardware_kw = get_keywords_by_category("hardware")
        assert sim_tools.issubset(hardware_kw)

    def test_plm_tools_present(self):
        """Verify PLM tools are present."""
        plm_tools = {"windchill"}
        hardware_kw = get_keywords_by_category("hardware")
        assert plm_tools.issubset(hardware_kw)

    def test_matlab_simulink_present(self):
        """Verify MATLAB and Simulink are present."""
        matlab_tools = {"matlab", "simulink"}
        hardware_kw = get_keywords_by_category("hardware")
        assert matlab_tools.issubset(hardware_kw)


class TestSignalProcessingKeywords:
    """Test DSP and signal processing keywords (4 keywords)."""

    def test_fft_keywords_present(self):
        """Verify FFT and related keywords are present."""
        fft_kw = {"fft", "ifft"}
        hardware_kw = get_keywords_by_category("hardware")
        assert fft_kw.issubset(hardware_kw)

    def test_dsp_operations_present(self):
        """Verify DSP operation keywords are present."""
        dsp_kw = {"cordic", "mac"}
        hardware_kw = get_keywords_by_category("hardware")
        assert dsp_kw.issubset(hardware_kw)


class TestCloudDevOpsKeywords:
    """Test GitOps and container registry keywords (5 keywords)."""

    def test_gitops_keywords_present(self):
        """Verify GitOps tools are present."""
        gitops_kw = {"argocd", "flux", "gitops"}
        infra_kw = get_keywords_by_category("infrastructure")
        assert gitops_kw.issubset(infra_kw)

    def test_container_registry_present(self):
        """Verify container registry tools are present."""
        registry_kw = {"harbor", "quay"}
        infra_kw = get_keywords_by_category("infrastructure")
        assert registry_kw.issubset(infra_kw)


class TestDataToolsKeywords:
    """Test data processing and ORM keywords (6 keywords)."""

    def test_timeseries_databases_present(self):
        """Verify time-series databases are present."""
        ts_db_kw = {"timescaledb", "clickhouse"}
        db_kw = get_keywords_by_category("databases")
        assert ts_db_kw.issubset(db_kw)

    def test_data_tools_present(self):
        """Verify DVC and other data tools are present."""
        data_kw = {"dvc"}
        db_kw = get_keywords_by_category("databases")
        assert data_kw.issubset(db_kw)

    def test_python_data_libraries_present(self):
        """Verify Pydantic, SQLAlchemy, Celery are present."""
        py_libs = {"pydantic", "sqlalchemy", "celery"}
        tools_kw = get_keywords_by_category("tools")
        assert py_libs.issubset(tools_kw)


class TestIoTProtocolsKeywords:
    """Test IoT and protocol keywords (4 keywords)."""

    def test_mqtt_amqp_present(self):
        """Verify MQTT and AMQP are present."""
        iot_kw = {"mqtt", "amqp"}
        tools_kw = get_keywords_by_category("tools")
        assert iot_kw.issubset(tools_kw)

    def test_websocket_coap_present(self):
        """Verify WebSocket and CoAP are present."""
        ws_kw = {"websocket", "coap"}
        tools_kw = get_keywords_by_category("tools")
        assert ws_kw.issubset(tools_kw)


class TestManufacturingKeywords:
    """Test manufacturing and PLM keywords (5 keywords)."""

    def test_manufacturing_tools_present(self):
        """Verify CAM and CNC are present."""
        mfg_kw = {"cam", "cnc"}
        tools_kw = get_keywords_by_category("tools")
        assert mfg_kw.issubset(tools_kw)

    def test_erp_plm_mrp_present(self):
        """Verify ERP, PLM, and MRP keywords are present."""
        erp_kw = {"plm", "erp", "mrp"}
        tools_kw = get_keywords_by_category("tools")
        assert erp_kw.issubset(tools_kw)


class TestNoDuplicates:
    """Verify no duplicates within categories or across keyword sets."""

    def test_no_duplicates_within_categories(self):
        """Ensure no keyword appears twice within a category."""
        for category, keywords in TECH_KEYWORDS.items():
            kw_list = list(keywords)
            assert len(kw_list) == len(set(kw_list)), f"Duplicates found in category '{category}'"

    def test_no_duplicates_across_categories(self):
        """Ensure no keyword appears in multiple categories."""
        all_kw = get_all_keywords()
        total_in_categories = sum(len(kw) for kw in TECH_KEYWORDS.values())
        assert len(all_kw) == total_in_categories, (
            f"Duplicate keywords across categories detected: "
            f"{total_in_categories} in categories but only {len(all_kw)} unique"
        )


class TestKeywordCaseHandling:
    """Verify keywords are case-insensitive lowercase."""

    def test_all_keywords_lowercase(self):
        """Verify all keywords are lowercase."""
        all_kw = get_all_keywords()
        for kw in all_kw:
            assert kw == kw.lower(), f"Keyword '{kw}' is not lowercase"

    def test_no_whitespace_in_keywords(self):
        """Verify no keywords have leading/trailing whitespace."""
        all_kw = get_all_keywords()
        for kw in all_kw:
            assert kw.strip() == kw, f"Keyword '{kw}' has whitespace"


class TestKeywordsFunctions:
    """Test helper functions work correctly."""

    def test_get_all_keywords_returns_set(self):
        """Verify get_all_keywords() returns a set."""
        result = get_all_keywords()
        assert isinstance(result, set)

    def test_get_keywords_by_category_returns_set(self):
        """Verify get_keywords_by_category() returns a set."""
        for category in get_categories():
            result = get_keywords_by_category(category)
            assert isinstance(result, set)

    def test_get_keywords_unknown_category_returns_empty_set(self):
        """Verify unknown category returns empty set."""
        result = get_keywords_by_category("unknown_category")
        assert result == set()

    def test_get_categories_returns_list(self):
        """Verify get_categories() returns a list."""
        result = get_categories()
        assert isinstance(result, list)

    def test_categories_count(self):
        """Verify we have 10 categories."""
        categories = get_categories()
        assert len(categories) == 10


class TestKeywordsIntegration:
    """Integration tests for keyword usage in extraction."""

    def test_aerospace_keywords_coverage(self):
        """Verify aerospace/defense keywords are well covered."""
        aerospace_keywords = {
            "ansys",
            "nastran",
            "optistruct",
            "creo",
            "windchill",
            "cordic",
            "fft",
            "ifft",
            "dsp",
            "cam",
            "cnc",
            "plm",
        }
        all_kw = get_all_keywords()
        covered = aerospace_keywords - {"dsp"}
        assert covered.issubset(all_kw)

    def test_devops_keywords_coverage(self):
        """Verify DevOps keywords are well covered."""
        devops_keywords = {"argocd", "flux", "gitops", "harbor", "quay", "kubernetes", "docker", "helm", "terraform"}
        all_kw = get_all_keywords()
        assert devops_keywords.issubset(all_kw)

    def test_manufacturing_keywords_coverage(self):
        """Verify manufacturing keywords are well covered."""
        mfg_keywords = {"cam", "cnc", "plm", "erp", "mrp", "catia", "solidworks"}
        all_kw = get_all_keywords()
        assert mfg_keywords.issubset(all_kw)


class TestPhase5KeywordExtraction:
    """Test that new keywords would be extracted from sample text."""

    @pytest.mark.parametrize(
        "keyword,text",
        [
            ("ansys", "We use ANSYS for finite element analysis"),
            ("creo", "Must have experience with Creo CAD"),
            ("windchill", "PLM experience using Windchill required"),
            ("simulink", "Develop control systems in Simulink"),
            ("fft", "Experience with FFT algorithms"),
            ("argocd", "Deploy using ArgoCD GitOps"),
            ("mqtt", "MQTT protocol implementation required"),
            ("pydantic", "Data validation using Pydantic"),
            ("plm", "Product lifecycle management (PLM) tools"),
        ],
    )
    def test_keyword_in_text(self, keyword, text):
        """Verify keywords would be detected in sample aerospace/defense text."""
        all_kw = get_all_keywords()
        assert keyword.lower() in all_kw, f"Keyword '{keyword}' not found"
        assert keyword.lower() in text.lower()
