"""
Email domain providers
Supports multiple email systems: SendGrid, Mailgun, AWS SES, etc.
"""

from .sendgrid import SendGridProvider
from .mailgun import MailgunProvider

__all__ = ['SendGridProvider', 'MailgunProvider']
