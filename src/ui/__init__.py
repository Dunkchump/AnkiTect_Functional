"""UI components for AnkiTect."""

from .workbench import WorkbenchView, create_workbench_view
from .dashboard import DashboardView, create_dashboard_view
from .settings import SettingsView, create_settings_view
from .card_preview import CardPreviewView, CardPreviewRenderer, create_card_preview
from .card_sections_editor import CardSectionsEditor, create_card_sections_editor
from .card_types_editor import CardTypesEditor, create_card_types_editor

__all__ = [
    'WorkbenchView',
    'create_workbench_view',
    'DashboardView',
    'create_dashboard_view',
    'SettingsView',
    'create_settings_view',
    'CardPreviewView',
    'CardPreviewRenderer',
    'create_card_preview',
    'CardSectionsEditor',
    'create_card_sections_editor',
    'CardTypesEditor',
    'create_card_types_editor',
]
