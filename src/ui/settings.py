"""
Settings View - Application Configuration UI
----------------------------------------------

Provides a polished UI for configuring AnkiTect settings.
"""

import flet as ft
from datetime import datetime
from typing import Any, Dict, Optional

from src.config.config_manager import SettingsManager
from src.config.languages import LANG_CONFIG
from src.config.settings import SUBDECK_FORMAT_DEFAULT
from src.ui.theme import DesignTokens as DT, show_snackbar


# ---------------------------------------------------------------------------
# Helpers — reduce boilerplate for styled fields
# ---------------------------------------------------------------------------

_FIELD_COMMON = dict(
    border_color=ft.Colors.WHITE12,
    focused_border_color=ft.Colors.INDIGO_200,
    label_style=ft.TextStyle(color=ft.Colors.WHITE54, size=12),
    text_style=ft.TextStyle(color=ft.Colors.WHITE, size=14),
    cursor_color=ft.Colors.INDIGO_200,
    content_padding=ft.Padding.symmetric(horizontal=14, vertical=12),
    border_radius=DT.RADIUS_SM,
)


def _styled_field(*, value: str = "", label: str = "", hint: str = "",
                  width: int | None = None, prefix_icon: str | None = None,
                  password: bool = False, numbers_only: bool = False,
                  on_change=None, **extra) -> ft.TextField:
    """Create a consistently-styled TextField."""
    kw = dict(_FIELD_COMMON)
    kw.update(
        value=value, label=label, hint_text=hint,
    )
    if width:
        kw["width"] = width
    if prefix_icon:
        kw["prefix_icon"] = prefix_icon
    if password:
        kw["password"] = True
        kw["can_reveal_password"] = True
    if numbers_only:
        kw["input_filter"] = ft.NumbersOnlyInputFilter()
    if on_change:
        kw["on_change"] = on_change
    kw.update(extra)
    return ft.TextField(**kw)


# ---------------------------------------------------------------------------
# Settings View
# ---------------------------------------------------------------------------

class SettingsView:
    """Settings view — configures language, deck naming, API keys, performance."""

    LANGUAGE_OPTIONS: Dict[str, str] = {
        "DE": "Deutsch",
        "EN": "English",
    }

    _LANG_FLAGS: Dict[str, str] = {"DE": "\U0001F1E9\U0001F1EA", "EN": "\U0001F1EC\U0001F1E7"}

    # Official Pollinations image models (from enter.pollinations.ai pricing)
    # Format: model_id -> (display_name, images_per_pollen, is_free)
    IMAGE_MODELS_INFO: list[tuple[str, str, str, bool]] = [
        # (key, label, cost_info, is_free)
        ("flux",           "Flux Schnell",        "~5 000 img/pollen",  True),
        ("zimage",         "Z-Image Turbo",       "~5 000 img/pollen",  True),
        ("gptimage",       "GPT Image 1 Mini",    "~75 img/pollen",     True),
        ("klein",          "FLUX.2 Klein 4B",     "~150 img/pollen",    True),
        ("klein-large",    "FLUX.2 Klein 9B",     "~85 img/pollen",     True),
        ("seedream",       "Seedream 4.0",        "~35 img/pollen",     False),
        ("kontext",        "FLUX.1 Kontext",      "~25 img/pollen",     False),
        ("nanobanana",     "NanoBanana",          "~25 img/pollen",     False),
        ("seedream-pro",   "Seedream 4.5 Pro",    "~25 img/pollen",     False),
        ("gptimage-large", "GPT Image 1.5",       "~15 img/pollen",     False),
        ("nanobanana-pro", "NanoBanana Pro",      "~7 img/pollen",      False),
    ]

    IMAGE_MODEL_OPTIONS: Dict[str, str] = {
        m[0]: m[1] for m in IMAGE_MODELS_INFO
    }

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.settings = SettingsManager()

        # UI refs
        self._lang_dropdown: Optional[ft.Dropdown] = None
        self._lang_badge: Optional[ft.Text] = None
        self._deck_name_field: Optional[ft.TextField] = None
        self._subdeck_format_field: Optional[ft.TextField] = None
        self._deck_preview: Optional[ft.Container] = None
        self._deck_preview_text: Optional[ft.Text] = None
        self._api_key_field: Optional[ft.TextField] = None
        self._concurrency_slider: Optional[ft.Slider] = None
        self._concurrency_value: Optional[ft.Text] = None
        self._timeout_field: Optional[ft.TextField] = None
        self._image_timeout_field: Optional[ft.TextField] = None
        self._retries_field: Optional[ft.TextField] = None
        self._performance_switch: Optional[ft.Switch] = None
        self._image_model_dropdown: Optional[ft.Dropdown] = None
        self._save_btn: Optional[ft.Container] = None

        self._has_changes: bool = False
        self._container = self._build_view()

    @property
    def container(self) -> ft.Container:
        return self._container

    # == Build helpers ======================================================

    @staticmethod
    def _section(title: str, icon: str, controls: list,
                 subtitle: str = "", accent: str = DT.ACCENT_PRIMARY) -> ft.Container:
        """Styled card section with accent-colored icon badge."""
        header_row = ft.Row(
            controls=[
                ft.Container(
                    content=ft.Icon(icon, size=18, color="#FFF"),
                    width=34, height=34,
                    border_radius=DT.RADIUS_SM,
                    bgcolor=accent,
                    alignment=ft.Alignment(0, 0),
                ),
                ft.Column(
                    controls=[
                        ft.Text(title, size=15, weight=ft.FontWeight.W_600,
                                color=DT.TEXT_PRIMARY),
                        *(
                            [ft.Text(subtitle, size=11, color=DT.TEXT_TERTIARY)]
                            if subtitle else []
                        ),
                    ],
                    spacing=1,
                ),
            ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        return ft.Container(
            content=ft.Column(
                controls=[header_row, ft.Divider(height=1, color=ft.Colors.WHITE10),
                          *controls],
                spacing=DT.SPACING_MD,
            ),
            padding=ft.Padding.all(20),
            border_radius=DT.RADIUS_MD,
            bgcolor=DT.BG_CARD,
            border=ft.Border.all(1, ft.Colors.WHITE10),
        )

    # == Language & Deck (merged) ==========================================

    def _build_language_and_deck_section(self) -> ft.Container:
        current_lang = self.settings.get("CURRENT_LANG", "DE")
        custom_deck = self.settings.get("DECK_NAME", "")
        custom_subdeck = self.settings.get("SUBDECK_FORMAT", "")
        lang_cfg = LANG_CONFIG.get(current_lang, LANG_CONFIG["DE"])

        self._lang_badge = ft.Text(
            f"{self._LANG_FLAGS.get(current_lang, '')}  {current_lang}",
            size=13, weight=ft.FontWeight.W_600, color=DT.TEXT_PRIMARY,
        )

        self._lang_dropdown = ft.Dropdown(
            value=current_lang,
            options=[
                ft.dropdown.Option(
                    key=code,
                    text=f"{self._LANG_FLAGS.get(code, '')}  {name}",
                )
                for code, name in self.LANGUAGE_OPTIONS.items()
            ],
            label="Target Language",
            border_color=ft.Colors.WHITE12,
            focused_border_color=ft.Colors.INDIGO_200,
            label_style=ft.TextStyle(color=ft.Colors.WHITE54, size=12),
            text_style=ft.TextStyle(color=ft.Colors.WHITE, size=14),
            border_radius=DT.RADIUS_SM,
            width=260,
            on_select=self._on_language_change,
        )

        self._deck_name_field = _styled_field(
            value=custom_deck,
            label="Deck Name",
            hint=lang_cfg["deck_name"],
            prefix_icon=ft.Icons.STYLE_ROUNDED,
            on_change=lambda _: self._update_deck_preview(),
        )

        self._subdeck_format_field = _styled_field(
            value=custom_subdeck,
            label="Sub-deck Format",
            hint=SUBDECK_FORMAT_DEFAULT,
            prefix_icon=ft.Icons.FOLDER_OPEN_ROUNDED,
            on_change=lambda _: self._update_deck_preview(),
        )

        self._deck_preview_text = ft.Text(
            "", size=13, weight=ft.FontWeight.W_500,
            color=ft.Colors.INDIGO_200,
        )
        self._deck_preview = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.ACCOUNT_TREE_ROUNDED, size=16,
                            color=ft.Colors.INDIGO_300),
                    self._deck_preview_text,
                ],
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            border_radius=DT.RADIUS_SM,
            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.INDIGO_200),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.INDIGO_200)),
        )
        self._update_deck_preview()

        token_hint = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.INFO_OUTLINE, size=13, color=DT.TEXT_MUTED),
                    ft.Text(
                        "Tokens:  {year}   {month}   {month_name}    \u2022    "
                        "Leave empty for language default",
                        size=11, color=DT.TEXT_MUTED,
                        font_family=DT.FONT_MONO,
                    ),
                ],
                spacing=6,
            ),
        )

        return self._section(
            "Language & Deck", ft.Icons.TRANSLATE_ROUNDED,
            [
                ft.Row(
                    controls=[self._lang_dropdown, self._lang_badge],
                    spacing=14,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(height=4),
                ft.Text("Deck Naming", size=13, weight=ft.FontWeight.W_500,
                         color=DT.TEXT_SECONDARY),
                self._deck_name_field,
                self._subdeck_format_field,
                token_hint,
                ft.Container(height=2),
                self._deck_preview,
            ],
            subtitle="Target language, deck & sub-deck names",
            accent="#5C6BC0",
        )

    # == API section ========================================================

    def _build_api_section(self) -> ft.Container:
        current_key = self.settings.get("POLLINATIONS_API_KEY", "")
        current_model = self.settings.get("POLLINATIONS_IMAGE_MODEL", "flux")

        self._api_key_field = _styled_field(
            value=current_key,
            label="Pollinations API Key",
            hint="sk_... or pk_...",
            prefix_icon=ft.Icons.KEY_ROUNDED,
            password=True,
        )

        # Build dropdown options with free/paid markers
        dropdown_options = []
        for key, label, cost, is_free in self.IMAGE_MODELS_INFO:
            tag = "\u2714 FREE" if is_free else "\U0001F48E PAID"
            dropdown_options.append(
                ft.dropdown.Option(key=key, text=f"{label}  ({tag})")
            )

        self._image_model_dropdown = ft.Dropdown(
            value=current_model if current_model in self.IMAGE_MODEL_OPTIONS else "flux",
            options=dropdown_options,
            label="Image Generation Model",
            border_color=ft.Colors.WHITE12,
            focused_border_color=ft.Colors.INDIGO_200,
            label_style=ft.TextStyle(color=ft.Colors.WHITE54, size=12),
            text_style=ft.TextStyle(color=ft.Colors.WHITE, size=14),
            border_radius=DT.RADIUS_SM,
            width=320,
            on_select=lambda _: self._mark_changed(),
        )

        info_row = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.OPEN_IN_NEW, size=13, color=ft.Colors.TEAL_200),
                    ft.Text("Get your key at enter.pollinations.ai",
                            size=11, color=ft.Colors.TEAL_200),
                ],
                spacing=6,
            ),
        )

        # Build pricing info table
        pricing_rows: list[ft.Control] = []
        # Header
        pricing_rows.append(ft.Row(
            controls=[
                ft.Text("Model", size=11, weight=ft.FontWeight.W_600,
                        color=DT.TEXT_SECONDARY, width=150),
                ft.Text("Cost", size=11, weight=ft.FontWeight.W_600,
                        color=DT.TEXT_SECONDARY, width=130),
                ft.Text("Access", size=11, weight=ft.FontWeight.W_600,
                        color=DT.TEXT_SECONDARY, width=70),
            ],
            spacing=4,
        ))
        pricing_rows.append(ft.Divider(height=1, color=ft.Colors.WHITE10))

        for key, label, cost, is_free in self.IMAGE_MODELS_INFO:
            access_color = "#66BB6A" if is_free else "#FFA726"
            access_text = "\u2714 Free" if is_free else "\U0001F48E Paid"
            pricing_rows.append(ft.Row(
                controls=[
                    ft.Text(label, size=11, color=DT.TEXT_PRIMARY, width=150),
                    ft.Text(cost, size=11, color=DT.TEXT_MUTED,
                            font_family=DT.FONT_MONO, width=130),
                    ft.Text(access_text, size=11, color=access_color, width=70),
                ],
                spacing=4,
            ))

        pricing_table = ft.Container(
            content=ft.Column(controls=pricing_rows, spacing=3),
            padding=ft.Padding.all(12),
            border_radius=DT.RADIUS_SM,
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.WHITE),
            border=ft.Border.all(1, ft.Colors.WHITE10),
        )

        # Legend
        legend = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.INFO_OUTLINE, size=13, color=DT.TEXT_MUTED),
                            ft.Text(
                                "1 pollen = daily free credit. "
                                "FREE models work with daily tier grant.",
                                size=11, color=DT.TEXT_MUTED,
                            ),
                        ],
                        spacing=6,
                    ),
                    ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.DIAMOND_OUTLINED, size=13, color="#FFA726"),
                            ft.Text(
                                "PAID models require purchased pollen (not daily grant).",
                                size=11, color="#FFA726",
                            ),
                        ],
                        spacing=6,
                    ),
                ],
                spacing=4,
            ),
        )

        return self._section(
            "API & Image Generation", ft.Icons.VPN_KEY_ROUNDED,
            [
                info_row,
                self._api_key_field,
                ft.Container(height=8),
                ft.Text("Image Model", size=13, weight=ft.FontWeight.W_500,
                         color=DT.TEXT_SECONDARY),
                self._image_model_dropdown,
                ft.Container(height=8),
                ft.Text("Model Pricing", size=13, weight=ft.FontWeight.W_500,
                         color=DT.TEXT_SECONDARY),
                pricing_table,
                legend,
            ],
            subtitle="API credentials & image generation model",
            accent="#00897B",
        )

    # == Performance section ================================================

    def _build_performance_section(self) -> ft.Container:
        g = self.settings.get

        concurrency = g("CONCURRENCY", 4)
        self._concurrency_value = ft.Text(
            str(concurrency), size=15, weight=ft.FontWeight.W_600,
            color=ft.Colors.INDIGO_200,
        )

        self._concurrency_slider = ft.Slider(
            min=1, max=16, divisions=15,
            value=concurrency,
            active_color=ft.Colors.INDIGO_400,
            inactive_color=ft.Colors.WHITE12,
            on_change_end=self._on_concurrency_change,
        )

        concurrency_row = ft.Row(
            controls=[
                ft.Text("Concurrency", size=13, color=DT.TEXT_SECONDARY),
                ft.Container(expand=True),
                self._concurrency_value,
            ],
        )

        self._timeout_field = _styled_field(
            value=str(g("TIMEOUT", 60)),
            label="Timeout (s)", width=150, numbers_only=True,
        )
        self._image_timeout_field = _styled_field(
            value=str(g("IMAGE_TIMEOUT", 90)),
            label="Image Timeout (s)", width=150, numbers_only=True,
        )
        self._retries_field = _styled_field(
            value=str(g("RETRIES", 5)),
            label="Retries", width=120, numbers_only=True,
        )

        self._performance_switch = ft.Switch(
            value=bool(g("PERFORMANCE_MODE", False)),
            label="Performance Mode",
            on_change=lambda _: self._mark_changed(),
            active_color=ft.Colors.INDIGO_400,
        )

        return self._section(
            "Performance", ft.Icons.SPEED_ROUNDED,
            [
                concurrency_row,
                self._concurrency_slider,
                ft.Text("Higher values = faster builds, may trigger rate limits.",
                         size=11, color=DT.TEXT_MUTED),
                ft.Container(height=8),
                ft.Row(
                    controls=[self._timeout_field,
                              self._image_timeout_field,
                              self._retries_field],
                    spacing=12, wrap=True,
                ),
                ft.Container(height=4),
                self._performance_switch,
            ],
            subtitle="Network, concurrency & timeouts",
            accent="#EF6C00",
        )

    # == Main view ==========================================================

    def _build_view(self) -> ft.Container:
        sections = [
            self._build_language_and_deck_section(),
            self._build_api_section(),
            self._build_performance_section(),
        ]

        # Save button — polished elevated button
        self._save_btn = ft.ElevatedButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.SAVE_ROUNDED, size=18),
                    ft.Text("Save Settings", size=14,
                            weight=ft.FontWeight.W_600),
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            style=ft.ButtonStyle(
                color=DT.TEXT_PRIMARY,
                bgcolor={
                    ft.ControlState.DEFAULT: DT.ACCENT_PRIMARY,
                    ft.ControlState.HOVERED: DT.ACCENT_PRIMARY_HOVER,
                    ft.ControlState.PRESSED: "#6A3FE0",
                },
                shape=ft.RoundedRectangleBorder(radius=DT.RADIUS_SM),
                elevation={"default": 2, "hovered": 4},
                padding=ft.Padding.symmetric(horizontal=28, vertical=14),
                animation_duration=150,
            ),
            height=DT.BUTTON_HEIGHT_LG,
            on_click=self._on_save_click,
        )

        reset_btn = ft.TextButton(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.Icons.RESTART_ALT_ROUNDED, size=16, color=DT.TEXT_MUTED),
                    ft.Text("Reset to Defaults", size=13, color=DT.TEXT_MUTED),
                ],
                spacing=6,
                tight=True,
            ),
            style=ft.ButtonStyle(
                padding=ft.Padding.symmetric(horizontal=16, vertical=10),
                shape=ft.RoundedRectangleBorder(radius=DT.RADIUS_SM),
            ),
            on_click=self._on_reset_click,
        )

        header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(ft.Icons.SETTINGS_ROUNDED, size=26, color="#FFF"),
                        width=48, height=48,
                        border_radius=DT.RADIUS_MD,
                        bgcolor=DT.ACCENT_PRIMARY,
                        alignment=ft.Alignment(0, 0),
                    ),
                    ft.Column(
                        controls=[
                            ft.Text("Settings", size=26, weight=ft.FontWeight.BOLD,
                                    color=DT.TEXT_PRIMARY),
                            ft.Text("Configure your AnkiTect preferences", size=13,
                                    color=DT.TEXT_TERTIARY),
                        ],
                        spacing=2,
                    ),
                ],
                spacing=16,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.Padding.only(bottom=20),
        )

        scroll_content = ft.Column(
            controls=[
                *sections,
                ft.Container(height=12),
                ft.Row(
                    controls=[reset_btn, ft.Container(expand=True), self._save_btn],
                ),
                ft.Container(height=20),
            ],
            spacing=20,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

        return ft.Container(
            content=ft.Column(controls=[header, scroll_content], expand=True),
            expand=True,
            padding=10,
        )

    # == Callbacks ==========================================================

    def _mark_changed(self) -> None:
        self._has_changes = True

    def _on_language_change(self, e: ft.ControlEvent) -> None:
        """Language changed — update deck name placeholder + preview."""
        self._mark_changed()
        # Read selected value from event data (more reliable in Flet 0.80.1)
        lang = getattr(e, 'data', None) or (self._lang_dropdown.value if self._lang_dropdown else "DE")
        lang_cfg = LANG_CONFIG.get(lang, LANG_CONFIG["DE"])

        if self._deck_name_field:
            self._deck_name_field.hint_text = lang_cfg["deck_name"]
        if self._lang_badge:
            self._lang_badge.value = f"{self._LANG_FLAGS.get(lang, '')}  {lang}"
            self._lang_badge.update()

        self._update_deck_preview()

    def _update_deck_preview(self) -> None:
        """Recompute the live preview using current field values."""
        lang = self._lang_dropdown.value if self._lang_dropdown else "DE"
        lang_cfg = LANG_CONFIG.get(lang, LANG_CONFIG["DE"])

        custom_deck = (self._deck_name_field.value or "").strip() if self._deck_name_field else ""
        deck_base = custom_deck if custom_deck else lang_cfg["deck_name"]

        custom_fmt = (self._subdeck_format_field.value or "").strip() if self._subdeck_format_field else ""
        subdeck_fmt = custom_fmt if custom_fmt else SUBDECK_FORMAT_DEFAULT

        now = datetime.now()
        month_names = lang_cfg["month_names"]
        try:
            subdeck = subdeck_fmt.format(
                year=now.year, month=f"{now.month:02d}",
                month_name=month_names[now.month],
            )
        except (KeyError, ValueError, IndexError):
            subdeck = SUBDECK_FORMAT_DEFAULT.format(
                year=now.year, month=f"{now.month:02d}",
                month_name=month_names[now.month],
            )

        if self._deck_preview_text:
            self._deck_preview_text.value = f"{deck_base}  ::  {subdeck}"

        self._mark_changed()
        self.page.update()

    def _on_concurrency_change(self, e: ft.ControlEvent) -> None:
        value = int(e.control.value)
        if self._concurrency_value:
            self._concurrency_value.value = str(value)
        self._mark_changed()
        self.page.update()

    def _on_save_click(self, e) -> None:
        try:
            lang = self._lang_dropdown.value if self._lang_dropdown else "DE"
            api_key = self._api_key_field.value if self._api_key_field else ""
            concurrency = int(self._concurrency_slider.value) if self._concurrency_slider else 4
            timeout = int(self._timeout_field.value or 60) if self._timeout_field else 60
            img_timeout = int(self._image_timeout_field.value or 90) if self._image_timeout_field else 90
            retries = int(self._retries_field.value or 5) if self._retries_field else 5
            perf_mode = bool(self._performance_switch.value) if self._performance_switch else False
            deck_name = (self._deck_name_field.value or "").strip() if self._deck_name_field else ""
            subdeck_fmt = (self._subdeck_format_field.value or "").strip() if self._subdeck_format_field else ""

            image_model = self._image_model_dropdown.value if self._image_model_dropdown else "flux"

            self.settings.batch_set({
                "CURRENT_LANG": lang,
                "DECK_NAME": deck_name,
                "SUBDECK_FORMAT": subdeck_fmt,
                "POLLINATIONS_API_KEY": api_key,
                "POLLINATIONS_IMAGE_MODEL": image_model,
                "CONCURRENCY": concurrency,
                "TIMEOUT": timeout,
                "IMAGE_TIMEOUT": img_timeout,
                "RETRIES": retries,
                "PERFORMANCE_MODE": perf_mode,
            })

            from src.config.settings import Config
            Config.reload_from_settings()

            self._has_changes = False
            self._show_snackbar("Settings saved successfully!")
        except Exception as ex:
            self._show_snackbar(f"Error saving: {ex}", error=True)

    def _on_reset_click(self, e) -> None:
        self.settings.reset()
        self._reload_ui()
        self._show_snackbar("Settings reset to defaults")

    def _reload_ui(self) -> None:
        """Reload all fields from persisted settings."""
        g = self.settings.get
        if self._lang_dropdown:
            self._lang_dropdown.value = g("CURRENT_LANG", "DE")
        if self._deck_name_field:
            self._deck_name_field.value = g("DECK_NAME", "")
            lang = g("CURRENT_LANG", "DE")
            lang_cfg = LANG_CONFIG.get(lang, LANG_CONFIG["DE"])
            self._deck_name_field.hint_text = lang_cfg["deck_name"]
        if self._subdeck_format_field:
            self._subdeck_format_field.value = g("SUBDECK_FORMAT", "")
        if self._api_key_field:
            self._api_key_field.value = g("POLLINATIONS_API_KEY", "")
        if self._image_model_dropdown:
            model = g("POLLINATIONS_IMAGE_MODEL", "flux")
            self._image_model_dropdown.value = model if model in self.IMAGE_MODEL_OPTIONS else "flux"
        if self._concurrency_slider:
            v = g("CONCURRENCY", 4)
            self._concurrency_slider.value = v
            if self._concurrency_value:
                self._concurrency_value.value = str(v)
        if self._timeout_field:
            self._timeout_field.value = str(g("TIMEOUT", 60))
        if self._image_timeout_field:
            self._image_timeout_field.value = str(g("IMAGE_TIMEOUT", 90))
        if self._retries_field:
            self._retries_field.value = str(g("RETRIES", 5))
        if self._performance_switch:
            self._performance_switch.value = bool(g("PERFORMANCE_MODE", False))
        if self._lang_badge:
            lang = g("CURRENT_LANG", "DE")
            self._lang_badge.value = f"{self._LANG_FLAGS.get(lang, '')}  {lang}"

        self._update_deck_preview()
        self._has_changes = False
        self.page.update()

    def _show_snackbar(self, message: str, error: bool = False) -> None:
        show_snackbar(self.page, message, error=error)


def create_settings_view(page: ft.Page) -> ft.Container:
    return SettingsView(page).container
