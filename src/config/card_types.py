"""
Card Types Configuration
------------------------

Defines all available Anki card types with their properties.
Card types can be enabled/disabled and reordered by the user.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class CardType:
    """Definition of a single card type."""

    id: str
    name: str
    description: str
    required: bool = False
    default_enabled: bool = True
    default_order: int = 0
    icon: str = "🗂️"

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


CARD_TYPES: Dict[str, CardType] = {
    "recognition": CardType(
        id="recognition",
        name="Recognition",
        description="Classic front: word → back: full card",
        required=True,
        default_enabled=True,
        default_order=0,
        icon="🧠",
    ),
    "production": CardType(
        id="production",
        name="Production",
        description="Front: meaning → write the word",
        required=False,
        default_enabled=True,
        default_order=1,
        icon="✍️",
    ),
    "listening": CardType(
        id="listening",
        name="Listening",
        description="Front: audio → recognize the word",
        required=False,
        default_enabled=True,
        default_order=2,
        icon="🎧",
    ),
    "context": CardType(
        id="context",
        name="Context Cloze",
        description="Front: sentence cloze → infer the word",
        required=False,
        default_enabled=True,
        default_order=3,
        icon="🧩",
    ),
}


def get_card_type_ids() -> List[str]:
    """Get list of all card type IDs in default order."""
    return sorted(CARD_TYPES.keys(), key=lambda x: CARD_TYPES[x].default_order)


def get_default_card_types_enabled() -> Dict[str, bool]:
    """Get default enabled state for all card types."""
    return {
        card_type_id: card_type.default_enabled
        for card_type_id, card_type in CARD_TYPES.items()
    }


def get_default_card_types_order() -> List[str]:
    """Get default card type order as list of IDs."""
    return get_card_type_ids()


def validate_card_types_config(
    enabled: Optional[Dict[str, bool]] = None,
    order: Optional[List[str]] = None,
) -> tuple[Dict[str, bool], List[str]]:
    """
    Validate and normalize card types configuration.

    If enabled dict is incomplete (missing some card IDs), missing types
    will be set to False (disabled), not True.
    """
    validated_enabled: Dict[str, bool] = {}

    for type_id, card_type in CARD_TYPES.items():
        if card_type.required:
            validated_enabled[type_id] = True
        elif enabled and type_id in enabled:
            validated_enabled[type_id] = bool(enabled[type_id])
        elif enabled is None or len(enabled) == 0:
            validated_enabled[type_id] = card_type.default_enabled
        else:
            validated_enabled[type_id] = False

    validated_order = get_default_card_types_order()
    if order:
        valid_ids = [tid for tid in order if tid in CARD_TYPES]
        missing = [tid for tid in get_card_type_ids() if tid not in valid_ids]
        validated_order = valid_ids + missing

    return validated_enabled, validated_order


def get_active_card_types(
    enabled: Dict[str, bool],
    order: List[str],
) -> List[CardType]:
    """Get list of active (enabled) card types in specified order."""
    validated_enabled, validated_order = validate_card_types_config(enabled, order)

    return [
        CARD_TYPES[type_id]
        for type_id in validated_order
        if validated_enabled.get(type_id, True)
    ]
