"""
Life Ops — Google integration library.

Package structure:
    lib.base             — BaseScript abstract class (logging, timing, CLI)
    lib.models           — Typed dataclasses (Email, Calendar, Drive, Contact)
    lib.google_factory   — GoogleServiceFactory (single credential, lazy services)
    lib.gmail_client     — GmailClient
    lib.calendar_client  — CalendarClient
    lib.sheets_client    — SheetsClient
    lib.drive_client     — DriveClient
    lib.contacts_client  — ContactsClient
"""
