# SPDX-License-Identifier: GPL-3.0-or-later
"""Fail-closed inventory of offline teaching data for MyScreenDraw.spec.

This validates bundle paths and file types, not catalog/course semantics or
teaching completeness; CatalogLoader owns those runtime checks. An absent
assets/tutorials tree is allowed during source development only and explicitly
warns that teaching is unavailable. No resource directory is ever created here.
"""
from __future__ import annotations

from pathlib import Path
import stat
import warnings


_IMAGE_SUFFIXES = frozenset({'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.webp'})
# Existing application import/open formats; extend only with a verified consumer.
_FIXTURE_SUFFIXES = _IMAGE_SUFFIXES | {'.msd', '.csv', '.pdf'}


class TeachingPackagingError(ValueError):
    """An existing teaching resource tree is unsafe or cannot be inventoried."""


def _inspect(path: Path, *, allow_missing: bool = False):
    try:
        result = path.lstat()
    except FileNotFoundError as exc:
        if allow_missing:
            return None
        raise TeachingPackagingError(f'cannot inspect teaching resource: {path}') from exc
    except OSError as exc:
        raise TeachingPackagingError(f'cannot inspect teaching resource: {path}') from exc
    if (stat.S_ISLNK(result.st_mode)
            or getattr(result, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
        # Reparse points include Windows junctions, including dangling ones.
        raise TeachingPackagingError(f'link/reparse teaching resource is forbidden: {path}')
    if stat.S_ISREG(result.st_mode) and result.st_nlink > 1:
        raise TeachingPackagingError(f'hard-linked teaching resource is forbidden: {path}')
    return result


def _resolve(path: Path, boundary: Path | None = None) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise TeachingPackagingError(f'cannot resolve teaching resource: {path}') from exc
    if boundary is not None and not resolved.is_relative_to(boundary):
        raise TeachingPackagingError(f'teaching resource escapes outside root: {path}')
    return resolved


def _require_directory(path: Path, info) -> None:
    if not stat.S_ISDIR(info.st_mode):
        raise TeachingPackagingError(f'teaching resource must be a directory: {path}')


def _unavailable() -> list[tuple[str, str]]:
    warnings.warn('assets/tutorials is absent; teaching is unavailable. '
                  'Keeping legacy release data only; this is not teaching acceptance.',
                  RuntimeWarning, stacklevel=3)
    return []


def _supported(relative: Path) -> bool:
    suffix = relative.suffix.lower()
    return (suffix == '.json'
            or (relative.parts[0] == 'fixtures' and suffix in _FIXTURE_SUFFIXES)
            or (relative.parts[0] == 'images' and suffix in _IMAGE_SUFFIXES))


def collect_teaching_datas(source_root: str | Path | None = None) -> list[tuple[str, str]]:
    """Return explicit (absolute source, relative bundle directory) data entries.

    source_root must be absolute (the spec uses its SPEC directory). The default
    uses this source file, never the execution CWD. All JSON and supported image/
    fixture files are included, even when not referenced by the current catalog.
    An existing but incomplete/unsafe tree raises before any data list is returned.
    """
    source = Path(source_root) if source_root is not None else Path(__file__).resolve().parents[1]
    if not source.is_absolute():
        raise TeachingPackagingError('teaching source root must be absolute')
    _require_directory(source, _inspect(source))
    source = _resolve(source)

    assets = source / 'assets'
    info = _inspect(assets, allow_missing=True)
    if info is None:
        return _unavailable()
    _require_directory(assets, info)
    _resolve(assets, source)

    tutorials = assets / 'tutorials'
    info = _inspect(tutorials, allow_missing=True)
    if info is None:
        return _unavailable()
    _require_directory(tutorials, info)
    tutorials = _resolve(tutorials, source)

    catalog = tutorials / 'catalog.json'
    info = _inspect(catalog, allow_missing=True)
    if info is None or not stat.S_ISREG(info.st_mode):
        raise TeachingPackagingError(f'teaching catalog.json is required as a regular file: {catalog}')
    _resolve(catalog, tutorials)

    files = []
    pending = [tutorials]
    while pending:
        path = pending.pop()
        info = _inspect(path)
        _resolve(path, tutorials)
        if stat.S_ISDIR(info.st_mode):
            try:
                pending.extend(sorted(path.iterdir()))
            except OSError as exc:
                raise TeachingPackagingError(f'cannot scan teaching resource directory: {path}') from exc
        elif stat.S_ISREG(info.st_mode):
            relative = path.relative_to(tutorials)
            if not _supported(relative):
                raise TeachingPackagingError(f'unsupported teaching resource file: {path}')
            files.append(path)
        else:
            raise TeachingPackagingError(f'teaching resource must be a regular file or directory: {path}')

    return [(str(path), (Path('assets') / 'tutorials' / path.relative_to(tutorials).parent).as_posix())
            for path in sorted(files, key=lambda item: item.relative_to(tutorials).as_posix())]
