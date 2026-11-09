"""CQL/FHIR Library identity rules from CQL IG Conformance Requirement 4.2."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_CQL_LIBRARY_RE = re.compile(
    r"^\s*library\s+([A-Za-z][A-Za-z0-9_.]*)\s+version\s+['\"]([^'\"]+)['\"]",
    re.IGNORECASE | re.MULTILINE,
)
_CQL_CONTEXT_RE = re.compile(
    r"^\s*context\s+([A-Za-z][A-Za-z0-9.]*)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_FHIR_CONTEXT_SYSTEM = "http://hl7.org/fhir/resource-types"
_CQL_CONTEXT_SYSTEM = "http://cql.hl7.org/CodeSystem/cql-context-declaration-codes"
_FHIR_SUBJECT_CONTEXTS = {"Patient", "Practitioner", "Organization", "Location", "Device"}
CQL_NAMESPACE_EXTENSION_URL = (
    "http://hl7.org/fhir/uv/cql/StructureDefinition/cql-namespace"
)
CQL_NAMESPACE_URI_EXTENSION_URL = (
    "http://hl7.org/fhir/uv/cql/StructureDefinition/cql-namespaceUri"
)


class CqlLibraryIdentityError(ValueError):
    """Raised when CQL source and its FHIR Library wrapper disagree."""


@dataclass(frozen=True)
class CqlLibraryIdentity:
    name: str
    version: str


def _without_cql_comments(source: str) -> str:
    """Remove line and block comments while preserving strings and newlines."""
    result: list[str] = []
    index = 0
    quote: str | None = None
    while index < len(source):
        if quote is not None:
            character = source[index]
            result.append(character)
            if character == "\\" and quote in {"'", '"', "`"} and index + 1 < len(source):
                result.append(source[index + 1])
                index += 2
                continue
            if character == quote:
                quote = None
            index += 1
            continue
        if source.startswith("//", index):
            newline = source.find("\n", index + 2)
            if newline < 0:
                break
            result.append("\n")
            index = newline + 1
            continue
        if source.startswith("/*", index):
            end = source.find("*/", index + 2)
            if end < 0:
                result.extend("\n" for character in source[index:] if character == "\n")
                break
            result.extend("\n" for character in source[index:end + 2] if character == "\n")
            index = end + 2
            continue
        character = source[index]
        result.append(character)
        if character in {"'", '"', "`"}:
            quote = character
        index += 1
    return "".join(result)


def parse_cql_library_identity_text(
    source: str,
    *,
    label: str = "embedded CQL source",
) -> CqlLibraryIdentity:
    """Return a CQL library identity from source text."""
    match = _CQL_LIBRARY_RE.search(_without_cql_comments(source))
    if match is None:
        raise CqlLibraryIdentityError(
            f"{label} must declare `library <name> version '<version>'`"
        )
    identity = CqlLibraryIdentity(match.group(1), match.group(2))
    validate_cql_library_name(identity.name)
    return identity


def parse_cql_library_identity(path: Path) -> CqlLibraryIdentity:
    """Return the declared CQL library name and version from ``path``."""
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise CqlLibraryIdentityError(f"Cannot read CQL source {path}: {exc}") from exc
    return parse_cql_library_identity_text(source, label=f"CQL source {path}")


def parse_cql_context_text(source: str, *, label: str = "embedded CQL source") -> str:
    """Return the single declared context, defaulting an omission to Patient."""
    contexts = _CQL_CONTEXT_RE.findall(_without_cql_comments(source))
    if len(contexts) > 1:
        raise CqlLibraryIdentityError(
            f"{label} declares multiple contexts; FHIR CQL libraries allow at most one"
        )
    return contexts[0] if contexts else "Patient"


def parse_cql_context(path: Path) -> str:
    """Return the single declared context, defaulting an omission to Patient."""
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise CqlLibraryIdentityError(f"Cannot read CQL source {path}: {exc}") from exc
    return parse_cql_context_text(source, label=f"CQL source {path}")


def subject_for_cql_context(context: str) -> dict[str, Any]:
    """Return the Library.subjectCodeableConcept for a supported CQL context."""
    if context == "Unfiltered":
        system = _CQL_CONTEXT_SYSTEM
    elif context in _FHIR_SUBJECT_CONTEXTS:
        system = _FHIR_CONTEXT_SYSTEM
    else:
        raise CqlLibraryIdentityError(
            f"CQL context {context!r} is not supported by rh-skills automatic Library.subject generation"
        )
    return {
        "coding": [{"system": system, "code": context, "display": context}],
        "text": context,
    }


def _subject_carries_context(subject: Any, expected_subject: dict[str, Any]) -> bool:
    """Return whether a subject CodeableConcept contains the required context code."""
    if not isinstance(subject, dict):
        return False
    expected_coding = expected_subject["coding"][0]
    return any(
        isinstance(coding, dict)
        and coding.get("system") == expected_coding["system"]
        and coding.get("code") == expected_coding["code"]
        for coding in (subject.get("coding") or [])
    )


def validate_cql_library_name(name: str) -> None:
    """Enforce the CQL IG 4.2 SHALL constraints on a library name."""
    if len(name) > 64:
        raise CqlLibraryIdentityError(
            f"CQL library name {name!r} is {len(name)} characters; the maximum is 64"
        )
    if "_" in name:
        raise CqlLibraryIdentityError(
            f"CQL library name {name!r} must not contain underscores"
        )


def expected_library_url(namespace_url: str, name: str) -> str:
    """Build the canonical required by CQL IG 4.2."""
    return f"{namespace_url.rstrip('/')}/Library/{name}"


def apply_cql_namespace_extensions(
    library: dict[str, Any],
    *,
    namespace_name: str,
    namespace_url: str,
) -> None:
    """Set the CQL IG namespace name and URI extensions on a Library."""
    managed_urls = {CQL_NAMESPACE_EXTENSION_URL, CQL_NAMESPACE_URI_EXTENSION_URL}
    extensions = [
        extension
        for extension in (library.get("extension") or [])
        if isinstance(extension, dict) and extension.get("url") not in managed_urls
    ]
    extensions.extend([
        {"url": CQL_NAMESPACE_EXTENSION_URL, "valueString": namespace_name},
        {"url": CQL_NAMESPACE_URI_EXTENSION_URL, "valueUri": namespace_url.rstrip("/")},
    ])
    library["extension"] = extensions


def _require_namespace_extension(
    library: dict[str, Any],
    *,
    extension_url: str,
    value_field: str,
    expected_value: str,
    label: str,
) -> None:
    matches = [
        extension
        for extension in (library.get("extension") or [])
        if isinstance(extension, dict) and extension.get("url") == extension_url
    ]
    if len(matches) != 1 or matches[0].get(value_field) != expected_value:
        raise CqlLibraryIdentityError(
            f"FHIR Library {label} must be {expected_value!r} in extension {extension_url!r}"
        )


def validate_fhir_library_identity(
    library: dict[str, Any],
    *,
    namespace_name: str | None = None,
    namespace_url: str | None = None,
    cql_path: Path | None = None,
    cql_source: str | None = None,
) -> list[str]:
    """Validate one FHIR Library wrapper and return 4.2 SHOULD warnings."""
    name = library.get("name")
    version = library.get("version")
    url = library.get("url")
    if not isinstance(name, str) or not name:
        raise CqlLibraryIdentityError("FHIR Library.name must be a non-empty CQL library name")
    if not isinstance(version, str) or not version:
        raise CqlLibraryIdentityError("FHIR Library.version must be a non-empty CQL library version")
    if not isinstance(url, str) or not url:
        raise CqlLibraryIdentityError("FHIR Library.url must be a non-empty canonical URL")
    validate_cql_library_name(name)

    if namespace_url is not None:
        normalized_namespace_url = namespace_url.rstrip("/")
        expected_url = expected_library_url(normalized_namespace_url, name)
        if url != expected_url:
            raise CqlLibraryIdentityError(
                f"FHIR Library.url must be {expected_url!r} for CQL library {name!r}; got {url!r}"
            )
        _require_namespace_extension(
            library,
            extension_url=CQL_NAMESPACE_URI_EXTENSION_URL,
            value_field="valueUri",
            expected_value=normalized_namespace_url,
            label="CQL namespace URI",
        )
    elif not url.endswith(f"/Library/{name}"):
        raise CqlLibraryIdentityError(
            f"FHIR Library.url must end with '/Library/{name}' to match Library.name; got {url!r}"
        )
    if namespace_name is not None:
        _require_namespace_extension(
            library,
            extension_url=CQL_NAMESPACE_EXTENSION_URL,
            value_field="valueString",
            expected_value=namespace_name,
            label="CQL namespace name",
        )

    warnings: list[str] = []
    if len(name) > 30:
        warnings.append(
            f"CQL library name {name!r} is {len(name)} characters; CQL IG 4.2 recommends 30 or fewer"
        )

    if cql_path is not None and cql_source is not None:
        raise CqlLibraryIdentityError("Provide either cql_path or cql_source, not both")
    if cql_path is not None or cql_source is not None:
        label = f"CQL source {cql_path}" if cql_path is not None else "embedded CQL source"
        cql_identity = (
            parse_cql_library_identity(cql_path)
            if cql_path is not None
            else parse_cql_library_identity_text(cql_source or "", label=label)
        )
        if cql_identity != CqlLibraryIdentity(name, version):
            raise CqlLibraryIdentityError(
                "CQL identity mismatch: FHIR Library identity "
                f"{name}|{version} does not match CQL declaration "
                f"{cql_identity.name}|{cql_identity.version} in {label}"
            )
        expected_filename = f"{name}-{version}.cql"
        if cql_path is not None and cql_path.name != expected_filename:
            warnings.append(
                f"CQL source {cql_path.name!r} should be named {expected_filename!r} per CQL IG 4.2"
            )
        context = (
            parse_cql_context(cql_path)
            if cql_path is not None
            else parse_cql_context_text(cql_source or "", label=label)
        )
        expected_subject = subject_for_cql_context(context)
        actual_subject = library.get("subjectCodeableConcept")
        subject_reference = library.get("subjectReference")
        if subject_reference is not None:
            raise CqlLibraryIdentityError(
                "FHIR Library.subjectReference cannot represent the CQL context type; "
                "use subjectCodeableConcept"
            )
        if actual_subject is None and context == "Patient":
            # CQL IG 4.2 explicitly defines an omitted Library.subject as Patient.
            pass
        elif not _subject_carries_context(actual_subject, expected_subject):
            raise CqlLibraryIdentityError(
                f"FHIR Library.subject must represent CQL context {context!r}; "
                "expected subjectCodeableConcept to include coding "
                f"{expected_subject['coding'][0]!r}"
            )

    return warnings
