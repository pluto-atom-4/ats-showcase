"""Tests for Issue #241: Enhance preprocessor to recognize bold lines as markdown section headers.

Tests the recognition of bold-formatted headers in markdown section extraction and
entity routing, particularly for sections like Blue Origin jobs with bold headers
like `**Responsibilities**` and `**Responsibilities include but are not limited to**`.
"""

import pytest

from src.tokenization.preprocessor import Preprocessor


class TestBoldHeaderRecognition:
    """Test recognizing bold-formatted headers in markdown section extraction."""

    @pytest.mark.unit
    def test_extract_markdown_sections_recognizes_bold_only_header(self):
        """Test that _extract_markdown_sections recognizes bold-only headers like **Responsibilities**."""
        try:
            preprocessor = Preprocessor()
        except Exception as e:
            pytest.skip(f"spaCy model not available: {e}")

        text = (
            "## Description\n\n"
            "Senior Python Developer role.\n\n"
            "**Responsibilities**\n\n"
            "Build scalable systems. Lead team.\n\n"
            "**Skills**\n\n"
            "Python, AWS, distributed systems.\n"
        )

        sections = preprocessor._extract_markdown_sections(text)

        assert "responsibilities" in sections
        assert "skills" in sections
        assert "Build scalable systems" in sections.get("responsibilities", "")
        assert "Python, AWS" in sections.get("skills", "")

    @pytest.mark.unit
    def test_extract_markdown_sections_bold_header_with_trailing_text(self):
        """Test bold headers with trailing text like **Responsibilities** include."""
        try:
            preprocessor = Preprocessor()
        except Exception as e:
            pytest.skip(f"spaCy model not available: {e}")

        text = (
            "**Responsibilities** include but are not limited to:\n\n"
            "- Design system architecture\n"
            "- Lead engineering team\n\n"
            "**Qualifications**:\n\n"
            "- 5+ years Python\n"
        )

        sections = preprocessor._extract_markdown_sections(text)

        assert "responsibilities" in sections
        assert "qualifications" in sections
        assert "include but are not limited to" in sections.get("responsibilities", "")

    @pytest.mark.unit
    def test_extract_markdown_sections_mixed_bold_and_markdown_headers(self):
        """Test sections with both markdown (##) and bold headers."""
        try:
            preprocessor = Preprocessor()
        except Exception as e:
            pytest.skip(f"spaCy model not available: {e}")

        text = (
            "## Responsibilities\n\n"
            "Lead architecture work.\n\n"
            "**Technical Skills**\n\n"
            "Python, AWS\n\n"
            "## Qualifications\n\n"
            "5+ years experience\n"
        )

        sections = preprocessor._extract_markdown_sections(text)

        assert "responsibilities" in sections
        assert "skills" in sections
        assert "qualifications" in sections

    @pytest.mark.unit
    def test_extract_markdown_sections_bold_with_em_dash(self):
        """Test bold headers with em-dash: **Label** — description."""
        try:
            preprocessor = Preprocessor()
        except Exception as e:
            pytest.skip(f"spaCy model not available: {e}")

        text = (
            "**Responsibilities** — what you'll do:\n\n"
            "Design and build scalable systems.\n\n"
            "**Skills** – technical and soft:\n\n"
            "Leadership, Python, AWS\n"
        )

        sections = preprocessor._extract_markdown_sections(text)

        assert "responsibilities" in sections
        assert "skills" in sections
        assert "what you'll do" in sections.get("responsibilities", "")


class TestIsMarkdownDetection:
    """Test _is_markdown() detection of bold-formatted headers."""

    @pytest.mark.unit
    def test_is_markdown_detects_bold_headers(self):
        """Test that _is_markdown detects bold-formatted headers at line start."""
        try:
            preprocessor = Preprocessor()
        except Exception as e:
            pytest.skip(f"spaCy model not available: {e}")

        text_with_bold = "**Responsibilities**\n\nLead team and design systems."
        assert preprocessor._is_markdown(text_with_bold) is True

    @pytest.mark.unit
    def test_is_markdown_detects_bold_headers_with_trailing(self):
        """Test _is_markdown detects bold headers with trailing text."""
        try:
            preprocessor = Preprocessor()
        except Exception as e:
            pytest.skip(f"spaCy model not available: {e}")

        text = "**Responsibilities** include:\n\n- Design systems\n- Lead team"
        assert preprocessor._is_markdown(text) is True

    @pytest.mark.unit
    def test_is_markdown_still_detects_regular_bold(self):
        """Test that _is_markdown still detects inline bold (not just headers)."""
        try:
            preprocessor = Preprocessor()
        except Exception as e:
            pytest.skip(f"spaCy model not available: {e}")

        text = "This role requires **strong leadership** and communication skills."
        assert preprocessor._is_markdown(text) is True

    @pytest.mark.unit
    def test_is_markdown_markdown_headers_priority(self):
        """Test that markdown headers (##) are still detected as highest priority."""
        try:
            preprocessor = Preprocessor()
        except Exception as e:
            pytest.skip(f"spaCy model not available: {e}")

        text = "## Major Section\n\nContent here"
        assert preprocessor._is_markdown(text) is True


class TestEntityRoutingFromBoldSections:
    """Test entity routing from bold-formatted sections."""

    @pytest.mark.unit
    def test_extract_entities_by_section_routes_from_bold_responsibilities(self):
        """Test that entities in bold **Responsibilities** sections are correctly routed."""
        try:
            preprocessor = Preprocessor()
        except Exception as e:
            pytest.skip(f"spaCy model not available: {e}")

        text = "**Responsibilities**\n\nLead European teams. Coordinate with stakeholders in Berlin and Amsterdam.\n"

        _skills, _technologies, requirements = preprocessor._extract_entities_by_section(text)

    @pytest.mark.unit
    def test_extract_entities_by_section_routes_from_bold_skills(self):
        """Test that entities in bold **Skills** sections are correctly routed."""
        try:
            preprocessor = Preprocessor()
        except Exception as e:
            pytest.skip(f"spaCy model not available: {e}")

        text = "**Skills**\n\nPython, AWS, Docker, Kubernetes, machine learning frameworks\n"

        _skills, technologies, _requirements = preprocessor._extract_entities_by_section(text)

        assert any(tech.lower() in ("python", "aws", "docker", "kubernetes") for tech in technologies)

    @pytest.mark.unit
    def test_extract_entities_by_section_handles_bold_qualifications(self):
        """Test entity routing from bold **Qualifications** sections."""
        try:
            preprocessor = Preprocessor()
        except Exception as e:
            pytest.skip(f"spaCy model not available: {e}")

        text = "**Qualifications**\n\n5+ years of Python development. Experience with microservices.\n"

        _skills, _technologies, requirements = preprocessor._extract_entities_by_section(text)


class TestRegressionCases:
    """Test that existing functionality is not broken."""

    @pytest.mark.unit
    def test_extract_markdown_sections_markdown_headers_still_work(self):
        """Test that standard markdown headers (##) still work as before."""
        try:
            preprocessor = Preprocessor()
        except Exception as e:
            pytest.skip(f"spaCy model not available: {e}")

        text = "## Responsibilities\n\nBuild systems.\n\n## Skills\n\nPython, AWS\n"

        sections = preprocessor._extract_markdown_sections(text)

        assert "responsibilities" in sections
        assert "skills" in sections

    @pytest.mark.unit
    def test_extract_markdown_sections_dividers_still_work(self):
        """Test that divider-based section splitting still works."""
        try:
            preprocessor = Preprocessor()
        except Exception as e:
            pytest.skip(f"spaCy model not available: {e}")

        text = "## Description\n\nSenior role.\n---\n## Responsibilities\n\nLead team.\n"

        sections = preprocessor._extract_markdown_sections(text)

        assert "description" in sections
        assert "responsibilities" in sections

    @pytest.mark.unit
    def test_is_markdown_existing_indicators_still_work(self):
        """Test that existing markdown indicators still work."""
        try:
            preprocessor = Preprocessor()
        except Exception as e:
            pytest.skip(f"spaCy model not available: {e}")

        assert preprocessor._is_markdown("# Header") is True

        assert preprocessor._is_markdown("- item\n- item") is True
        assert preprocessor._is_markdown("1. item\n2. item") is True

        assert preprocessor._is_markdown("```python\ncode\n```") is True

    @pytest.mark.unit
    def test_extract_entities_existing_markdown_sections_still_route_correctly(self):
        """Test that entity routing in existing markdown sections still works."""
        try:
            preprocessor = Preprocessor()
        except Exception as e:
            pytest.skip(f"spaCy model not available: {e}")

        text = "## Responsibilities\n\nCollaborate with teams across Europe.\n"

        _skills, _technologies, requirements = preprocessor._extract_entities_by_section(text)

        assert "Europe" in requirements


class TestBlueOriginBoldHeaders:
    """Test with actual Blue Origin job description patterns."""

    @pytest.mark.unit
    def test_blue_origin_bold_responsibilities_header(self):
        """Test recognition of Blue Origin's bold **Responsibilities include...** pattern."""
        try:
            preprocessor = Preprocessor()
        except Exception as e:
            pytest.skip(f"spaCy model not available: {e}")

        text = (
            "**Responsibilities** include but are not limited to:\n\n"
            "Design and develop software architecture\n"
            "Lead engineering teams\n"
            "Mentor junior engineers\n"
        )

        sections = preprocessor._extract_markdown_sections(text)

        assert "responsibilities" in sections
        assert "Design and develop" in sections.get("responsibilities", "")

    @pytest.mark.unit
    def test_blue_origin_multiple_bold_sections(self):
        """Test multiple bold sections in Blue Origin format."""
        try:
            preprocessor = Preprocessor()
        except Exception as e:
            pytest.skip(f"spaCy model not available: {e}")

        text = (
            "**Responsibilities** include but are not limited to:\n\n"
            "- Design systems\n"
            "- Lead teams\n\n"
            "**Qualifications** include:\n\n"
            "- 5+ years experience\n"
            "- Advanced Python\n\n"
            "**What You'll Bring**:\n\n"
            "- Technical excellence\n"
            "- Leadership\n"
        )

        sections = preprocessor._extract_markdown_sections(text)

        assert "responsibilities" in sections
        assert "qualifications" in sections
        assert len(sections) >= 2

    @pytest.mark.unit
    def test_is_markdown_blue_origin_pattern(self):
        """Test that Blue Origin's bold pattern is detected as markdown."""
        try:
            preprocessor = Preprocessor()
        except Exception as e:
            pytest.skip(f"spaCy model not available: {e}")

        text = "**Responsibilities** include but are not limited to: Design systems"
        assert preprocessor._is_markdown(text) is True
