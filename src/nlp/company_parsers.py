"""Company-specific requirement parsers."""

import re
from abc import ABC, abstractmethod
from typing import Dict, Set


class CompanyParser(ABC):
    """Base class for company-specific requirement parsing."""

    company_name: str

    @abstractmethod
    def parse_requirements(self, text: str) -> Set[str]:
        """Parse requirements specific to this company's format."""
        pass

    def extract_section(self, text: str, section_pattern: str) -> str:
        """Extract a specific section from the text."""
        match = re.search(section_pattern, text, re.IGNORECASE | re.DOTALL)
        return match.group(1) if match else ""


class BlueOriginParser(CompanyParser):
    """Blue Origin-specific requirement parser."""

    company_name = "blue origin"

    def parse_requirements(self, text: str) -> Set[str]:
        """Parse Blue Origin's structured bullet format."""
        requirements = set()

        min_qual = self.extract_section(
            text,
            r"(?:##\s+)?(?:minimum|required)\s+(?:qualifications?|experience)[\s\n:]*(.+?)(?=\n##|Preferred|---|\Z)",
        )

        if min_qual:
            bullets = re.findall(r"[\*•\-]\s+(.+?)(?:\n|$)", min_qual)
            for bullet in bullets:
                bullet = bullet.strip()
                # Keep bullets unless they're ONLY about years (no domain context)
                is_only_years = re.match(r"^\d+\+?\s+years\s+of\s+experience\s*$", bullet, re.IGNORECASE)
                if 10 < len(bullet) < 150 and not is_only_years:
                    requirements.add(bullet)

        # Years of experience (only add if domain specified)
        years_pattern = (
            r"(\d+)\+?\s+years\s+(?:of\s+)?experience"
            r"(?:\s+(?:in|with|focused\s+on)\s+([^\.\n]+))?"
        )
        for match in re.finditer(years_pattern, text, re.IGNORECASE):
            years = match.group(1)
            domain = match.group(2)
            if domain:
                domain = domain.strip().rstrip(".,;")
                requirements.add(f"{years}+ years of experience in {domain}")

        if re.search(r"background\s+check|security\s+clearance", text, re.IGNORECASE):
            requirements.add("Blue's Standard Background Check")

        if re.search(r"U\.S\.\s+(?:citizen|national)", text, re.IGNORECASE):
            requirements.add("U.S. citizen, national, permanent resident, refugee, or asylee status")

        return requirements


class BoeingParser(CompanyParser):
    """Boeing-specific requirement parser (narrative + structured)."""

    company_name = "boeing"

    def _extract_section_bullets(self, section: str) -> Set[str]:
        """Extract bullet points from a section."""
        bullets = set()
        matches = re.findall(r"[\*•\-]\s+(.+?)(?:\n|$)", section)
        for bullet in matches:
            bullet = bullet.strip()
            is_only_years = re.match(r"^\d+\+?\s+years\s+of\s+experience\s*$", bullet, re.IGNORECASE)
            if 10 < len(bullet) < 150 and not is_only_years:
                bullets.add(bullet)
        return bullets

    def _extract_years_experience(self, text: str) -> Set[str]:
        """Extract years of experience requirements."""
        years_reqs = set()
        pattern = r"(\d+)\+?\s+years\s+(?:of\s+)?experience(?:\s+(?:in|with|using|focused\s+on)\s+([^\.\n]+))?"
        for match in re.finditer(pattern, text, re.IGNORECASE):
            if match.group(2):
                domain = match.group(2).strip().rstrip(".,;")
                years_reqs.add(f"{match.group(1)}+ years of experience {domain}")
        return years_reqs

    def _extract_standard_requirements(self, text: str) -> Set[str]:
        """Extract standard requirements (degree, clearance, etc.)."""
        standard = set()
        if re.search(r"Bachelor[''s]*\s+(?:Degree|of\s+Science)", text, re.IGNORECASE):
            standard.add("Bachelor's Degree")
        if re.search(r"Top\s+Secret", text, re.IGNORECASE):
            standard.add("Ability to obtain a U.S. Security Clearance (requires U.S. Citizenship)")
        if re.search(r"U\.S\.\s+Person|export\s+control", text, re.IGNORECASE):
            standard.add("U.S. Person status as defined by 22 C.F.R. §120.62 for export control compliance")
        if re.search(r"CodeVue|coding\s+challenge", text, re.IGNORECASE):
            standard.add("Completion of the CodeVue Coding Challenge during the selection process")
        if re.search(r"drug", text, re.IGNORECASE):
            standard.add("Passing a post-offer drug test")
        return standard

    def _extract_preferred_bullets(self, section: str) -> Set[str]:
        """Extract preferred qualifications."""
        preferred = set()
        matches = re.findall(r"[\*•\-]\s+(.+?)(?:\n|$)", section)
        for bullet in matches:
            bullet = bullet.strip()
            if 10 < len(bullet) < 150:
                preferred.add(f"{bullet} (Preferred)")
        return preferred

    def parse_requirements(self, text: str) -> Set[str]:
        """Parse Boeing's mixed structured/narrative format."""
        requirements = set()

        basic_qual = self.extract_section(
            text,
            r"(?:#{2,3}\s+)?(?:basic|minimum|required)\s+(?:qualifications?|skills/experience)[\s\n:]*(.+?)(?=\n#{2,3}|Preferred|Travel|---|\Z)",
        )
        if basic_qual:
            requirements.update(self._extract_section_bullets(basic_qual))

        requirements.update(self._extract_years_experience(text))
        requirements.update(self._extract_standard_requirements(text))

        pref_qual = self.extract_section(
            text,
            r"(?:#{2,3}\s+)?(?:preferred|desired)\s+(?:qualifications?|experience)[\s\n:]*(.+?)(?=\n#{2,3}|Travel|Background|---|\Z)",
        )
        if pref_qual:
            requirements.update(self._extract_preferred_bullets(pref_qual))

        return requirements


class GenericParser(CompanyParser):
    """Generic fallback parser for unknown companies."""

    company_name = "generic"

    def parse_requirements(self, text: str) -> Set[str]:
        """Generic requirement extraction."""
        requirements = set()

        for section_label in [r"basic\s+qualifications", r"minimum\s+qualifications"]:
            section = self.extract_section(
                text, rf"(?:##\s+)?(?:{section_label})[\s\n:]*(.+?)(?=\n##|Preferred|---|\Z)"
            )
            if section:
                bullets = re.findall(r"[\*•\-]\s+(.+?)(?:\n|$)", section)
                for bullet in bullets:
                    bullet = bullet.strip()
                    is_only_years = re.match(r"^\d+\+?\s+years\s+of\s+experience\s*$", bullet, re.IGNORECASE)
                    if 10 < len(bullet) < 150 and not is_only_years:
                        requirements.add(bullet)
                break

        # Generic "X+ years of experience" lines are deliberately skipped: no domain context.
        if re.search(r"degree|bachelor|master", text, re.IGNORECASE):
            if not any("degree" in req.lower() for req in requirements):
                requirements.add("Bachelor's Degree or equivalent")

        return requirements


COMPANY_PARSERS: Dict[str, CompanyParser] = {
    "blue origin": BlueOriginParser(),
    "boeing": BoeingParser(),
}


def get_parser(company_name: str) -> CompanyParser:
    """Get parser for company, or generic fallback."""
    normalized = company_name.lower().strip()
    return COMPANY_PARSERS.get(normalized, GenericParser())
