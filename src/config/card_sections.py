"""
Card Sections Configuration
----------------------------

Defines all available sections in Anki cards with their properties.
Sections can be enabled/disabled and reordered by the user.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class CardSection:
    """Definition of a single card section."""
    
    id: str
    name: str
    description: str
    required: bool = False
    default_enabled: bool = True
    default_order: int = 0
    icon: str = "📝"
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "required": self.required,
            "default_enabled": self.default_enabled,
            "default_order": self.default_order,
            "icon": self.icon,
        }


# All available card sections with their definitions
CARD_SECTIONS: Dict[str, CardSection] = {
    "header": CardSection(
        id="header",
        name="Header (Word & IPA)",
        description="Main word with pronunciation, gender, and part of speech",
        required=True,
        default_enabled=True,
        default_order=0,
        icon="🔤",
    ),
    "meaning": CardSection(
        id="meaning",
        name="Meaning",
        description="Word translation or definition",
        required=True,
        default_enabled=True,
        default_order=1,
        icon="📖",
    ),
    "morphology": CardSection(
        id="morphology",
        name="Morphology & Etymology",
        description="Word formation, gender pill, and word origin story",
        required=False,
        default_enabled=True,
        default_order=2,
        icon="🧬",
    ),
    "context": CardSection(
        id="context",
        name="Context & Sentences",
        description="Usage nuance and example sentences with audio",
        required=False,
        default_enabled=True,
        default_order=3,
        icon="💬",
    ),
    "mnemonic": CardSection(
        id="mnemonic",
        name="Memory Hook",
        description="Mnemonic tip to help remember the word",
        required=False,
        default_enabled=True,
        default_order=4,
        icon="💡",
    ),
    "analogues": CardSection(
        id="analogues",
        name="Analogues",
        description="Similar words in other languages (cognates)",
        required=False,
        default_enabled=True,
        default_order=5,
        icon="🌍",
    ),
    "image": CardSection(
        id="image",
        name="Image",
        description="AI-generated visual association image",
        required=False,
        default_enabled=True,
        default_order=6,
        icon="🖼️",
    ),
    "footer": CardSection(
        id="footer",
        name="Footer Controls",
        description="Forvo pronunciation link and Listen button",
        required=False,
        default_enabled=True,
        default_order=7,
        icon="🎛️",
    ),
    "tags": CardSection(
        id="tags",
        name="Tags",
        description="Category and topic tags",
        required=False,
        default_enabled=True,
        default_order=8,
        icon="🏷️",
    ),
}


def get_section_ids() -> List[str]:
    """Get list of all section IDs in default order."""
    return sorted(CARD_SECTIONS.keys(), key=lambda x: CARD_SECTIONS[x].default_order)


def get_default_enabled() -> Dict[str, bool]:
    """Get default enabled state for all sections."""
    return {
        section_id: section.default_enabled 
        for section_id, section in CARD_SECTIONS.items()
    }


def get_default_order() -> List[str]:
    """Get default section order as list of IDs."""
    return get_section_ids()


def validate_sections_config(
    enabled: Optional[Dict[str, bool]] = None,
    order: Optional[List[str]] = None
) -> tuple[Dict[str, bool], List[str]]:
    """
    Validate and normalize sections configuration.
    
    If enabled dict is incomplete (missing some section IDs), missing sections
    will be set to False (disabled), not True. This ensures user's explicit
    choices are preserved and undefined sections don't appear unexpectedly.
    
    Args:
        enabled: Dict of section_id -> enabled state
        order: List of section IDs in desired order
        
    Returns:
        Tuple of (validated_enabled, validated_order)
    """
    # Validate enabled dict
    # Start with all sections DISABLED by default
    # Only enable sections that are explicitly set to True in the input
    validated_enabled: Dict[str, bool] = {}
    
    for section_id, section in CARD_SECTIONS.items():
        if section.required:
            # Required sections are always enabled
            validated_enabled[section_id] = True
        elif enabled and section_id in enabled:
            # Use the value from input
            validated_enabled[section_id] = bool(enabled[section_id])
        elif enabled is None or len(enabled) == 0:
            # No input provided - use defaults (all enabled)
            validated_enabled[section_id] = section.default_enabled
        else:
            # Input provided but this section is missing - keep it disabled
            # This handles the case of incomplete/partial dicts
            validated_enabled[section_id] = False
    
    # Validate order list
    validated_order = get_default_order()
    if order:
        # Keep only valid section IDs
        valid_ids = [sid for sid in order if sid in CARD_SECTIONS]
        # Add any missing sections at the end
        missing = [sid for sid in get_section_ids() if sid not in valid_ids]
        validated_order = valid_ids + missing
    
    return validated_enabled, validated_order


def get_active_sections(
    enabled: Dict[str, bool],
    order: List[str]
) -> List[CardSection]:
    """
    Get list of active (enabled) sections in specified order.
    
    Args:
        enabled: Dict of section_id -> enabled state
        order: List of section IDs in desired order
        
    Returns:
        List of CardSection objects that are enabled, in order
    """
    validated_enabled, validated_order = validate_sections_config(enabled, order)
    
    return [
        CARD_SECTIONS[section_id]
        for section_id in validated_order
        if validated_enabled.get(section_id, True)
    ]
