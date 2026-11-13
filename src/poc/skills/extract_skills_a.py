import logging

import spacy
from spacy.matcher import Matcher
from spacy.tokens import Doc, Span, Token
from spacy.util import filter_spans

from .patterns import SKILL_VERBS

_SKILL_VERB_SET = frozenset(SKILL_VERBS)
_CONNECTOR_POS = ("ADP", "DET", "PART")

logger = logging.getLogger(__name__)

_NOUN_RUN_POS = ("ADJ", "NOUN", "PROPN")
_JOIN_CONJUNCTIONS = ("and", "or")
# Tech terms spaCy tags VERB (spelled like a verb, #604); "Go" in a language list is a noun-run token.
_TECH_TERMS_TAGGED_VERB = frozenset({"Go"})


def _is_noun_run_token(tok: Token) -> bool:
    """True for a token that can sit in a noun run: a noun-run POS, or a tech term tagged VERB (#604)."""
    return tok.pos_ in _NOUN_RUN_POS or (tok.pos_ == "VERB" and tok.text in _TECH_TERMS_TAGGED_VERB)


def _is_spaced_dash(tok: Token) -> bool:
    """True if a "-" token is not glued to both neighbours.

    spaCy keeps "high-performance" as [high, -, performance] with no whitespace
    around the "-", so the hyphen can join a noun run. A dash set off by spaces
    ("design systems - build tools") is punctuation and must end the span.
    Em/en dashes ("—", "–") are different tokens and never match the "-" pattern.
    """
    return tok.text == "-" and bool(tok.whitespace_ or tok.doc[tok.i - 1].whitespace_)


def _has_spaced_dash(span: Span) -> bool:
    """True if a "-" token in the span is not glued to both neighbours."""
    return any(_is_spaced_dash(tok) for tok in span)


# --- Verb tagged NOUN (#511)
# spaCy sometimes tags a coordinated skill verb NOUN (dep conj), so the Matcher never starts on it; the guard does.
# _conjunct_end() refuses it, so it is never merged into the preceding span.


def _is_verb_tagged_noun(tok: Token) -> bool:
    """True for a skill verb that spaCy tagged NOUN as a conjunct under a skill verb (#511).

    The coordination must be governed by a skill verb somewhere up the parse. Noun
    coordinations under another verb ("Our team includes the design and build
    managers") have the same tags but no skill verb above them, so they do not match.
    """
    if tok.pos_ != "NOUN" or tok.lemma_ not in _SKILL_VERB_SET:
        return False
    # spaCy tags "mentor" in "and mentor engineers" as compound, not conj (#604).
    after_conjunction = tok.i > 0 and _is_join_conjunction(tok.doc[tok.i - 1])
    if tok.dep_ != "conj" and not (tok.dep_ == "compound" and after_conjunction):
        return False
    return any(anc.pos_ == "VERB" and anc.lemma_ in _SKILL_VERB_SET for anc in tok.ancestors)


def _verb_start_end(doc: Doc, start: int) -> int | None:
    """End (exclusive) of the object of a verb-tagged-NOUN start at ``start``, or None.

    None unless the guard passes: the token is a verb-tagged-NOUN conjunct and an
    object noun run follows it, optionally after one connector.
    """
    if start >= len(doc) or not _is_verb_tagged_noun(doc[start]):
        return None
    obj = start + 1
    if obj < len(doc) and doc[obj].pos_ in _CONNECTOR_POS:
        obj += 1
    return _noun_run_end(doc, obj)


# --- Participle inside a noun run (#523)
# A participle tagged VERB (dep amod) joins the run only when a noun-run token follows; a trailing one is not absorbed.
# A participle with dep acl ("systems used internally") is a clause, not a modifier.


def _is_amod_participle(tok: Token) -> bool:
    """True for a VBN/VBG token tagged VERB that modifies the following noun (dep amod)."""
    return tok.pos_ == "VERB" and tok.tag_ in ("VBN", "VBG") and tok.dep_ == "amod"


def _noun_run_end(doc: Doc, start: int) -> int | None:
    """End (exclusive) of a noun run starting at ``start``, or None.

    The run is maximal over _NOUN_RUN_POS tokens and amod participles that precede
    a noun (see _run_end) and may contain one glued hyphen join ("high-performance").
    Spaced dashes end the run.
    """
    if start >= len(doc) or not _starts_noun_run(doc, start):
        return None
    end = _run_end(doc, start)
    if end < len(doc) and doc[end].text == "-" and not _is_spaced_dash(doc[end]):
        # The glued join may continue with a participle ("data-driven platforms", #556).
        if end + 1 < len(doc) and _starts_noun_run(doc, end + 1):
            end = _run_end(doc, end + 1)
    return end


# --- Skill verb tagged ADJ after a comma or conjunction (#604)
# spaCy tags "lead" ADJ in "design systems and lead teams"; it starts its own span only after a comma or conjunction.
# "lead agile, platform teams" is unaffected: its "lead" is sentence-led.


def _is_skill_verb_adjective(tok: Token) -> bool:
    return tok.pos_ == "ADJ" and tok.lemma_ in _SKILL_VERB_SET


def _skill_verb_adjective_end(doc: Doc, start: int) -> int | None:
    """End (exclusive) of a span headed by a skill verb tagged ADJ at ``start``, or None (#604)."""
    if start < 1 or start >= len(doc) or not _is_skill_verb_adjective(doc[start]):
        return None
    if doc[start - 1].text != "," and not _is_join_conjunction(doc[start - 1]):
        return None
    return _noun_run_end(doc, start + 1)


def _conjunct_end(doc: Doc, start: int) -> int | None:
    """End (exclusive) of a conjunct noun run starting at ``start``, or None.

    None also when ``start`` is a verb-tagged-NOUN that passes the #511 guard, or a
    skill verb tagged ADJ (#604): each starts its own match and must not be merged
    into the preceding span.
    """
    if _verb_start_end(doc, start) is not None or _skill_verb_adjective_end(doc, start) is not None:
        return None
    return _noun_run_end(doc, start)


def _is_committable_conjunct(doc: Doc, run_start: int, run_end: int) -> bool:
    """True if a conjunct run may extend the span: a plain noun head or a tech term tagged VERB (#604).

    An adjective-only run ("and secure.") is not a noun head and must not end the span.
    """
    last = doc[run_end - 1]
    if last.pos_ == "VERB" and last.text in _TECH_TERMS_TAGGED_VERB:
        return True
    return _is_plain_noun_head(doc, run_start, run_end)


def _starts_noun_run(doc: Doc, start: int) -> bool:
    """True if a noun run can begin at ``start``: a noun-run token, or an amod participle before a noun."""
    if _is_noun_run_token(doc[start]):
        return True
    return _is_amod_participle(doc[start]) and start + 1 < len(doc) and _is_noun_run_token(doc[start + 1])


def _run_end(doc: Doc, start: int) -> int:
    """Index just past the contiguous run tokens starting at ``start`` (#523).

    Run tokens are _NOUN_RUN_POS tokens and amod participles that are followed by a
    noun-run token. A trailing participle is not part of the run.
    """
    end = start
    while end < len(doc):
        if _is_noun_run_token(doc[end]):
            end += 1
        elif _is_amod_participle(doc[end]) and end + 1 < len(doc) and _is_noun_run_token(doc[end + 1]):
            end += 1
        else:
            break
    return end


def _participle_head_end(doc: Doc, head_end: int) -> int:
    """Extend a matched head across an amod participle that continues its noun run (#523).

    "design high-performance" + "distributed systems" -> the run through "systems".
    Returns ``head_end`` unchanged when the token there does not continue the run.
    """
    if head_end < len(doc) and _is_amod_participle(doc[head_end]) and _starts_noun_run(doc, head_end):
        return _run_end(doc, head_end)
    return head_end


# --- Glued compound tails (#556)
# "data-driven" is tagged VERB and would start a match as a skill verb ("drive"); a participle glued after a hyphen
# is never a head verb, so that match is dropped.


def _is_glued_participle_head(doc: Doc, start: int) -> bool:
    """True if ``start`` is an amod participle glued to a preceding hyphen ("driven" in "data-driven")."""
    return (
        _is_amod_participle(doc[start])
        and start > 0
        and doc[start - 1].text == "-"
        and not _is_spaced_dash(doc[start - 1])
    )


# --- Participial "built with <tech>" (#551)
# "Built with Go and gRPC" names a stack, not a skill phrase: a participle skill verb before "with" is dropped.
# The base form "Build scalable APIs with Python" (VB/VBP) is unchanged.


def _is_participial_with_head(doc: Doc, start: int) -> bool:
    """True for a past-tense/participle skill verb followed by "with" ("Built with Go", #551)."""
    return doc[start].tag_ in ("VBN", "VBD") and start + 1 < len(doc) and doc[start + 1].lower_ == "with"


def _is_join_conjunction(tok: Token) -> bool:
    return tok.pos_ == "CCONJ" and tok.lower_ in _JOIN_CONJUNCTIONS


def _is_glued_hyphen(doc: Doc, i: int) -> bool:
    return 0 <= i < len(doc) and doc[i].text == "-" and not _is_spaced_dash(doc[i])


def _is_adjectival(tok: Token) -> bool:
    return tok.pos_ == "ADJ" or _is_amod_participle(tok)


def _is_adjectival_segment(doc: Doc, seg: int) -> bool:
    if _is_adjectival(doc[seg]):
        return True
    if not _is_glued_hyphen(doc, seg + 1) or seg + 2 >= len(doc):
        return False
    # "self-healing", "self-service": spaCy tags "self" NOUN and the second half NOUN too (#604).
    if doc[seg].lower_ == "self":
        return True
    last = doc[seg + 2]
    return last.pos_ == "ADJ" or last.tag_ in ("VBN", "VBG")


def _segment_run_end(doc: Doc, seg: int) -> int | None:
    if _is_glued_hyphen(doc, seg + 1) and not _starts_noun_run(doc, seg) and seg + 2 < len(doc):
        return _noun_run_end(doc, seg + 2)
    return _noun_run_end(doc, seg)


def _is_verb_led_adverb(doc: Doc, idx: int) -> bool:
    """True for an ADV tagged token directly after a skill verb ("design fast, ...") (#588)."""
    return doc[idx].pos_ == "ADV" and idx > 0 and doc[idx - 1].pos_ == "VERB" and doc[idx - 1].lemma_ in _SKILL_VERB_SET


def _ends_adjectival_modifier(doc: Doc, comma: int) -> bool:
    """True if the token before the comma at ``comma`` is an adjectival modifier (#557)."""
    before = comma - 1
    if before < 0:
        return False
    if _is_adjectival(doc[before]) or _is_verb_led_adverb(doc, before):
        return True
    return _is_glued_hyphen(doc, before - 1) and before >= 2 and _is_adjectival(doc[before - 2])


def _is_plain_noun_head(doc: Doc, run_start: int, run_end: int) -> bool:
    """True if the run ends in a noun that is not the second half of a glued compound."""
    last = run_end - 1
    if last < run_start or doc[last].pos_ not in ("NOUN", "PROPN"):
        return False
    return not (last - 1 >= run_start and _is_glued_hyphen(doc, last - 1))


def _adjective_pair_end(doc: Doc, conj: int) -> int | None:
    """End of a "<conj> ADJ NOUN" pair closing an adjective list at ``conj`` (#604), or None.

    "secure and reliable APIs": ``conj`` is the "and" after "secure", and the pair ends
    at a plain noun head.
    """
    if conj >= len(doc) or not _is_join_conjunction(doc[conj]):
        return None
    pair = conj + 1
    if pair >= len(doc) or not _is_adjectival_segment(doc, pair):
        return None
    pair_end = _segment_run_end(doc, pair)
    if pair_end is None or not _is_plain_noun_head(doc, pair, pair_end):
        return None
    return pair_end


# --- Bare comma inside an adjective list (#557)
# "design fault-tolerant, low-latency services": the comma joins premodifiers of one head noun; a trailing clause is
# not absorbed and "and" closes the list. Token before the comma: adjectival, glued adjective, or verb-led ADV (#588).
def _adjective_list_end(doc: Doc, comma: int, *, adverb_led: bool = False) -> int | None:
    """End (exclusive) of an adjective list after the bare comma at ``comma``, or None (#557).

    Returns the end of the last segment that is a plain noun head. None when the
    comma does not follow an adjectival modifier or no segment ends in a noun head.
    ``adverb_led`` is set only by _adverb_led_list_end: there a skill-verb segment is
    a verb, not a premodifier ("design fast, lead teams", #599).
    """
    if not _ends_adjectival_modifier(doc, comma):
        return None
    best: int | None = None
    cursor = comma
    while cursor < len(doc) and doc[cursor].text == ",":
        seg = cursor + 1
        closes = seg < len(doc) and _is_join_conjunction(doc[seg])
        if closes:
            seg += 1
        if seg >= len(doc) or not _is_adjectival_segment(doc, seg):
            break
        if adverb_led and doc[seg].lemma_ in _SKILL_VERB_SET:
            break
        run_end = _segment_run_end(doc, seg)
        if run_end is None:
            # A participle adjective before a comma ("distributed," #585) is a segment, not a head.
            if closes or seg + 1 >= len(doc) or doc[seg + 1].text != ",":
                break
            cursor = seg + 1
            continue
        if _is_plain_noun_head(doc, seg, run_end):
            best = run_end
            break
        # An adjective pair closes the list: "secure and reliable APIs" (#604).
        pair_end = _adjective_pair_end(doc, run_end) if not closes else None
        if pair_end is not None:
            best = pair_end
            break
        if closes:
            break
        cursor = run_end
    return best


# VERB-tagged premodifiers in an ADV-led list ("develop quickly, secure APIs"), not skill verbs (#599).
_ADVERB_LIST_VERB_ADJECTIVES = frozenset({"secure"})


def _adverb_led_list_end(doc: Doc, start: int) -> int | None:
    """End (exclusive) of a skill-verb head whose ADV first segment opens an adjective list (#588, #599)."""
    if start + 2 >= len(doc) or doc[start].pos_ != "VERB" or doc[start].lemma_ not in _SKILL_VERB_SET:
        return None
    if doc[start + 1].pos_ != "ADV" or doc[start + 2].text != ",":
        return None
    seg = start + 3
    if seg < len(doc) and doc[seg].pos_ == "VERB" and doc[seg].lemma_ in _ADVERB_LIST_VERB_ADJECTIVES:
        run_end = _noun_run_end(doc, seg + 1)
        if run_end is None or not _is_plain_noun_head(doc, seg + 1, run_end):
            return None
        return run_end
    return _adjective_list_end(doc, start + 2, adverb_led=True)


# --- Verb list before an object (#604)
# "design, build, and maintain ... services": the skill verb is followed by a comma list of verbs, so no match starts.
# Later verbs need only be VERB-tagged; the head verb must be a skill verb.


def _verb_list_end(doc: Doc, start: int) -> int | None:
    """End (exclusive) of a comma-separated verb list under a skill verb plus its object, or None."""
    if start >= len(doc) or doc[start].pos_ != "VERB" or doc[start].lemma_ not in _SKILL_VERB_SET:
        return None
    last = start
    cursor = start + 1
    while cursor < len(doc) and doc[cursor].text == ",":
        seg = cursor + 1
        if seg < len(doc) and _is_join_conjunction(doc[seg]):
            seg += 1
        if seg >= len(doc) or doc[seg].pos_ != "VERB":
            break
        last = seg
        cursor = seg + 1
    if last == start:
        return None
    return _noun_run_end(doc, last + 1)


# --- Coordination extension (#509)
# _coordinated_end() walks "A and B" / "A, B, and C" chains; bare-comma conjuncts stay only if a later one commits.
# "lead data science, platform teams" -> "lead data science"; "or" followed by a VERB never merges.
def _coordinated_end(doc: Doc, head_end: int) -> int:
    """Return the end of the coordinated span that starts at a head ending at ``head_end``.

    Returns ``head_end`` unchanged when no conjunction-led conjunct follows.
    """
    committed = head_end
    cursor = head_end
    # A glued participle compound before a comma ("data-driven,") opens an adjective list (#585).
    if (
        _is_glued_hyphen(doc, cursor)
        and cursor + 2 < len(doc)
        and _is_amod_participle(doc[cursor + 1])
        and doc[cursor + 2].text == ","
    ):
        cursor += 2
    bare_comma_conjunct = False
    while cursor < len(doc):
        if doc[cursor].text == ",":
            after_comma = cursor + 1
            commits = after_comma < len(doc) and _is_join_conjunction(doc[after_comma])
            if not commits:
                # A bare comma may open an adjective list at the head or after a conjunction-led conjunct (#557);
                # never after a bare noun conjunct (#509).
                if not bare_comma_conjunct:
                    list_end = _adjective_list_end(doc, cursor)
                    if list_end is not None:
                        committed = list_end
                        cursor = list_end
                        continue
                bare_comma_conjunct = True
            run_start = after_comma + 1 if commits else after_comma
        elif _is_join_conjunction(doc[cursor]):
            commits = True
            run_start = cursor + 1
        else:
            break
        run_end = _conjunct_end(doc, run_start)
        if run_end is None:
            break
        if commits:
            # A committed conjunct ends the bare-noun run, so a later adjective list may open (#557).
            bare_comma_conjunct = False
            # An adjective-only conjunct ("and secure.") is not a noun head: it does not extend the span (#604).
            if _is_committable_conjunct(doc, run_start, run_end):
                committed = run_end
        cursor = run_end
    return committed


class SkillExtractor:
    def __init__(self, model_name="en_core_web_md", nlp=None):
        if nlp is not None:
            self.nlp = nlp
        else:
            try:
                self.nlp = spacy.load(model_name)
            except OSError:
                logger.error(
                    f"Failed to load spaCy model '{model_name}'. Ensure it's installed: "
                    f"python -m spacy download {model_name}"
                )
                raise
        self.matcher = Matcher(self.nlp.vocab)

        def noun_group() -> dict:
            # ADP excluded: prepositions are not descriptors.
            return {"POS": {"IN": ["ADJ", "NOUN", "PROPN"]}, "OP": "+"}

        def action_verb() -> dict:
            return {"POS": "VERB", "LEMMA": {"IN": SKILL_VERBS}}

        def connector() -> dict:
            return {"POS": {"IN": ["ADP", "DET", "PART"]}, "OP": "?"}

        pattern = [action_verb(), connector(), noun_group()]

        # Coordinated objects are not matched here: _coordinated_end() extends each head through
        # and/or/serial conjuncts (#509).

        # "high-performance" is tokenized [high, -, performance]; the PUNCT "-" would stop the noun run, so
        # one hyphen join is allowed.
        # Spaced dashes are rejected in extract() via _has_spaced_dash().
        hyphen_pattern = [action_verb(), connector(), noun_group(), {"ORTH": "-"}, noun_group()]
        # Function word inside a glued compound (#556): "state-of-the-art" (ADP + DET) and
        # "end-to-end" (ADP only); the DET and its hyphen are optional.
        hyphen_adp_pattern = [
            action_verb(),
            connector(),
            noun_group(),
            {"ORTH": "-"},
            {"POS": "ADP"},
            {"ORTH": "-"},
            {"POS": "DET", "OP": "?"},
            {"ORTH": "-", "OP": "?"},
            noun_group(),
        ]
        # Participle second half of a glued compound (#556): "data-driven platforms". spaCy
        # tags the participle VERB with dep amod, which the noun-run pattern does not accept.
        hyphen_participle_pattern = [
            action_verb(),
            connector(),
            noun_group(),
            {"ORTH": "-"},
            {"TAG": {"IN": ["VBN", "VBG"]}, "DEP": "amod"},
            noun_group(),
        ]
        # Participle-led head (#558): "Design distributed systems" at the start of a sentence.
        # spaCy tags the imperative NOUN and the participle VERB, so no action verb starts a match; the
        # participle must not be a skill verb itself.
        participle_head_pattern = [
            {"POS": "NOUN", "LEMMA": {"IN": SKILL_VERBS}, "IS_SENT_START": True},
            {"TAG": {"IN": ["VBN", "VBG"]}, "DEP": "amod", "LEMMA": {"NOT_IN": SKILL_VERBS}},
            noun_group(),
        ]
        self.matcher.add(
            "SKILL_PHRASE",
            [pattern, hyphen_pattern, hyphen_adp_pattern, hyphen_participle_pattern, participle_head_pattern],
        )

    def extract(self, text):
        try:
            doc = self.nlp(text)
        except Exception as e:
            logger.error(f"Failed to process text with spaCy pipeline: {e}")
            return []

        try:
            matches = list(self.matcher(doc, as_spans=True))
            # Verb-tagged-NOUN starts (#511) are matched by the guard, not the Matcher.
            for i in range(len(doc)):
                obj_end = _verb_start_end(doc, i)
                if obj_end is not None:
                    matches.append(doc[i:obj_end])
                list_end = _adverb_led_list_end(doc, i)
                if list_end is not None:
                    matches.append(doc[i:list_end])
                verb_list_end = _verb_list_end(doc, i)
                if verb_list_end is not None:
                    matches.append(doc[i:verb_list_end])
                adj_verb_end = _skill_verb_adjective_end(doc, i)
                if adj_verb_end is not None:
                    matches.append(doc[i:adj_verb_end])
            # Drop hyphen-variant matches whose "-" is spaced punctuation; the plain pattern still yields the
            # non-hyphenated prefix.
            matches = [
                m
                for m in matches
                if not _has_spaced_dash(m)
                and not _is_glued_participle_head(doc, m.start)
                and not _is_participial_with_head(doc, m.start)
            ]
            # Extend each head through its coordinated conjuncts (#509); the extended span contains the
            # head, so filter_spans keeps it.
            extended = [doc[m.start : _coordinated_end(doc, _participle_head_end(doc, m.end))] for m in matches]

            unique_spans = filter_spans(matches + extended)

            results = [span.text.replace("\n", " ").strip().lower() for span in unique_spans]

            return sorted(set(results))
        except Exception as e:
            logger.error(f"Matcher extraction failed: {e}")
            return []


if __name__ == "__main__":
    carbon_jd_bullets = """[PASTE THE JOB DESCRIPTION HERE]"""

    extractor = SkillExtractor()
    skills = extractor.extract(carbon_jd_bullets)

    print(f"{'INDEX':<5} | {'EXTRACTED SKILL'}")
    print("-" * 50)
    for i, skill in enumerate(skills):
        print(f"{i + 1:<5} | {skill}")
