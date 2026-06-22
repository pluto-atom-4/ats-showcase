"""Unit tests for CLI date filtering functionality."""

import pytest

from storage.export import ExportConfig, parse_date_str


class TestDateParsing:
    """Test date parsing at CLI boundary."""

    def test_valid_date_parsing(self):
        """Test valid ISO 8601 dates."""
        valid_dates = [
            ("2026-01-01", (2026, 1, 1)),
            ("2026-12-31", (2026, 12, 31)),
            ("2025-06-15", (2025, 6, 15)),
        ]

        for date_str, (year, month, day) in valid_dates:
            dt = parse_date_str(date_str)
            assert dt is not None
            assert dt.year == year
            assert dt.month == month
            assert dt.day == day

    def test_invalid_date_formats(self):
        """Test various invalid date formats."""
        invalid_dates = [
            "05-31-2026",  # MM-DD-YYYY
            "31/05/2026",  # DD/MM/YYYY
            "2026/05/31",  # YYYY/MM/DD
            "May 31, 2026",  # Text format
            "2026.05.31",  # Dot separator
        ]

        for date_str in invalid_dates:
            with pytest.raises(ValueError, match="Invalid date format"):
                parse_date_str(date_str)

    def test_invalid_dates(self):
        """Test invalid calendar dates."""
        invalid_dates = [
            "2026-13-01",  # Invalid month
            "2026-05-32",  # Invalid day
            "2026-02-30",  # Feb 30 (invalid)
        ]

        for date_str in invalid_dates:
            with pytest.raises(ValueError, match="Invalid date format"):
                parse_date_str(date_str)

    def test_date_parsing_edge_cases(self):
        """Test edge case dates."""
        # Leap year
        dt = parse_date_str("2024-02-29")
        assert dt.day == 29
        assert dt.month == 2

        # Year boundaries
        dt = parse_date_str("2000-01-01")
        assert dt.year == 2000

        dt = parse_date_str("2099-12-31")
        assert dt.year == 2099

    def test_date_timezone_normalization(self):
        """Test dates are normalized to UTC."""
        dt = parse_date_str("2026-05-15")
        assert dt.tzinfo is not None
        assert str(dt.tzinfo) == "UTC"


class TestExportConfigDateValidation:
    """Test ExportConfig date validation."""

    def test_valid_date_range(self):
        """Test valid date range."""
        date_from = parse_date_str("2026-05-01")
        date_to = parse_date_str("2026-05-31")

        config = ExportConfig(date_from=date_from, date_to=date_to)
        assert config.date_from == date_from
        assert config.date_to == date_to

    def test_equal_dates_valid(self):
        """Test equal from and to dates are valid."""
        date = parse_date_str("2026-05-15")
        config = ExportConfig(date_from=date, date_to=date)
        assert config.date_from == date
        assert config.date_to == date

    def test_invalid_date_range(self):
        """Test invalid date range (from > to)."""
        date_from = parse_date_str("2026-05-31")
        date_to = parse_date_str("2026-05-01")

        with pytest.raises(ValueError, match="date_from must be <= date_to"):
            ExportConfig(date_from=date_from, date_to=date_to)

    def test_date_from_only(self):
        """Test date_from only (no date_to)."""
        date_from = parse_date_str("2026-05-01")
        config = ExportConfig(date_from=date_from)
        assert config.date_from == date_from
        assert config.date_to is None

    def test_date_to_only(self):
        """Test date_to only (no date_from)."""
        date_to = parse_date_str("2026-05-31")
        config = ExportConfig(date_to=date_to)
        assert config.date_from is None
        assert config.date_to == date_to

    def test_no_dates(self):
        """Test no dates (should be valid)."""
        config = ExportConfig()
        assert config.date_from is None
        assert config.date_to is None


class TestScoreValidation:
    """Test score range validation."""

    def test_valid_score_range(self):
        """Test valid score ranges."""
        config = ExportConfig(min_score=50, max_score=75)
        assert config.min_score == 50
        assert config.max_score == 75

    def test_equal_scores_valid(self):
        """Test equal min and max scores are valid."""
        config = ExportConfig(min_score=75, max_score=75)
        assert config.min_score == 75
        assert config.max_score == 75

    def test_invalid_score_range(self):
        """Test min > max scores."""
        with pytest.raises(ValueError, match="min_score must be <= max_score"):
            ExportConfig(min_score=75, max_score=50)

    def test_score_boundary_0_100(self):
        """Test score boundaries."""
        config = ExportConfig(min_score=0, max_score=100)
        assert config.min_score == 0
        assert config.max_score == 100

    def test_invalid_min_score_negative(self):
        """Test negative min_score."""
        with pytest.raises(ValueError, match="min_score must be 0-100"):
            ExportConfig(min_score=-1)

    def test_invalid_min_score_over_100(self):
        """Test min_score > 100."""
        with pytest.raises(ValueError, match="min_score must be 0-100"):
            ExportConfig(min_score=101)

    def test_invalid_max_score_negative(self):
        """Test negative max_score."""
        with pytest.raises(ValueError, match="max_score must be 0-100"):
            ExportConfig(max_score=-1)

    def test_invalid_max_score_over_100(self):
        """Test max_score > 100."""
        with pytest.raises(ValueError, match="max_score must be 0-100"):
            ExportConfig(max_score=101)


class TestCombinedFilters:
    """Test combining date and score filters."""

    def test_date_and_score_filters(self):
        """Test combining date and score filters."""
        date_from = parse_date_str("2026-05-01")
        date_to = parse_date_str("2026-05-31")

        config = ExportConfig(
            min_score=70,
            max_score=90,
            date_from=date_from,
            date_to=date_to,
        )

        assert config.min_score == 70
        assert config.max_score == 90
        assert config.date_from == date_from
        assert config.date_to == date_to

    def test_all_filters_together(self):
        """Test all filter types together."""
        date_from = parse_date_str("2026-05-01")
        date_to = parse_date_str("2026-05-31")

        config = ExportConfig(
            min_score=75,
            max_score=95,
            sort_by="company",
            template_style="summary",
            include_recommendations=False,
            include_stats=False,
            date_from=date_from,
            date_to=date_to,
        )

        assert config.min_score == 75
        assert config.max_score == 95
        assert config.sort_by == "company"
        assert config.template_style == "summary"
        assert config.include_recommendations is False
        assert config.include_stats is False
        assert config.date_from == date_from
        assert config.date_to == date_to


class TestDateFilterEdgeCases:
    """Test edge cases for date filtering."""

    def test_wide_date_range(self):
        """Test very wide date range."""
        date_from = parse_date_str("2000-01-01")
        date_to = parse_date_str("2099-12-31")

        config = ExportConfig(date_from=date_from, date_to=date_to)
        assert config.date_from < config.date_to

    def test_single_day_range(self):
        """Test single day date range."""
        date = parse_date_str("2026-06-22")

        config = ExportConfig(date_from=date, date_to=date)
        assert config.date_from == config.date_to

    def test_leap_year_february(self):
        """Test leap year February 29th."""
        dt = parse_date_str("2024-02-29")
        assert dt.month == 2
        assert dt.day == 29

    def test_year_2000(self):
        """Test year 2000 (Y2K)."""
        dt = parse_date_str("2000-01-01")
        assert dt.year == 2000

    def test_future_year(self):
        """Test future year."""
        dt = parse_date_str("2099-12-31")
        assert dt.year == 2099
        assert dt.month == 12
        assert dt.day == 31


class TestSortValidation:
    """Test sort_by validation."""

    def test_valid_sort_options(self):
        """Test all valid sort options."""
        for sort_by in ["score", "company", "location"]:
            config = ExportConfig(sort_by=sort_by)
            assert config.sort_by == sort_by

    def test_invalid_sort_option(self):
        """Test invalid sort option."""
        with pytest.raises(ValueError, match="sort_by must be"):
            ExportConfig(sort_by="invalid")


class TestTemplateValidation:
    """Test template_style validation."""

    def test_valid_templates(self):
        """Test all valid templates."""
        for template in ["detailed", "summary"]:
            config = ExportConfig(template_style=template)
            assert config.template_style == template

    def test_invalid_template(self):
        """Test invalid template."""
        with pytest.raises(ValueError, match="template_style must be"):
            ExportConfig(template_style="html")
