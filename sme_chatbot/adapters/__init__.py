"""Channel adapters.

Each adapter translates between a channel's wire format and the engine's
`CanonicalMessage`, and sends outbound replies via that channel.

Implementations:

    `whatsapp.WhatsAppCloudAdapter` — Meta WhatsApp Business Cloud API.
    `widget.WidgetAdapter`          — Embeddable web widget (first-party).
"""

from .whatsapp import WhatsAppCloudAdapter
from .widget import WidgetAdapter

__all__ = ["WhatsAppCloudAdapter", "WidgetAdapter"]
