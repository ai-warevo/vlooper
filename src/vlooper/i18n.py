import json
import os
from vlooper.config import config

class I18nManager:
    def __init__(self):
        self._translations = {}
        self._load_translations()

    def _load_translations(self):
        base_path = os.path.dirname(__file__)
        locales_dir = os.path.join(base_path, "locales")
        lang = config.language or "en"
        
        # Try requested language
        lang_file = os.path.join(locales_dir, f"{lang}.json")
        if not os.path.exists(lang_file):
            lang_file = os.path.join(locales_dir, "en.json")

        try:
            with open(lang_file, "r", encoding="utf-8") as f:
                self._translations = json.load(f)
        except Exception as e:
            print(f"Error loading translations from {lang_file}: {e}")
            # Fallback to empty dict, but try en if we failed
            if lang != "en":
                try:
                    with open(os.path.join(locales_dir, "en.json"), "r", encoding="utf-8") as f:
                        self._translations = json.load(f)
                except Exception:
                    self._translations = {}

    def get(self, key_path, **kwargs):
        """Get a translation string by key path (e.g., 'github.comment_header')."""
        keys = key_path.split('.')
        val = self._translations
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return key_path
        
        if isinstance(val, str):
            try:
                return val.format(**kwargs)
            except KeyError as e:
                print(f"i18n Error: Missing key {e} in path '{key_path}' (template: '{val}')")
                return val
        return val

    def t(self, key_path, **kwargs):
        """Alias for get."""
        return self.get(key_path, **kwargs)

i18n = I18nManager()
