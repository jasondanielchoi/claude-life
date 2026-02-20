"""
Re-authorize with the full 11-scope set.
Run this after adding new scopes to the OAuth consent screen in Cloud Console.
Deletes the existing token and triggers a fresh browser auth flow.
"""
import sys, os
sys.path.insert(0, '/Users/jasonchoi/life')

TOKEN_FILE = os.path.expanduser('~/cred/google_token.json')
if os.path.exists(TOKEN_FILE):
    os.remove(TOKEN_FILE)
    print(f"Deleted old token: {TOKEN_FILE}")

from lib.google_factory import ALL_SCOPES, GoogleServiceFactory

print(f"Requesting {len(ALL_SCOPES)} scopes:")
for s in ALL_SCOPES:
    print(f"  {s}")
print()

factory = GoogleServiceFactory()
_ = factory.credentials   # triggers the browser flow
print("\nRe-auth complete. All services ready.")

# Quick smoke test
from lib.tasks_client import TasksClient
from lib.docs_client import DocsClient

tasks = TasksClient(factory)
lists = tasks.list_task_lists()
print(f"Tasks: {len(lists)} task list(s) — {[l.title for l in lists]}")

docs = DocsClient(factory)
print("Docs API: OK (create/read ready)")
print("\nAll good.")
