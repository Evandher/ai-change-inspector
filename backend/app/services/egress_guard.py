"""Conservative MCP-only preflight. Secret detection is deliberately not a guarantee."""

import os
import re
from pathlib import Path, PurePosixPath

from app.inspection_models import InspectionError
from app.services.diff_parser import ParsedDiff

SENSITIVE_PARTS = frozenset(
    {
        ".git",
        ".local",
        ".aws",
        ".ssh",
        ".gnupg",
        ".azure",
        ".kube",
        ".docker",
        ".npmrc",
        ".pypirc",
        ".netrc",
        "credentials",
        "secrets",
        "tokens",
        "id_rsa",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
    }
)
SENSITIVE_SUFFIXES = frozenset({".pem", ".key", ".p12", ".pfx", ".keystore", ".kdbx"})
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:[A-Z0-9 ]*PRIVATE KEY|PGP PRIVATE KEY BLOCK)-----"),
    re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{15,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"""(?ix)\b(?:model_api_key|api[_-]?key|access[_-]?token|client[_-]?secret|
                   password|passwd|secret[_-]?key)\b["']?\s*[:=]\s*["']?[^\s"'`,;]{8,}"""),
    re.compile(r"https?://[^/\s:@]+:[^/\s@]+@"),
)


def check_egress(root: Path, text: str, parsed: ParsedDiff) -> None:
    for file in parsed.files:
        for name in (file.old_path, file.new_path):
            if name is None:
                continue
            path = PurePosixPath(name)
            if (
                path.is_absolute()
                or ".." in path.parts
                or "\\" in name
                or ":" in name
                or not path.parts
            ):
                raise InspectionError(
                    "unsafe_diff_path", "El diff contiene rutas no admitidas.", blocked=True
                )
            parts = [part.casefold() for part in path.parts]
            if (
                any(part in SENSITIVE_PARTS or part.startswith(".env") for part in parts)
                or path.suffix.casefold() in SENSITIVE_SUFFIXES
                or any(re.search(r"\.(?:db|sqlite3?)(?:-|$)", part) for part in parts)
                or any(
                    re.match(r"(?:credentials|secrets|passwords|tokens)[._-]", part)
                    for part in parts
                )
            ):
                raise InspectionError(
                    "sensitive_path", "El alcance contiene archivos sensibles.", blocked=True
                )
            candidate = root.joinpath(*path.parts)
            try:
                if candidate.is_symlink() or not candidate.resolve().is_relative_to(root):
                    raise InspectionError(
                        "unsafe_diff_path", "Una ruta escapa del repositorio.", blocked=True
                    )
            except (OSError, RuntimeError) as exc:
                raise InspectionError(
                    "unsafe_diff_path", "No se pudo validar una ruta del diff.", blocked=True
                ) from exc
        if any(re.search(r"\b(?:120000|160000)\b", value) for value in file.metadata):
            raise InspectionError(
                "unsupported_change", "Symlinks y gitlinks no admitidos.", blocked=True
            )
    key = os.environ.get("MODEL_API_KEY", "")
    if (key and len(key) >= 8 and key in text) or any(
        pattern.search(text) for pattern in SECRET_PATTERNS
    ):
        raise InspectionError(
            "possible_secret", "El diff contiene posibles credenciales; no se envió.", blocked=True
        )
