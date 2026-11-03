"""Opt-in bounded untracked text capture. Never touches Git's index or executes content."""

import os
import re
import stat
import unicodedata
from contextlib import ExitStack
from pathlib import Path, PurePosixPath

from app.audit_models import CaptureCoverage
from app.inspection_models import InspectionError
from app.services.diff_parser import MAX_DIFF_BYTES, parse_diff
from app.services.egress_guard import check_egress
from app.services.git_capture import CONFIG_LIMIT_BYTES, AuthorizedRepository, _run_git

MAX_FILE_BYTES = 64 * 1024
MAX_FILES = 500
SOURCE_SUFFIXES = frozenset(
    {
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".css",
        ".html",
        ".json",
        ".md",
        ".txt",
        ".go",
        ".rs",
        ".java",
        ".cs",
        ".sql",
        ".yaml",
        ".yml",
        ".toml",
        ".xml",
        ".vue",
        ".svelte",
        ".c",
        ".h",
        ".cpp",
        ".rb",
        ".php",
        ".sh",
        ".ps1",
        ".gx",
    }
)
EXCLUDED_PARTS = frozenset(
    {
        "node_modules",
        "vendor",
        "dist",
        "build",
        "coverage",
        "__pycache__",
        "artifacts",
        "logs",
        "private",
        "backups",
        "tmp",
        "temp",
        "uploads",
    }
)


def _windows_read(path: Path, root: Path) -> bytes:
    # Holding directory handles without FILE_SHARE_DELETE prevents ancestor replacement;
    # the file handle also denies concurrent writers. Reparse points are opened, not followed.
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    get_info = kernel.GetFileInformationByHandleEx
    get_info.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]

    class Attributes(ctypes.Structure):
        _fields_ = [("attributes", wintypes.DWORD), ("tag", wintypes.DWORD)]

    with ExitStack() as stack:
        # Lock every ancestor, including ancestors above the authorized root.
        for item in [*reversed(path.parents), path]:
            directory = item != path
            handle = create(
                str(item),
                0 if directory else 0x80000000,
                1,
                None,
                3,
                0x00200000 | (0x02000000 if directory else 0),
                None,
            )
            if handle == wintypes.HANDLE(-1).value:
                raise OSError("Cannot acquire a safe read handle")
            stack.callback(close, handle)
            attrs = Attributes()
            if not get_info(handle, 9, ctypes.byref(attrs), ctypes.sizeof(attrs)):
                raise OSError("Cannot validate file attributes")
            if attrs.attributes & 0x400 or bool(attrs.attributes & 0x10) != directory:
                raise OSError("Reparse point or unexpected file type")
        # Duplicate the locked file handle; fd owns only the duplicate.
        duplicate = wintypes.HANDLE()
        current = kernel.GetCurrentProcess
        current.restype = wintypes.HANDLE
        dup = kernel.DuplicateHandle
        dup.argtypes = [
            wintypes.HANDLE,
            wintypes.HANDLE,
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.HANDLE),
            wintypes.DWORD,
            wintypes.BOOL,
            wintypes.DWORD,
        ]
        if not dup(current(), handle, current(), ctypes.byref(duplicate), 0, False, 2):
            raise OSError("Cannot duplicate read handle")
        fd = msvcrt.open_osfhandle(duplicate.value, os.O_RDONLY | os.O_BINARY)
        with os.fdopen(fd, "rb") as stream:
            return _read_stream(stream)


def _read_stream(stream) -> bytes:
    before = os.fstat(stream.fileno())
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise OSError("Not a single-link regular file")
    if before.st_size > MAX_FILE_BYTES:
        raise OverflowError
    data = stream.read(MAX_FILE_BYTES + 1)
    after = os.fstat(stream.fileno())

    def signature(s):
        return (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)

    if signature(before) != signature(after) or len(data) != before.st_size:
        raise OSError("File changed during capture")
    if len(data) > MAX_FILE_BYTES:
        raise OverflowError
    return data


def safe_read(root: Path, relative: str) -> bytes:
    path = root.joinpath(*PurePosixPath(relative).parts)
    if os.name == "nt":
        return _windows_read(path, root)
    # Fail closed on platforms without descriptor-relative no-follow traversal.
    if not hasattr(os, "O_NOFOLLOW") or os.open not in os.supports_dir_fd:
        raise OSError("Safe traversal unavailable")
    with ExitStack() as stack:
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        stack.callback(os.close, fd)
        for part in PurePosixPath(relative).parts[:-1]:
            fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            stack.callback(os.close, fd)
        file_fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        with os.fdopen(file_fd, "rb") as stream:
            return _read_stream(stream)


def capture_untracked(
    repository: AuthorizedRepository, tracked: str
) -> tuple[str, CaptureCoverage]:
    code, output = _run_git(
        repository.root, ["ls-files", "--others", "--exclude-standard", "-z"], CONFIG_LIMIT_BYTES
    )
    if code or (output and not output.endswith(b"\0")):
        raise InspectionError(
            "untracked_enumeration_failed", "Could not enumerate untracked files safely."
        )
    names = output[:-1].split(b"\0") if output else []
    if len(names) > MAX_FILES:
        raise InspectionError("untracked_limit", "Reduce the number of untracked files.")
    coverage = CaptureCoverage(include_untracked=True, untracked_seen=len(names))
    text = tracked
    represented = (
        {
            name
            for file in parse_diff(tracked).files
            for name in (file.old_path, file.new_path)
            if name
        }
        if tracked
        else set()
    )

    def exclude(reason):
        coverage.exclusions[reason] = coverage.exclusions.get(reason, 0) + 1

    for raw in names:
        try:
            name = raw.decode("utf-8")
            path = PurePosixPath(name)
            if (
                len(name) > 512
                or not re.fullmatch(r"[A-Za-z0-9_./ -]+", name)
                or path.is_absolute()
                or any(part in ("", ".", "..") for part in name.split("/"))
            ):
                exclude("unsafe")
                continue
            if name in represented:
                exclude("policy")
                continue
            # Apply the existing sensitive-path guard before opening the file.
            header = f'diff --git "a/{name}" "b/{name}"\nnew file mode 100644\n'
            check_egress(repository.root, header, parse_diff(header))
            if (
                any(
                    part.startswith(".") or part.casefold() in EXCLUDED_PARTS for part in path.parts
                )
                or path.suffix.casefold() not in SOURCE_SUFFIXES
            ):
                exclude("policy")
                continue
            data = safe_read(repository.root, name)
            content = data.decode("utf-8")
            if any(
                unicodedata.category(c) == "Cc" and c not in "\n\r\t" for c in content
            ) or "\r" in content.replace("\r\n", ""):
                exclude("binary")
                continue
            content = content.replace("\r\n", "\n")
            rows = content.split("\n") if content else []
            if content.endswith("\n"):
                rows.pop()
            patch = header
            if rows:
                patch += f'--- /dev/null\n+++ "b/{name}"\n@@ -0,0 +1,{len(rows)} @@\n'
                patch += "".join("+" + row.rstrip("\n") + "\n" for row in rows)
                if not content.endswith("\n"):
                    patch += "\\ No newline at end of file\n"
            check_egress(repository.root, patch, parse_diff(patch))
            if len((text + patch).encode("utf-8")) > MAX_DIFF_BYTES:
                exclude("budget")
                continue
            text += patch
            coverage.included_untracked.append(name)
        except UnicodeError:
            exclude("encoding")
        except OverflowError:
            exclude("too_large")
        except InspectionError as exc:
            exclude("sensitive" if exc.code in ("sensitive_path", "possible_secret") else "unsafe")
        except (OSError, ValueError):
            exclude("unsafe")
    return text, coverage
