"""
Booking domain providers
Supports multiple booking systems: Calendly, Google Calendar, MS Bookings, etc.
"""

from .calendly import CalendlyProvider
from .google_calendar import GoogleCalendarProvider
from .ms_bookings import MSBookingsProvider

__all__ = ['CalendlyProvider', 'GoogleCalendarProvider', 'MSBookingsProvider']
