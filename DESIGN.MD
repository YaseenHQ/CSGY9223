# DESIGN.md — Chat Client Service (HW2 Scaffold)
 
> **Status:** First-draft scaffold. Core routes return `501 Not Implemented` intentionally.
> Full OAuth, Telegram delegation, and OpenAPI client generation are planned for final submission.
 
---
 
## Architecture Overview
 
### What Changed from HW1
 
In HW1, the Telegram implementation was imported directly as a library — wired in at import time via dependency injection. Every consumer of `chat_client_api` had to have the Telegram credentials and implementation installed locally.
 
HW2 introduces a **service-oriented architecture**: the implementation is wrapped in a standalone FastAPI process that exposes chat operations over HTTP. Consumers talk to the service through a generated API client and an adapter — and crucially, their calling code does not change.
 
```
[User Code]
    │  calls chat_client_api.get_client() — same as HW1
    ▼
[chat_client_adapter]           ← NEW: implements chat_client_api.Client
    │  delegates to →
[chat_client_service_api_client]  ← NEW: stable wrapper around generated HTTP client
    │  HTTP requests →
[chat_client_service]           ← NEW: FastAPI service (runs as independent process)
    │  (will delegate to) →
[telegram_client_impl]          ← HW1: unchanged Telegram implementation
```
 
### Components
 
| Component | Role |
|---|---|
| `chat_client_api` | Unchanged HW1 interface (`Client`, `Message`, `Channel`) |
| `telegram_client_impl` | Unchanged HW1 Telegram implementation |
| `chat_client_service` | New FastAPI service — wraps implementation, exposes HTTP endpoints |
| `chat_client_service_api_client` | New HTTP client wrapper — stable layer over the generated OpenAPI client |
| `chat_client_adapter` | New adapter — implements `chat_client_api.Client` by delegating to the service client |
 
---
 
## Request Flow
 
A complete `send_message` call travels through all three bridges:
 
```
User Code
  │
  │  client = chat_client_api.get_client()
  │  # at import time, chat_client_adapter rebinds get_client
  │  # so this returns a ServiceBackedChatClient
  │
  ▼
chat_client_adapter.ServiceBackedChatClient.send_message(channel_id, text)
  │
  │  calls → self._service_client.send_message(channel_id=..., text=...)
  │
  ▼
chat_client_service_api_client.ChatServiceApiClient.send_message(...)
  │
  │  HTTP POST → /chat/messages
  │
  ▼
chat_client_service  (FastAPI)
  │  POST /chat/messages
  │  [scaffold: currently returns 501]
  │  [final: delegates to telegram_client_impl]
  │
  ▼
HTTP Response (JSON)
  │
  ▼
chat_client_service_api_client  (parses response → DTO)
  │
  ▼
chat_client_adapter  (maps DTO → AdapterMessage implementing chat_client_api.Message)
  │
  ▼
User Code receives a Message object — identical interface to HW1
```
 
---
 
## Sample API Response
 
The `/health` endpoint is the only fully implemented route in this scaffold. A real response looks like:
 
```json
{
  "status": "ok"
}
```
 
For chat endpoints (scaffold state), the service currently returns HTTP `501` with a per-route detail message, e.g.:
 
```json
{
  "detail": "send_message is not implemented in scaffold."
}
``` The final response shape for `POST /chat/messages` will be:
 
```json
{
  "id": "msg_abc123",
  "sender": "user_xyz",
  "channel_id": "channel_001",
  "timestamp": "2026-03-24T12:00:00Z",
  "text": "Hello from the service!"
}
```
 
---
 
## API Design
 
### Endpoints
 
#### Health
 
| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Returns service liveness status |
 
**Response:**
```json
{ "status": "ok" }
```
 
#### Auth (Scaffold — returns placeholder responses)
 
| Method | Path | Description |
|---|---|---|
| `GET` | `/auth/login` | Returns placeholder OAuth redirect details (200) |
| `GET` | `/auth/callback` | Echoes code/state query params (200) |
 
Both return `200` with scaffold payloads — they are not `501`s. Full OAuth 2.0/OIDC logic is a final-submission follow-up.
 
**`GET /auth/login` response:**
```json
{
  "authorization_url": "https://oauth.telegram.org/auth",
  "state": "scaffold-state"
}
```
 
**`GET /auth/callback?code=abc&state=xyz` response:**
```json
{
  "detail": "OAuth callback scaffold endpoint.",
  "code": "abc",
  "state": "xyz"
}
```
 
#### Chat
 
| Method | Path | Description | Status |
|---|---|---|---|
| `POST` | `/chat/messages` | Send a message to a channel | 501 scaffold |
| `GET` | `/chat/messages` | List messages from a channel | 501 scaffold |
| `DELETE` | `/chat/messages/{message_id}` | Delete a specific message | 501 scaffold |
| `GET` | `/chat/channels` | List available channels | 501 scaffold |
 
**Request model for `POST /chat/messages`:**
```json
{
  "channel_id": "string (min_length=1)",
  "text": "string (min_length=1)"
}
```
 
**Response model for messages:**
```json
{
  "id": "string",
  "sender": "string",
  "channel_id": "string",
  "timestamp": "string (ISO 8601)",
  "text": "string"
}
```
 
**Response model for `DELETE /chat/messages/{message_id}`:**
```json
{
  "success": true
}
```
 
### Error Handling
 
| Scenario | HTTP Status | Response |
|---|---|---|
| Unimplemented chat route (scaffold) | `501 Not Implemented` | `{"detail": "<route_name> is not implemented in scaffold."}` |
| Auth login (scaffold) | `200 OK` | `{"authorization_url": "...", "state": "scaffold-state"}` |
| Auth callback (scaffold) | `200 OK` | `{"detail": "OAuth callback scaffold endpoint.", "code": "...", "state": "..."}` |
| Invalid request body | `422 Unprocessable Entity` | FastAPI default validation error |
| Telegram API error (planned) | `502 Bad Gateway` | `{"detail": "Upstream error: <reason>"}` |
| Auth missing/invalid (planned) | `401 Unauthorized` | `{"detail": "Authentication required"}` |
 
Telegram API errors will be caught in the service layer and translated to appropriate HTTP status codes before being returned to the client. The service is the only component that knows about Telegram — the adapter and user code see only HTTP semantics.
 
---
 
## The Adapter Pattern
 
### Why the Generated Client Doesn't Match the Interface
 
`chat_client_api.Client` defines an interface using domain types: `Message` and `Channel` are abstract classes with specific properties (`id`, `sender`, `channel_id`, `timestamp`, `text`). The OpenAPI-generated client returns raw DTOs — plain data containers shaped by the HTTP response schema, not by the `chat_client_api` contract.
 
Without the adapter, user code would have to know it's talking to a service and deal with DTOs directly. The adapter closes this gap.
 
### How It Works
 
**Library usage (HW1) — no changes required to user code:**
```python
from chat_client_api import get_client
 
client = get_client(interactive=False)
# client is telegram_client_impl.TelegramClient
# get_messages returns telegram Message objects implementing chat_client_api.Message
 
for msg in client.get_messages(channel_id="my_channel"):
    print(msg.text)
```
 
**Service usage (HW2) — same user code, different wiring:**
```python
import chat_client_adapter  # importing this rebinds chat_client_api.get_client at module level
from chat_client_api import get_client
 
client = get_client(interactive=False)
# client is now chat_client_adapter.ServiceBackedChatClient
# get_messages calls the service, maps DTOs to AdapterMessage (implements chat_client_api.Message)
 
for msg in client.get_messages(channel_id="my_channel"):
    print(msg.text)  # identical call — user code is unchanged
```
 
**The adapter's mapping logic:**
```python
class ServiceBackedChatClient(Client):
    def send_message(self, channel_id: str, text: str) -> Message:
        dto = self._service_client.send_message(channel_id=channel_id, text=text)
        # dto is a service DTO — not a chat_client_api.Message
        # AdapterMessage wraps it and satisfies the interface contract
        return AdapterMessage(
            message_id=dto.id,
            sender=dto.sender,
            channel_id=dto.channel_id,
            timestamp=dto.timestamp,
            text=dto.text,
        )
```
 
**The DI rebinding (in `chat_client_adapter/__init__.py`):**
```python
import chat_client_api
import chat_client_api.client as client_module
from chat_client_adapter.client import get_client_impl
 
client_module.get_client = get_client_impl
chat_client_api.get_client = get_client_impl
# Importing the adapter package is enough — no user-facing config change needed
```
 
> **Known limitation (noted in PR review):** This monkey-patches module attributes at import time. If `get_client` is imported before the adapter loads (e.g., `from chat_client_api import get_client` before `import chat_client_adapter`), the caller holds the old reference. A proper `register()` hook on `chat_client_api` would be more robust and is flagged as a follow-up.
 
---
 
## Testing Strategy
 
### What Was Tested and Why
 
This scaffold prioritizes **structural correctness** — verifying that the wiring, contracts, and component boundaries are right before real behavior is implemented. All tests currently run without live service or Telegram credentials.
 
### Test Types
 
| Test | Location | Type | What It Validates |
|---|---|---|---|
| `test_health_endpoint` | `chat_client_service/tests/test_app.py` | Unit | `GET /health` returns `200` with `{"status": "ok"}` |
| `test_auth_login_scaffold` | `chat_client_service/tests/test_app.py` | Unit | `GET /auth/login` returns `200` with placeholder `authorization_url` and `state` |
| `test_auth_callback_scaffold` | `chat_client_service/tests/test_app.py` | Unit | `GET /auth/callback` echoes `code` and `state` query params in a `200` response |
| `test_chat_endpoints_are_scaffold_not_implemented` | `chat_client_service/tests/test_app.py` | Unit | All 4 chat routes exist and return `501` |
| Adapter forwarding tests | `chat_client_adapter/tests/test_adapter_client.py` | Unit | Adapter methods call service client correctly and map DTOs to `chat_client_api` models |
| `test_generation_placeholder` | `chat_client_service_api_client/tests/test_generation_placeholder.py` | Scaffold/Skip | Marks generated-client wiring as a pending step; skipped until generation runs |
| DI rebinding test | `tests/integration/test_adapter_dependency_injection.py` | Integration | Importing `chat_client_adapter` correctly rebinds `chat_client_api.get_client` |
 
### Mocking Strategy
 
| What Was Mocked | Why |
|---|---|
| `ChatServiceApiClient` | Adapter unit tests mock the service client so tests don't require a running service |
| DTO responses | Mock DTOs are injected to verify adapter mapping logic in isolation |
| Real Telegram API | Not used in any tests — env-gated E2E tests are skipped unless `TELEGRAM_*` env vars are set |
| Real HTTP service | Not called in unit tests — service tests use FastAPI's `TestClient` for in-process testing |
 
### Interface Compliance
 
The adapter's compliance with `chat_client_api.Client` is enforced at two levels:
 
**Static:** `ServiceBackedChatClient` inherits directly from `chat_client_api.Client`. `mypy` type-checks the full component graph (`uv run mypy components tests`) and will fail if any method signature diverges from the interface.
 
**Runtime:** The integration test `test_adapter_dependency_injection.py` imports `chat_client_adapter`, calls `chat_client_api.get_client()`, and asserts the returned object is an instance of `chat_client_api.Client`. This confirms both the DI rebinding and the isinstance relationship hold end-to-end.
 
---
 
## Follow-ups (Final Submission Scope)
 
- Implement real OAuth 2.0/OIDC flow in `chat_client_service`
- Replace `501` chat handlers with real delegation to `telegram_client_impl`
- Generate and wire concrete OpenAPI client in `chat_client_service_api_client` via `openapi-python-client`
- Complete adapter end-to-end service calls (remove placeholder behavior)
- Deploy service publicly and document URL, env vars, secrets, and deploy pipeline
- Add final E2E test coverage for deployed service flow
- Address `assert base_url` in `get_client_impl` — replace with explicit `ValueError` (flagged in PR review)
- Consider a proper `register()` hook in `chat_client_api` to replace import-time monkey-patching