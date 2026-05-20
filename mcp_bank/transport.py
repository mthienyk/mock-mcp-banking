from mcp.server.sse import SseServerTransport

# Clients open GET /sse, then POST JSON-RPC payloads to /messages/?session_id=...
sse_transport = SseServerTransport("/messages/")
