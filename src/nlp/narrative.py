"""Narrative requirement extraction from prose text."""

import re
from typing import Set

from spacy.language import Language
from spacy.tokens import Span


class NarrativeRequirementExtractor:
    """Extract requirements from narrative/prose text using NLP."""

    def __init__(self, nlp_model: Language) -> None:
        """Initialize with spaCy NLP model."""
        self.nlp = nlp_model

    def extract_narrative_requirements(self, text: str) -> Set[str]:
        """Extract requirements from narrative text.

        Strategy:
        1. Identify requirement-bearing clauses (gerunds, infinitives, role patterns)
        2. Split complex sentences into semantic units
        3. Filter for requirement-like phrases
        """
        requirements = set()

        requirement_triggers = [
            r"experience\s+(?:with|in|using|involving|developing|designing)",
            r"ability\s+to\s+(?:work|develop|design|manage|lead|test|implement)",
            r"(?:demonstrated|proven)\s+(?:experience|ability|knowledge|expertise)",
            r"(?:knowledge|expertise)\s+(?:of|in|with)",
            r"(?:familiarity|proficiency)\s+(?:with|in)",
            r"(?:strong|deep)\s+(?:experience|knowledge|background)",
            r"experience\s+(?:leading|managing|working)",
            r"(?:degree|certification|credential)\s+(?:in|from)",
            r"(?:must|should|required\s+to)\s+(?:have|be|know)",
            r"(?:ability|willingness)\s+to\s+",
        ]

        doc = self.nlp(text)

        sentences = list(doc.sents)

        for sent in sentences:
            sent_text = sent.text.strip()

            # Skip very short sentences and bullets
            if len(sent_text) < 15 or sent_text.startswith(("•", "*", "-", "●")):
                continue

            has_trigger = any(re.search(trigger, sent_text, re.IGNORECASE) for trigger in requirement_triggers)

            if has_trigger:
                req = self._extract_requirement_from_sentence(sent)
                if req and 15 < len(req) < 200:
                    requirements.add(req)

        return requirements

    def _extract_requirement_from_sentence(self, sent: Span) -> str:
        """Extract core requirement from a sentence.

        Handles:
        - Gerund phrases: "Experience working with X"
        - Infinitive phrases: "Ability to manage large teams"
        - Predicate nominatives: "Knowledge of C++"
        """
        text = sent.text.strip()

        text = re.sub(r"\s*\([^)]*\)\s*$", "", text)

        text = re.sub(r"[,;.!?]+$", "", text)

        text = re.sub(r"\s+", " ", text)

        return text if text else ""

    def extract_skill_requirements(self, text: str) -> Set[str]:
        """Extract skill-like requirements from narrative text.

        Targets: "experience with X", "knowledge of Y", "expertise in Z"
        """
        skills = set()

        # Skill extraction patterns
        patterns = [
            (r"experience\s+(?:with|in|using)\s+([^,\.;]+?)(?:\s+and|\s+or|,|\.|\s+for)", 1),
            (r"expertise\s+(?:in|with)\s+([^,\.;]+?)(?:\s+and|\s+or|,|\.|\s+for)", 1),
            (r"(?:strong|deep)\s+(?:knowledge|background)\s+(?:in|with)\s+([^,\.;]+?)(?:\s+and|\s+or|,|\.|\s+for)", 1),
            (r"proficiency\s+(?:with|in)\s+([^,\.;]+?)(?:\s+and|\s+or|,|\.|\s+for)", 1),
        ]

        for pattern, group_idx in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                skill = match.group(group_idx).strip()
                # Filter out boilerplate
                if skill and not any(x in skill.lower() for x in ["environments", "languages"]):
                    skills.add(skill)

        return skills

    def extract_qualification_requirements(self, text: str) -> Set[str]:
        """Extract degree/certification requirements from narrative."""
        qualifications = set()

        # Degree patterns
        degree_patterns = [
            r"(?:B\.?S\.?|Bachelor[''s]*)\s+(?:Degree|of\s+Science)\s+(?:in|from)\s+([^,\.;]+)",
            r"(?:M\.?S\.?|Master[''s]*)\s+(?:Degree|of\s+Science)\s+(?:in|from)\s+([^,\.;]+)",
            r"(?:Ph\.?D\.?|PhD)\s+(?:in|from|of)\s+([^,\.;]+)",
            r"(?:Certification|Certified)\s+(?:in|from|by)\s+([^,\.;]+)",
        ]

        for pattern in degree_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                full_match = match.group(0).strip()
                qualifications.add(full_match)

        return qualifications

    def extract_responsibility_requirements(self, text: str) -> Set[str]:
        """Extract work responsibility/experience requirements.

        Targets: "led X-person team", "developed Y systems", "managed Z projects"
        """
        responsibilities = set()

        doc = self.nlp(text)
        sentences = list(doc.sents)

        # Patterns for responsibilities (past tense, leadership, execution)
        resp_patterns = [
            r"(?:led|managed|directed|supervised)\s+([^,\.;]+?)(?:\s+(?:team|group|department)|,|\.)",
            r"(?:developed|designed|implemented|built)\s+([^,\.;]+?)(?:\s+system|s|,|\.)",
            r"(?:oversaw|owned|drove)\s+([^,\.;]+?)(?:\s+project|s|,|\.)",
        ]

        for sent in sentences:
            sent_text = sent.text
            for pattern in resp_patterns:
                for match in re.finditer(pattern, sent_text, re.IGNORECASE):
                    resp = match.group(0).strip().rstrip(",;.")
                    if resp and 10 < len(resp) < 150:
                        responsibilities.add(resp)

        return responsibilities

    def extract_soft_skills(self, text: str) -> Set[str]:
        """Extract soft skill requirements from narrative."""
        soft_skills = set()

        # Soft skill phrases
        soft_skill_patterns = [
            r"(?:strong|excellent|exceptional)\s+(?:communication|interpersonal|leadership|organizational|problem.?solving|analytical|critical.?thinking)\s+(?:skill|ability|capacit)",
            r"(?:ability|capacity)\s+to\s+(?:work|collaborate|communicate)\s+(?:effectively|independently|with\s+(?:team|group|diverse))",
            r"(?:team)?(?:player|oriented)|collaborative|detail.?oriented",
        ]

        for pattern in soft_skill_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                skill = match.group(0).strip()
                soft_skills.add(skill)

        return soft_skills
