"""I18n - simple key=value translation loader."""

from __future__ import annotations

from src.core.constants import LOCALES_DIR


class I18n:
    """Singleton internationalization manager."""

    _instance: I18n | None = None

    def __init__(self) -> None:
        self._translations: dict[str, dict[str, str]] = {}
        self.current_lang: str = "zh"

    @classmethod
    def instance(cls) -> I18n:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load(self, lang: str) -> None:
        """Load a locale file (e.g. 'zh' or 'en')."""
        filepath = LOCALES_DIR / f"{lang}.txt"
        translations: dict[str, str] = {}
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, value = line.split("=", 1)
                        translations[key.strip()] = value.strip()
        except FileNotFoundError:
            pass
        self._translations[lang] = translations

    def t(self, key: str) -> str:
        """Get translation for key in current language, fallback to key."""
        lang_dict = self._translations.get(self.current_lang, {})
        result = lang_dict.get(key, "")
        if not result:
            # fallback to other language
            for lang, d in self._translations.items():
                result = d.get(key, "")
                if result:
                    break
        return result or key
