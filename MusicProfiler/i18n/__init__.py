"""MusicProfiler i18n — simple JSON-based internationalization.

Usage::

    from MusicProfiler.i18n import t, set_locale

    print(t("cli.list.empty"))           # -> "No songs found."
    print(t("cli.import.success", count=5, path="/tmp/songs.csv"))
    set_locale("zh_CN")
    print(t("cli.list.empty"))           # -> "未找到歌曲。"

The default locale is read from the ``MUSICPROFILER_LANG`` environment variable.
If not set, ``en_US`` is used.  When a key is missing from the active locale
file the key *itself* is returned so that callers never crash on a missing
translation.
"""

import json
import os
from typing import Any


class I18n:
    """Thread-unsafe, module-level singleton responsible for loading and
    caching locale JSON files and resolving translation keys."""

    def __init__(self) -> None:
        self._translations: dict[str, dict[str, str]] = {}
        self._locale: str = "en_US"
        self._base: str = os.path.dirname(os.path.abspath(__file__))

    # -- public API --------------------------------------------------------

    def set_locale(self, lang: str) -> None:
        """Switch to *lang* (e.g. ``"zh_CN"``), loading its JSON file on
        first use."""
        self._locale = lang
        self._load(lang)

    def t(self, key: str, **kwargs: Any) -> str:
        """Return the translation for *key* in the current locale.

        If *kwargs* are supplied, ``str.format(**kwargs)`` is called on the
        resolved text.  Missing keys fall back to *key* itself.
        """
        bag = self._translations.get(self._locale, {})
        text = bag.get(key, key)
        if kwargs:
            try:
                text = text.format(**kwargs)
            except (KeyError, ValueError):
                pass
        return text

    # -- internal ----------------------------------------------------------

    def _load(self, lang: str) -> None:
        """Load *lang* JSON file if not already cached."""
        if lang in self._translations:
            return
        path = os.path.join(self._base, "locales", f"{lang}.json")
        try:
            with open(path, "r", encoding="utf-8") as fh:
                self._translations[lang] = json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError):
            self._translations[lang] = {}


# -----------------------------------------------------------------------
# Module-level singleton & convenience re-exports
# -----------------------------------------------------------------------

_i18n = I18n()


def _detect_locale() -> str:
    """Inspect ``MUSICPROFILER_LANG`` env var; default to ``en_US``."""
    return os.environ.get("MUSICPROFILER_LANG", "en_US")


_i18n.set_locale(_detect_locale())


def t(key: str, **kwargs: Any) -> str:
    """Convenience wrapper around the singleton ``I18n.t``."""
    return _i18n.t(key, **kwargs)


def set_locale(lang: str) -> None:
    """Convenience wrapper around the singleton ``I18n.set_locale``."""
    _i18n.set_locale(lang)
