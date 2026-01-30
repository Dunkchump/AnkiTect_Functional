"""
Live Card Preview Component - Real-time Anki card visualization.

Renders card templates with actual data for instant visual feedback
during vocabulary editing in the Workbench.
"""

import html
import re
from typing import Any, Dict, List, Optional

import flet as ft

from ..config import (
    Config, 
    SettingsManager,
    get_default_enabled,
    get_default_order,
    validate_sections_config,
)
from ..templates import CardTemplates


class CardPreviewRenderer:
    """
    Renders Anki card templates with actual vocabulary data.
    
    Converts Mustache-style {{Field}} placeholders to actual values
    and renders HTML/CSS for preview.
    """
    
    # Mustache pattern: {{Field}} or {{#Field}}...{{/Field}}
    FIELD_PATTERN = re.compile(r'\{\{(\#?)(\w+)\}\}')
    CONDITIONAL_PATTERN = re.compile(r'\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}', re.DOTALL)
    
    @classmethod
    def render_template(cls, template: str, data: Dict[str, Any], css: str = "") -> str:
        """
        Render a Mustache-style template with data.
        
        Args:
            template: HTML template with {{Field}} placeholders
            data: Dictionary of field values
            css: Optional CSS to embed
            
        Returns:
            Rendered HTML string
        """
        result = template
        
        # Process conditionals first: {{#Field}}content{{/Field}}
        def replace_conditional(match):
            field = match.group(1)
            content = match.group(2)
            value = data.get(field, "")
            # Show content only if field has value
            if value and str(value).strip() and str(value).lower() != "nan":
                # Recursively process content
                return cls.render_template(content, data)
            return ""
        
        result = cls.CONDITIONAL_PATTERN.sub(replace_conditional, result)
        
        # Replace simple field placeholders: {{Field}}
        def replace_field(match):
            is_section = match.group(1) == "#"
            field = match.group(2)
            if is_section:
                return ""  # Already handled by conditional
            value = data.get(field, "")
            if value is None or str(value).lower() == "nan":
                return ""
            return str(value)
        
        result = cls.FIELD_PATTERN.sub(replace_field, result)
        
        # Wrap in complete HTML document with CSS
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{ 
                    margin: 0; 
                    padding: 10px; 
                    background: #1a1a2e; 
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                }}
                {css}
            </style>
        </head>
        <body>
            {result}
        </body>
        </html>
        """
        
        return full_html
    
    @classmethod
    def render_recognition_front(cls, data: Dict[str, Any]) -> str:
        """Render the Recognition card front (question side)."""
        settings = SettingsManager()
        style = settings.get("CARD_STYLE", CardTemplates.DEFAULT_STYLE)
        template = CardTemplates.get_recognition_template(Config.LABEL)
        return cls.render_template(template, data, CardTemplates.get_css(style))
    
    @classmethod
    def render_recognition_back(
        cls, 
        data: Dict[str, Any],
        sections_enabled: Optional[Dict[str, bool]] = None,
        sections_order: Optional[List[str]] = None,
    ) -> str:
        """
        Render the Recognition card back (answer side) with dynamic sections.
        
        Args:
            data: Card field data
            sections_enabled: Optional dict of section_id -> enabled state
            sections_order: Optional list of section IDs in order
            
        Returns:
            Rendered HTML string
        """
        # Load sections config from settings if not provided
        settings = SettingsManager()
        settings.reload()  # Ensure fresh data from disk
        if sections_enabled is None or sections_order is None:
            sections_enabled = sections_enabled or settings.get(
                "CARD_SECTIONS_ENABLED", 
                get_default_enabled()
            )
            sections_order = sections_order or settings.get(
                "CARD_SECTIONS_ORDER",
                get_default_order()
            )
        style = settings.get("CARD_STYLE", CardTemplates.DEFAULT_STYLE)
        
        # Validate config
        sections_enabled, sections_order = validate_sections_config(
            sections_enabled, sections_order
        )
        
        # Build dynamic template
        template = CardTemplates.build_dynamic_back_template(
            sections_enabled=sections_enabled,
            sections_order=sections_order,
            forvo_code=Config.FORVO_CODE
        )
        
        # Remove JavaScript for preview (not executable in Flet)
        template = re.sub(r'<script.*?</script>', '', template, flags=re.DOTALL)
        return cls.render_template(template, data, CardTemplates.get_css(style))
    
    @classmethod
    def render_production_front(cls, data: Dict[str, Any]) -> str:
        """Render the Production card front."""
        settings = SettingsManager()
        style = settings.get("CARD_STYLE", CardTemplates.DEFAULT_STYLE)
        return cls.render_template(CardTemplates.FRONT_PROD, data, CardTemplates.get_css(style))
    
    @classmethod
    def render_listening_front(cls, data: Dict[str, Any]) -> str:
        """Render the Listening card front."""
        template = re.sub(r'<script.*?</script>', '', CardTemplates.FRONT_LIST, flags=re.DOTALL)
        settings = SettingsManager()
        style = settings.get("CARD_STYLE", CardTemplates.DEFAULT_STYLE)
        return cls.render_template(template, data, CardTemplates.get_css(style))
    
    @classmethod
    def render_cloze_front(cls, data: Dict[str, Any]) -> str:
        """Render the Context Cloze card front."""
        template = re.sub(r'<script.*?</script>', '', CardTemplates.FRONT_CLOZE, flags=re.DOTALL)
        settings = SettingsManager()
        style = settings.get("CARD_STYLE", CardTemplates.DEFAULT_STYLE)
        return cls.render_template(template, data, CardTemplates.get_css(style))


class CardPreviewView:
    """
    Flet component for live Anki card preview.
    
    Shows real-time card preview as user edits vocabulary data.
    Supports multiple card types (Recognition, Production, etc.)
    """
    
    CARD_TYPES = ["Recognition (Front)", "Recognition (Back)", "Production", "Listening", "Cloze"]
    
    def __init__(self, page: ft.Page, initial_data: Optional[Dict[str, Any]] = None):
        """
        Initialize card preview component.
        
        Args:
            page: Flet page instance for updates
            initial_data: Optional initial vocabulary data to display
        """
        self.page = page
        self._data: Dict[str, Any] = initial_data or {}
        self._current_type_index: int = 1  # Default to Recognition Back (answer)
        self._html_content: str = ""
        self._preview_style: Dict[str, str] = {}
        
        # Media paths for preview
        self._preview_image_path: Optional[str] = None
        self._preview_audio_path: Optional[str] = None
        
        # UI References
        self._preview_container: Optional[ft.Container] = None
        self._type_dropdown: Optional[ft.Dropdown] = None
        self._html_view: Optional[ft.Container] = None
        self._view: Optional[ft.Container] = None
    
    def build(self) -> ft.Control:
        """Build the preview component."""
        # Card type selector
        self._type_dropdown = ft.Dropdown(
            value=self.CARD_TYPES[self._current_type_index],
            options=[ft.dropdown.Option(t) for t in self.CARD_TYPES],
            on_select=self._on_type_change,
            width=200,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
        )
        
        # Preview container (will hold rendered HTML as styled text)
        self._preview_container = ft.Container(
            content=self._build_preview_content(),
            bgcolor=ft.Colors.TRANSPARENT,
            border_radius=12,
            padding=0,
            expand=True,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )
        
        self._view = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Row(
                        controls=[
                            ft.Text(
                                "Card Preview",
                                size=14,
                                weight=ft.FontWeight.BOLD,
                                color=ft.Colors.WHITE70,
                            ),
                            ft.Container(expand=True),
                            self._type_dropdown,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Container(height=10),
                    self._preview_container,
                ],
                expand=True,
                spacing=0,
            ),
            expand=True,
            padding=10,
        )
        
        return self._view
    
    def _get_style_config(self) -> Dict[str, str]:
        """Get the current style config for preview rendering."""
        settings = SettingsManager()
        style = settings.get("CARD_STYLE", CardTemplates.DEFAULT_STYLE)
        return CardTemplates.normalize_style(style)

    def _parse_radius(self, value: str, default: int = 12) -> int:
        """Parse a CSS radius value (e.g. "12px") to int."""
        if isinstance(value, (int, float)):
            return int(value)
        try:
            return int(str(value).replace("px", "").strip())
        except (TypeError, ValueError):
            return default

    def _parse_shadow(self, value: str) -> Optional[ft.BoxShadow]:
        """Parse a CSS-like shadow string into a Flet BoxShadow."""
        if not value or value == "none":
            return None
        try:
            parts = value.replace(",", " ").split()
            if len(parts) < 4:
                return None
            x = float(parts[0])
            y = float(parts[1])
            blur = float(parts[2])
            color = parts[3]
            return ft.BoxShadow(
                offset=ft.Offset(x, y),
                blur_radius=blur,
                color=color,
            )
        except Exception:
            return None

    def _build_preview_content(self) -> ft.Control:
        """Build the preview content based on current data and type."""
        self._preview_style = self._get_style_config()
        style = self._preview_style
        radius = self._parse_radius(style.get("card_radius", "12px"))
        shadow = self._parse_shadow(style.get("card_shadow", ""))

        if not self._data:
            return ft.Container(
                content=ft.Row(
                    controls=[
                        ft.Column(
                            controls=[
                                ft.Icon(ft.Icons.PREVIEW, size=48, color=ft.Colors.WHITE24),
                                ft.Text(
                                    "No Data",
                                    size=16,
                                    color=ft.Colors.WHITE38,
                                ),
                                ft.Text(
                                    "Select a word to preview",
                                    size=12,
                                    color=ft.Colors.WHITE24,
                                ),
                            ],
                            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                            alignment=ft.MainAxisAlignment.CENTER,
                            expand=True,
                        ),
                    ],
                    expand=True,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                bgcolor=style.get("card_bg", "#1e1e2e"),
                border_radius=radius,
                expand=True,
            )

        # Render based on selected type
        return ft.Container(
            content=self._render_card_preview(style),
            bgcolor=style.get("card_bg", "#1e1e2e"),
            border_radius=radius,
            shadow=shadow,
            expand=True,
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
        )
    
    def _render_card_preview(self, style: Dict[str, str]) -> ft.Control:
        """Render the card as a styled Flet layout (not HTML)."""
        data = self._data
        card_type = self.CARD_TYPES[self._current_type_index]
        
        if "Front" in card_type or card_type == "Production" or card_type == "Listening" or card_type == "Cloze":
            return self._render_front_preview(data, card_type, style)
        else:
            return self._render_back_preview(data, style)
    
    def _render_front_preview(self, data: Dict[str, Any], card_type: str, style: Dict[str, str]) -> ft.Control:
        """Render front side of card."""
        target_word = data.get("TargetWord", "???")
        meaning = data.get("Meaning", "")
        pos = data.get("Part_of_Speech", "")
        mnemonic = data.get("Mnemonic", "")
        radius = self._parse_radius(style.get("card_radius", "12px"))
        container_bg = style.get("container_bg", "#1b1b1b")
        text_color = style.get("text_color", "#ffffff")
        label_color = style.get("label_color", "#9aa0a6")
        definition_color = style.get("definition_color", text_color)
        
        if card_type == "Production":
            # Production: Show meaning + hint
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text("TRANSLATE", size=10, color=label_color, 
                               weight=ft.FontWeight.BOLD),
                        ft.Container(height=10),
                        ft.Text(meaning, size=18, color=definition_color, 
                               weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
                        ft.Container(height=15),
                        ft.Container(
                            content=ft.Text(f"💡 {mnemonic}", size=12, color=text_color),
                            bgcolor=style.get("card_bg", "#1e1e2e"),
                            padding=10,
                            border_radius=8,
                        ) if mnemonic else ft.Container(),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                padding=30,
                bgcolor=container_bg,
                border_radius=radius,
                expand=True,
            )
        
        elif card_type == "Listening":
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text("🎧", size=48),
                        ft.Container(height=10),
                        ft.Text("Listen & Recognize", size=14, color=label_color),
                        ft.Container(height=15),
                        ft.ElevatedButton(
                            content=ft.Row([ft.Icon(ft.Icons.PLAY_ARROW), ft.Text("Play")], spacing=5),
                            disabled=True,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                padding=30,
                bgcolor=container_bg,
                border_radius=radius,
                expand=True,
            )
        
        elif card_type == "Cloze":
            context = data.get("ContextSentences", "").split("<br>")[0] if data.get("ContextSentences") else ""
            # Replace <b>word</b> with [...]
            context_cloze = re.sub(r'<b>.*?</b>', '[...]', context)
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text("Complete the Context", size=14, color=text_color,
                               weight=ft.FontWeight.BOLD),
                        ft.Container(height=15),
                        ft.Container(
                            content=ft.Text(context_cloze or "No context available", 
                                          size=14, color=text_color),
                            bgcolor=style.get("card_bg", "#1e1e2e"),
                            padding=15,
                            border_radius=8,
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                padding=20,
                bgcolor=container_bg,
                border_radius=radius,
                expand=True,
            )
        
        else:
            # Recognition Front: Show word
            return ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text(Config.LABEL, size=10, color=label_color,
                               weight=ft.FontWeight.BOLD),
                        ft.Container(height=10),
                        ft.Text(target_word, size=32, color=definition_color,
                               weight=ft.FontWeight.W_800),
                        ft.Container(height=5),
                        ft.Text(pos, size=12, color=label_color, 
                               font_family="monospace"),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                padding=30,
                bgcolor=container_bg,
                border_radius=radius,
                expand=True,
            )
    
    def _render_back_preview(self, data: Dict[str, Any], style: Dict[str, str]) -> ft.Control:
        """Render back side of card (full answer) respecting sections config."""
        # Load sections configuration
        settings = SettingsManager()
        sections_enabled = settings.get("CARD_SECTIONS_ENABLED", get_default_enabled())
        sections_order = settings.get("CARD_SECTIONS_ORDER", get_default_order())
        sections_enabled, sections_order = validate_sections_config(sections_enabled, sections_order)
        
        target_word = data.get("TargetWord", "???")
        meaning = data.get("Meaning", "")
        ipa = data.get("IPA", "")
        pos = data.get("Part_of_Speech", "")
        gender = str(data.get("Gender", "")).lower() or "none"
        morphology = data.get("Morphology", "")
        etymology = data.get("Etymology", "")
        mnemonic = data.get("Mnemonic", "")
        nuance = data.get("Nuance", "")
        sentences = data.get("ContextSentences", "")
        translation = data.get("ContextTranslation", "")
        analogues = data.get("Analogues", "")
        
        # Gender-based colors
        gender_colors = {
            "der": (style.get("der_start", "#2980b9"), style.get("der_end", "#3498db")),
            "die": (style.get("die_start", "#c0392b"), style.get("die_end", "#e74c3c")),
            "das": (style.get("das_start", "#27ae60"), style.get("das_end", "#2ecc71")),
            "none": (style.get("none_start", "#8e44ad"), style.get("none_end", "#9b59b6")),
            "en": (style.get("en_start", "#2c3e50"), style.get("en_end", "#4ca1af")),
        }
        header_gradient = gender_colors.get(
            gender,
            (style.get("none_start", "#8e44ad"), style.get("none_end", "#9b59b6")),
        )
        
        # Parse sentences
        sentence_list = [s.strip() for s in sentences.split("<br>") if s.strip()] if sentences else []
        
        # Build section renderers
        section_builders = {
            "header": lambda: self._build_header_section(target_word, ipa, pos, header_gradient, style),
            "meaning": lambda: self._full_width_section(
                "MEANING",
                ft.Text(meaning, size=14, weight=ft.FontWeight.W_600, color=style.get("definition_color", "#ffffff")),
                style,
            ) if meaning else None,
            "morphology": lambda: self._build_morphology_section(
                gender,
                morphology,
                etymology,
                header_gradient[0],
                style,
            ),
            "context": lambda: self._build_context_section(nuance, sentence_list, translation, style),
            "mnemonic": lambda: self._full_width_section(
                "MEMORY HOOK",
                ft.Text(f"💡 {mnemonic}", size=12, color=style.get("text_color", "#ffffff"), no_wrap=False),
                style,
            ) if mnemonic else None,
            "analogues": lambda: self._full_width_section(
                "ANALOGUES",
                ft.Text(analogues, size=12, color=style.get("text_color", "#ffffff")),
                style,
            ) if analogues else None,
            "image": lambda: self._build_image_section(style),
            "footer": lambda: self._build_footer_section(style),
            "tags": lambda: self._build_tags_section(data.get("Tags", ""), style),
        }
        
        # Build sections in configured order
        sections = []
        for section_id in sections_order:
            if not sections_enabled.get(section_id, True):
                continue
            
            builder = section_builders.get(section_id)
            if builder:
                section_content = builder()
                if section_content is not None:
                    sections.append(section_content)
        
        return ft.Container(
            content=ft.Column(
                controls=sections,
                spacing=0,
                scroll=ft.ScrollMode.AUTO,
            ),
            bgcolor=style.get("container_bg", "#1b1b1b"),
            border_radius=self._parse_radius(style.get("card_radius", "12px")),
            clip_behavior=ft.ClipBehavior.HARD_EDGE,
            expand=True,
        )
    
    def _build_header_section(
        self,
        target_word: str,
        ipa: str,
        pos: str,
        header_gradient: tuple,
        style: Dict[str, str],
    ) -> ft.Row:
        """Build the header section with word and pronunciation."""
        radius = self._parse_radius(style.get("card_radius", "12px"))
        return ft.Row(
            controls=[
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(target_word, size=24, color=style.get("header_text", "#ffffff"), 
                                   weight=ft.FontWeight.W_800, text_align=ft.TextAlign.CENTER),
                            ft.Text(f"/{ipa}/ • {pos}", size=11, color=style.get("header_text", "#ffffff"),
                                   font_family="monospace", text_align=ft.TextAlign.CENTER),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=5,
                    ),
                    gradient=ft.LinearGradient(
                        begin=ft.Alignment.TOP_LEFT,
                        end=ft.Alignment.BOTTOM_RIGHT,
                        colors=[header_gradient[0], header_gradient[1]],
                    ),
                    padding=20,
                    border_radius=ft.border_radius.only(top_left=radius, top_right=radius),
                    expand=True,
                )
            ],
            expand=True,
        )
    
    def _build_morphology_section(
        self,
        gender: str,
        morphology: str,
        etymology: str,
        header_color: str,
        style: Dict[str, str],
    ) -> Optional[ft.Row]:
        """Build the morphology and etymology section."""
        if not morphology and not etymology:
            return None
        
        morph_content = []
        if gender and gender != "none":
            morph_content.append(
                ft.Container(
                    content=ft.Text(gender.upper(), size=10, color=style.get("header_text", "#ffffff"),
                                   weight=ft.FontWeight.BOLD),
                    bgcolor=header_color,
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=6,
                )
            )
        if morphology:
            morph_content.append(
                ft.Container(
                    content=ft.Text(morphology, size=10, color=style.get("text_color", "#ffffff")),
                    bgcolor=style.get("card_bg", "#1e1e2e"),
                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                    border_radius=6,
                )
            )
        
        ety_row = ft.Row(controls=morph_content, spacing=5, wrap=True)
        ety_text = ft.Container(
            content=ft.Text(etymology, size=12, color=style.get("text_color", "#ffffff"), italic=True),
            bgcolor=style.get("card_bg", "#1e1e2e"),
            padding=10,
            border_radius=8,
            margin=ft.Margin.only(top=10),
            expand=True,
        ) if etymology else ft.Container()
        
        return self._full_width_section(
            "MORPHOLOGY & ETYMOLOGY",
            ft.Column([ety_row, ety_text], spacing=0, expand=True),
            style,
        )
    
    def _build_context_section(
        self,
        nuance: str,
        sentence_list: List[str],
        translation: str,
        style: Dict[str, str],
    ) -> Optional[ft.Row]:
        """Build the context section with sentences."""
        if not sentence_list and not nuance:
            return None
        
        context_controls = []
        if nuance:
            context_controls.append(ft.Text(nuance, size=12, color=style.get("label_color", "#9aa0a6")))
        
        for sent in sentence_list[:3]:
            context_controls.append(
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.Text(sent, size=12, color=style.get("text_color", "#ffffff"), expand=True),
                            ft.IconButton(ft.Icons.PLAY_CIRCLE_OUTLINE, 
                                        icon_size=18, disabled=True),
                        ],
                        expand=True,
                    ),
                    bgcolor=style.get("card_bg", "#1e1e2e"),
                    padding=8,
                    border_radius=6,
                    border=ft.border.only(left=ft.BorderSide(3, style.get("section_border", "#f2f2f2"))),
                    expand=True,
                )
            )
        
        if translation:
            context_controls.append(
                ft.Text(translation, size=11, color=style.get("label_color", "#9aa0a6"), italic=True)
            )
        
        return self._full_width_section(
            "CONTEXT",
            ft.Column(context_controls, spacing=8, expand=True),
            style,
        )
    
    def _build_image_section(self, style: Dict[str, str]) -> Optional[ft.Row]:
        """Build the image section."""
        if not self._preview_image_path:
            return None
        
        return self._full_width_section("IMAGE",
            ft.Image(
                src=self._preview_image_path,
                fit=ft.BoxFit.FIT_WIDTH,
                border_radius=8,
                expand=True,
            ),
            style,
        )
    
    def _build_footer_section(self, style: Dict[str, str]) -> ft.Row:
        """Build the footer controls section."""
        return ft.Row(
            controls=[
                ft.Container(
                    content=ft.Row(
                        controls=[
                            ft.ElevatedButton(
                                content=ft.Row([ft.Text("🔊 Forvo")], spacing=5),
                                disabled=True,
                            ),
                            ft.ElevatedButton(
                                content=ft.Row([ft.Text("🎧 Listen")], spacing=5),
                                disabled=True,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=15,
                    ),
                    padding=15,
                    bgcolor=style.get("card_bg", "#1e1e2e"),
                    expand=True,
                )
            ],
            expand=True,
        )
    
    def _build_tags_section(self, tags: str, style: Dict[str, str]) -> Optional[ft.Row]:
        """Build the tags section."""
        if not tags:
            return None
        
        tag_list = tags.split() if tags else []
        if not tag_list:
            return None
        
        tag_pills = [
            ft.Container(
                content=ft.Text(tag, size=10, color=style.get("label_color", "#9aa0a6")),
                bgcolor=style.get("card_bg", "#1e1e2e"),
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                border_radius=10,
            )
            for tag in tag_list
        ]
        
        return ft.Row(
            controls=[
                ft.Container(
                    content=ft.Row(controls=tag_pills, spacing=5, wrap=True,
                                  alignment=ft.MainAxisAlignment.CENTER),
                    padding=10,
                    expand=True,
                )
            ],
            expand=True,
        )
    
    def _full_width_section(self, label: str, content: ft.Control, style: Dict[str, str]) -> ft.Row:
        """Create a labeled section that spans full width."""
        return ft.Row(
            controls=[
                ft.Container(
                    content=ft.Column(
                        controls=[
                            ft.Text(label, size=9, color=style.get("label_color", "#9aa0a6"), 
                                   weight=ft.FontWeight.W_800),
                            ft.Container(height=5),
                            ft.Row(
                                controls=[content],
                                expand=True,
                            ),
                        ],
                        spacing=0,
                        expand=True,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                    ),
                    padding=12,
                    bgcolor=style.get("container_bg", "#1b1b1b"),
                    border=ft.border.only(bottom=ft.BorderSide(1, style.get("section_border", "#f2f2f2"))),
                    expand=True,
                )
            ],
            expand=True,
        )
    
    def _section(self, label: str, content: ft.Control) -> ft.Container:
        """Create a labeled section (deprecated, use _full_width_section)."""
        return ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text(label, size=9, color=ft.Colors.WHITE54, 
                           weight=ft.FontWeight.W_800),
                    ft.Container(height=5),
                    content,
                ],
                spacing=0,
            ),
            padding=12,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
            border=ft.border.only(bottom=ft.BorderSide(1, ft.Colors.WHITE10)),
            expand=True,
        )
    
    def _on_type_change(self, e: ft.ControlEvent) -> None:
        """Handle card type dropdown change."""
        selected = e.control.value
        self._current_type_index = self.CARD_TYPES.index(selected)
        self.update_preview(self._data)
        if self.page:
            self.page.update()
    
    def update_preview(self, data: Dict[str, Any]) -> None:
        """
        Update preview with new data.
        
        Args:
            data: Vocabulary data dictionary
        """
        self._data = data or {}
        if self._preview_container:
            self._preview_container.content = self._build_preview_content()
    
    def set_preview_image(self, image_path: Optional[str]) -> None:
        """Set the image to display in card preview."""
        self._preview_image_path = image_path
        self.update_preview(self._data)
    
    def set_preview_audio(self, audio_path: Optional[str]) -> None:
        """Set the audio path for card preview."""
        self._preview_audio_path = audio_path
        self.update_preview(self._data)
    
    def set_card_type(self, type_name: str) -> None:
        """Set the card type to display."""
        if type_name in self.CARD_TYPES:
            self._current_type_index = self.CARD_TYPES.index(type_name)
            if self._type_dropdown:
                self._type_dropdown.value = type_name
            self.update_preview(self._data)


def create_card_preview(page: ft.Page, data: Optional[Dict[str, Any]] = None) -> CardPreviewView:
    """
    Factory function to create a card preview component.
    
    Args:
        page: Flet page instance
        data: Optional initial vocabulary data
        
    Returns:
        Configured CardPreviewView instance
    """
    return CardPreviewView(page=page, initial_data=data)
