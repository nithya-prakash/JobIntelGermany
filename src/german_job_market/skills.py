"""Deterministic bilingual skill matching against a versioned seed taxonomy."""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


@dataclass
class _TrieNode:
    children: dict[str, _TrieNode] = field(default_factory=dict)
    skill_ids: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class Skill:
    id: str
    label: str
    category: str
    aliases: tuple[str, ...]
    case_sensitive_aliases: tuple[str, ...]


@dataclass(frozen=True)
class SkillTaxonomy:
    version: str
    skills: tuple[Skill, ...]
    casefold_trie: _TrieNode
    strict_trie: _TrieNode

    @property
    def by_id(self) -> dict[str, Skill]:
        return {skill.id: skill for skill in self.skills}

    @property
    def fingerprint(self) -> str:
        payload = [
            {
                "id": skill.id,
                "label": skill.label,
                "category": skill.category,
                "aliases": skill.aliases,
                "case_sensitive_aliases": skill.case_sensitive_aliases,
            }
            for skill in self.skills
        ]
        encoded = json.dumps(
            {"version": self.version, "skills": payload},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def _alias_key(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _insert_alias(root: _TrieNode, alias: str, skill_id: str, case_sensitive: bool) -> None:
    node = root
    tokens = _TOKEN_RE.findall(alias)
    for token in tokens:
        key = token if case_sensitive else token.casefold()
        node = node.children.setdefault(key, _TrieNode())
    node.skill_ids.add(skill_id)


_EXCLUDED = "__excluded__"


def load_taxonomy(path: Path) -> SkillTaxonomy:
    """Load and validate taxonomy data from TOML."""
    with path.open("rb") as source:
        document: dict[str, Any] = tomllib.load(source)

    version = document.get("version")
    raw_skills = document.get("skills")
    if not isinstance(version, str) or not isinstance(raw_skills, list) or not raw_skills:
        raise ValueError("taxonomy must define a version and at least one skill")

    skills: list[Skill] = []
    seen_ids: set[str] = set()
    alias_to_id: dict[str, str] = {}
    for item in raw_skills:
        if not isinstance(item, dict):
            raise ValueError("each taxonomy skill must be a table")
        aliases_value = item.get("aliases", [])
        strict_value = item.get("case_sensitive_aliases", [])
        if not isinstance(aliases_value, list) or not isinstance(strict_value, list):
            raise ValueError("skill aliases and case_sensitive_aliases must be lists")
        skill = Skill(
            id=str(item.get("id", "")),
            label=str(item.get("label", "")),
            category=str(item.get("category", "")),
            aliases=tuple(str(alias).strip() for alias in aliases_value),
            case_sensitive_aliases=tuple(str(alias).strip() for alias in strict_value),
        )
        if not skill.id or not skill.label or not skill.category or not skill.aliases:
            raise ValueError("each skill needs an id, label, category, and aliases")
        if skill.id in seen_ids:
            raise ValueError(f"duplicate skill id: {skill.id}")
        if not set(skill.case_sensitive_aliases).issubset(skill.aliases):
            raise ValueError(f"case-sensitive aliases must also appear in aliases for {skill.id}")
        seen_ids.add(skill.id)
        skills.append(skill)
        for alias in skill.aliases:
            if not alias:
                raise ValueError(f"empty alias for skill {skill.id}")
            key = _alias_key(alias)
            existing = alias_to_id.get(key)
            if existing is not None and existing != skill.id:
                raise ValueError(
                    f"ambiguous alias {alias!r}: assigned to {existing} and {skill.id}"
                )
            alias_to_id[key] = skill.id

    casefold_trie = _TrieNode()
    strict_trie = _TrieNode()
    # Exclusion phrases win as longest matches and are dropped from output, e.g.
    # "communication protocols" must not yield the soft skill Communication.
    for phrase in document.get("exclusions", []):
        _insert_alias(casefold_trie, str(phrase).strip(), _EXCLUDED, False)
    for skill in skills:
        for alias in skill.aliases:
            strict = alias in skill.case_sensitive_aliases
            _insert_alias(strict_trie if strict else casefold_trie, alias, skill.id, strict)
    return SkillTaxonomy(
        version=version,
        skills=tuple(skills),
        casefold_trie=casefold_trie,
        strict_trie=strict_trie,
    )


def _best_matches(tokens: list[str], taxonomy: SkillTaxonomy) -> list[tuple[int, int, set[str]]]:
    """Longest taxonomy match starting at each token: (start, token_length, skill_ids)."""
    matches: list[tuple[int, int, set[str]]] = []
    for start, raw_token in enumerate(tokens):
        best_length = 0
        best_ids: set[str] = set()
        for root, sensitive in ((taxonomy.casefold_trie, False), (taxonomy.strict_trie, True)):
            first_key = raw_token if sensitive else raw_token.casefold()
            node = root.children.get(first_key)
            if node is None:
                continue
            position = start + 1
            if node.skill_ids:
                if best_length < 1:
                    best_length = 1
                    best_ids = set(node.skill_ids)
                elif best_length == 1:
                    best_ids.update(node.skill_ids)
            while position < len(tokens):
                next_raw = tokens[position]
                next_key = next_raw if sensitive else next_raw.casefold()
                child = node.children.get(next_key)
                if child is None:
                    break
                node = child
                position += 1
                match_length = position - start
                if node.skill_ids:
                    if match_length > best_length:
                        best_length = match_length
                        best_ids = set(node.skill_ids)
                    elif match_length == best_length:
                        best_ids.update(node.skill_ids)
        if best_ids:
            matches.append((start, best_length, best_ids))
    return matches


def extract_skill_ids(text: str | None, taxonomy: SkillTaxonomy) -> list[str]:
    """Return canonical skill IDs found in text, in taxonomy order."""
    if not text:
        return []
    found: set[str] = set()
    for _, _, ids in _best_matches(_TOKEN_RE.findall(text), taxonomy):
        found.update(ids - {_EXCLUDED})
    return [skill.id for skill in taxonomy.skills if skill.id in found]


def extract_skill_spans(
    text: str | None, taxonomy: SkillTaxonomy
) -> dict[str, list[tuple[int, int]]]:
    """Return character spans (start, end) of each lexicon match, keyed by skill ID."""
    if not text:
        return {}
    tokens = list(_TOKEN_RE.finditer(text))
    spans: dict[str, list[tuple[int, int]]] = {}
    for start, length, ids in _best_matches([m.group() for m in tokens], taxonomy):
        span = (tokens[start].start(), tokens[start + length - 1].end())
        for skill_id in ids - {_EXCLUDED}:
            spans.setdefault(skill_id, []).append(span)
    return spans


def extract_posting_skills(
    title: str | None, description: str | None, taxonomy: SkillTaxonomy
) -> list[str]:
    """Extract from title and ad description while preserving a single result per skill."""
    return extract_skill_ids(" ".join(value for value in (title, description) if value), taxonomy)
