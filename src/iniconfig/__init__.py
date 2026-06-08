"""brain-dead simple parser for ini-style files.
(C) Ronny Pfannschmidt, Holger Krekel -- MIT licensed
"""

from __future__ import annotations
import os
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Final, TypeVar, overload, Union

from . import _parse
from ._parse import COMMENTCHARS, iscommentline
from .exceptions import ParseError

_D = TypeVar("_D")
_T = TypeVar("_T")

__all__ = ["IniConfig", "ParseError", "COMMENTCHARS", "iscommentline", "IniParseError"]


class IniParseError(Exception):
    """Custom exception for configuration parsing errors."""
    def __init__(self, message: str, line_no: int) -> None:
        super().__init__(f"{message} (at line {line_no})")
        self.line_no = line_no


class SectionWrapper:
    config: Final["IniConfig"]
    name: Final[str]

    def __init__(self, config: "IniConfig", name: str) -> None:
        self.config = config
        self.name = name

    def lineof(self, name: str) -> int | None:
        return self.config.lineof(self.name, name)

    @overload
    def get(self, key: str) -> str | None: ...

    @overload
    def get(
        self,
        key: str,
        convert: Callable[[str], _T],
    ) -> _T | None: ...

    @overload
    def get(
        self,
        key: str,
        default: None,
        convert: Callable[[str], _T],
    ) -> _T | None: ...

    @overload
    def get(self, key: str, default: _D, convert: None = None) -> str | _D: ...

    @overload
    def get(
        self,
        key: str,
        default: _D,
        convert: Callable[[str], _T],
    ) -> _T | _D: ...

    def get(
        self,
        key: str,
        default: _D | None = None,
        convert: Callable[[str], _T] | None = None,
    ) -> _D | _T | str | None:
        return self.config.get(self.name, key, convert=convert, default=default)

    def __getitem__(self, key: str) -> str:
        return self.config.sections[self.name][key]

    def __iter__(self) -> Iterator[str]:
        section: Mapping[str, str] = self.config.sections.get(self.name, {})

        def lineof(key: str) -> int:
            return self.config.lineof(self.name, key) or 0

        yield from sorted(section, key=lineof)

    def items(self) -> Iterator[tuple[str, str]]:
        for name in self:
            yield name, self[name]


class IniConfig(Mapping[str, SectionWrapper]):
    path: Final[Path]
    sections: Final[Mapping[str, Mapping[str, str]]]
    _sources: Final[Mapping[tuple[str, str | None], int]]

    def __init__(
        self,
        path: Union[str, os.PathLike[str]],
        data: str | None = None,
        encoding: str = "utf-8",
        *,
        _sections: Mapping[str, Mapping[str, str]] | None = None,
        _sources: Mapping[tuple[str, str | None], int] | None = None,
    ) -> None:
        self.path = Path(path)

        if _sections is not None and _sources is not None:
            sections_data, sources = _sections, _sources
        else:
            if data is None:
                with self.path.open(encoding=encoding) as fp:
                    data = fp.read()

            sections_data, sources = _parse.parse_ini_data(
                str(self.path), data, strip_inline_comments=False
            )

        self._sources = sources
        self.sections = sections_data

    @classmethod
    def parse(
        cls,
        path: Union[str, os.PathLike[str]],
        data: str | None = None,
        encoding: str = "utf-8",
        *,
        strip_inline_comments: bool = True,
        strip_section_whitespace: bool = False,
    ) -> "IniConfig":
        fspath = Path(path)

        if data is None:
            with fspath.open(encoding=encoding) as fp:
                data = fp.read()

        sections_data, sources = _parse.parse_ini_data(
            str(fspath),
            data,
            strip_inline_comments=strip_inline_comments,
            strip_section_whitespace=strip_section_whitespace,
        )

        return cls(path=fspath, _sections=sections_data, _sources=sources)

    def lineof(self, section: str, name: str | None = None) -> int | None:
        lineno = self._sources.get((section, name))
        return None if lineno is None else lineno + 1

    @overload
    def get(self, section: str, name: str) -> str | None: ...

    @overload
    def get(self, section: str, name: str, convert: Callable[[str], _T]) -> _T | None: ...

    @overload
    def get(self, section: str, name: str, default: None, convert: Callable[[str], _T]) -> _T | None: ...

    @overload
    def get(self, section: str, name: str, default: _D, convert: None = None) -> str | _D: ...

    @overload
    def get(self, section: str, name: str, default: _D, convert: Callable[[str], _T]) -> _T | _D: ...

    def get(
        self,
        section: str,
        name: str,
        default: _D | None = None,
        convert: Callable[[str], _T] | None = None,
    ) -> _D | _T | str | None:
        try:
            value: str = self.sections[section][name]
        except KeyError:
            return default
        else:
            return convert(value) if convert is not None else value

    def __getitem__(self, name: str) -> SectionWrapper:
        if name not in self.sections:
            raise KeyError(name)
        return SectionWrapper(self, name)

    def __iter__(self) -> Iterator[str]:
        return iter(sorted(self.sections, key=lambda n: self.lineof(n) or 0))

    def __len__(self) -> int:
        return len(self.sections)

    def __contains__(self, arg: object) -> bool:
        return arg in self.sections