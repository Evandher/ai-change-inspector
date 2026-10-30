"""Bounded, read-only Git capture; never part of the pure diff parser."""

import os
import re
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path

from app.inspection_models import ChangeScope, InspectionError
from app.services.diff_parser import MAX_DIFF_BYTES

GIT_TIMEOUT_SECONDS = 10.0
CONFIG_LIMIT_BYTES = 64 * 1024
EOL_CONFIG_QUERY = [
    "config",
    "--no-includes",
    "--null",
    "--get-regexp",
    r"^core\.(autocrlf|eol|safecrlf)$",
]
# Reject includes before invoking any diff: otherwise a clean filter from an included
# config could execute repository commands even with --no-ext-diff/--no-textconv.
UNSAFE_CONFIG = (
    r"^(include.*\.path|filter\..*|core\.fsmonitor|extensions\.partialclone|"
    r"extensions\.worktreeconfig|remote\..*\.promisor)$"
)


@dataclass(frozen=True)
class AuthorizedRepository:
    name: str
    root: Path


def authorize_repositories(entries: list[str]) -> dict[str, AuthorizedRepository]:
    repositories = {}
    for entry in entries:
        name, separator, value = entry.partition("=")
        if not separator or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name):
            raise ValueError("Each --repo must be an ID=absolute_path with a simple ID.")
        path = Path(value)
        if not path.is_absolute() or name in repositories:
            raise ValueError("Repository paths must be absolute and IDs unique.")
        try:
            root = path.resolve(strict=True)
        except OSError as exc:
            raise ValueError("An authorized repository directory is unavailable.") from exc
        if not root.is_dir():
            raise ValueError("An authorized repository must be a directory.")
        repositories[name] = AuthorizedRepository(name, root)
    if not repositories:
        raise ValueError("At least one --repo authorization is required.")
    return repositories


def _git_environment(*, read_eol_config: bool = False) -> dict[str, str]:
    # Do not inherit MODEL_API_KEY, Git redirects, config injections, credentials,
    # external diff programs or other arbitrary agent environment variables.
    environment = {
        key: value
        for key, value in os.environ.items()
        if key.upper()
        in {
            "PATH",
            "SYSTEMROOT",
            "WINDIR",
            "COMSPEC",
            "PATHEXT",
            "TEMP",
            "TMP",
        }
    }
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_ATTR_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_NO_LAZY_FETCH": "1",
            "GIT_PAGER": "",
            "LC_ALL": "C",
        }
    )
    if read_eol_config:
        # Only the fixed config query may read normal system/user config, never a diff.
        # Includes remain disabled; no caller-provided GIT_* overrides are inherited.
        for key in ("GIT_CONFIG_NOSYSTEM", "GIT_CONFIG_SYSTEM", "GIT_CONFIG_GLOBAL"):
            environment.pop(key)
        for key in ("HOME", "USERPROFILE", "XDG_CONFIG_HOME"):
            if key in os.environ:
                environment[key] = os.environ[key]
    return environment


def _run_git(
    root: Path, arguments: list[str], limit: int, *, read_eol_config: bool = False
) -> tuple[int, bytes]:
    if read_eol_config and arguments != EOL_CONFIG_QUERY:
        raise ValueError("Only the fixed EOL config query may read user/system configuration.")
    executable = shutil.which("git")
    if executable is None:
        raise InspectionError("git_unavailable", "Git no está disponible en PATH.")
    try:
        git_path = Path(executable).resolve(strict=True)
    except OSError as exc:
        raise InspectionError("git_unavailable", "No se pudo localizar el ejecutable Git.") from exc
    if git_path.is_relative_to(root) or (os.name == "nt" and git_path.suffix.casefold() != ".exe"):
        raise InspectionError(
            "unsafe_git_executable",
            "Git debe ser un ejecutable confiable fuera del repositorio.",
            blocked=True,
        )
    command = [
        str(git_path),
        "--no-pager",
        "--no-optional-locks",
        "-c",
        f"safe.directory={root}",
        "-c",
        "core.fsmonitor=false",
        "-c",
        f"core.hooksPath={os.devnull}",
        "-c",
        f"core.attributesFile={os.devnull}",
        f"--git-dir={root / '.git'}",
        f"--work-tree={root}",
        *arguments,
    ]
    try:
        with subprocess.Popen(
            command,
            cwd=root,
            env=_git_environment(read_eol_config=read_eol_config),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            # Warnings (e.g. CRLF conversion) are not diff data. Errors use exit codes
            # and sanitized messages; never retain potentially sensitive diagnostics.
            stderr=subprocess.DEVNULL,
            shell=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ) as process:
            expired = threading.Event()

            def timeout() -> None:
                expired.set()
                try:
                    process.kill()
                except OSError:
                    pass

            timer = threading.Timer(GIT_TIMEOUT_SECONDS, timeout)
            timer.daemon = True
            timer.start()
            output = bytearray()
            try:
                assert process.stdout is not None
                while chunk := process.stdout.read(64 * 1024):
                    output.extend(chunk)
                    if len(output) > limit:
                        process.kill()
                        raise InspectionError(
                            "git_output_too_large", "La salida Git excede el límite."
                        )
                code = process.wait()
                if expired.is_set():
                    raise InspectionError(
                        "git_timeout", "Git excedió el tiempo límite de 10 segundos."
                    )
                return code, bytes(output)
            finally:
                timer.cancel()
    except OSError as exc:
        raise InspectionError(
            "git_unavailable", "No se pudo ejecutar Git de forma segura."
        ) from exc


def _check_layout(root: Path) -> None:
    try:
        if root.resolve(strict=True) != root or not root.is_dir():
            raise InspectionError("unauthorized_path", "La ruta autorizada cambió.", blocked=True)
        metadata = root / ".git"
        if not metadata.is_dir() or metadata.is_symlink() or metadata.resolve() != metadata:
            raise InspectionError(
                "invalid_repository",
                "Se requiere la raíz de un repositorio Git con .git local.",
            )
        for name in ("config", "index", "HEAD", "objects", "refs", "info/attributes"):
            path = metadata / name
            if path.is_symlink() or not path.resolve().is_relative_to(metadata):
                raise InspectionError(
                    "unsafe_git_layout", "Git usa metadatos externos.", blocked=True
                )
        for name in ("commondir", "objects/info/alternates", "objects/info/http-alternates"):
            if (metadata / name).exists():
                raise InspectionError(
                    "unsafe_git_layout",
                    "Worktrees y almacenes de objetos externos no admitidos.",
                    blocked=True,
                )
    except (OSError, RuntimeError) as exc:
        raise InspectionError("invalid_repository", "No se pudo validar el repositorio.") from exc


def _eol_options(root: Path) -> list[str]:
    code, output = _run_git(root, EOL_CONFIG_QUERY, CONFIG_LIMIT_BYTES, read_eol_config=True)
    if code == 1 and not output:
        return []
    if code != 0:
        raise InspectionError("git_error", "No se pudo leer la configuración de finales de línea.")
    booleans = {
        "": "false",
        "true": "true",
        "yes": "true",
        "on": "true",
        "1": "true",
        "false": "false",
        "no": "false",
        "off": "false",
        "0": "false",
    }
    allowed = {
        "core.autocrlf": {**booleans, "input": "input"},
        "core.eol": {value: value for value in ("lf", "crlf", "native")},
        "core.safecrlf": {**booleans, "warn": "warn"},
    }
    values: dict[str, str] = {}
    try:
        if not output.endswith(b"\0"):
            raise ValueError("Incomplete configuration")
        for entry in output[:-1].decode("utf-8").split("\0"):
            key, separator, value = entry.partition("\n")
            if not separator:
                value = "true"  # Git boolean variable without '='.
            if key in ("core.autocrlf", "core.safecrlf") and re.fullmatch(r"[+-]?\d+", value):
                value = "true" if value.lstrip("+-").strip("0") else "false"
            values[key] = allowed[key][value.casefold()]
    except (UnicodeDecodeError, ValueError, KeyError) as exc:
        raise InspectionError(
            "unsupported_eol_config",
            "La configuración de finales de línea contiene valores no admitidos.",
        ) from exc
    # Git emits scopes in precedence order; last value wins, including local overrides.
    return [argument for key, value in values.items() for argument in ("-c", f"{key}={value}")]


def capture_changes(repository: AuthorizedRepository, scope: ChangeScope) -> str:
    if scope not in ("staged", "unstaged"):
        raise InspectionError("invalid_scope", "Selecciona staged o unstaged explícitamente.")
    root = repository.root
    _check_layout(root)
    code, config = _run_git(
        root,
        ["config", "--local", "--no-includes", "--get-regexp", UNSAFE_CONFIG],
        CONFIG_LIMIT_BYTES,
    )
    if code == 0 and config:
        raise InspectionError(
            "unsafe_git_config",
            "La configuración Git incluye filtros/includes no admitidos.",
            blocked=True,
        )
    if code != 1:
        raise InspectionError("git_error", "No se pudo validar la configuración local de Git.")
    code, state = _run_git(
        root, ["rev-parse", "--is-inside-work-tree", "--is-bare-repository"], CONFIG_LIMIT_BYTES
    )
    if code != 0 or state.splitlines() != [b"true", b"false"]:
        raise InspectionError(
            "invalid_repository", "El directorio no es un repositorio de trabajo."
        )
    arguments = [
        "diff",
        "--no-ext-diff",
        "--no-textconv",
        "--ignore-submodules=all",
        "--no-renames",
        "--no-color",
        "--no-relative",
        "--src-prefix=a/",
        "--dst-prefix=b/",
        "--unified=3",
    ]
    if scope == "staged":
        arguments.append("--cached")
    eol_options = _eol_options(root) if scope == "unstaged" else []
    code, output = _run_git(root, [*eol_options, *arguments, "--"], MAX_DIFF_BYTES)
    if code != 0:
        raise InspectionError("git_error", "Git no pudo capturar los cambios seleccionados.")
    try:
        return output.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InspectionError("unsupported_encoding", "El diff Git no es UTF-8 válido.") from exc
