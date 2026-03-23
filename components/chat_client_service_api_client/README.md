# Chat Client Service API Client

This component is the home for the OpenAPI-generated client code for `chat_client_service`.

## Generation (planned)

Run after the service is available:

```bash
openapi-python-client generate --url http://localhost:8000/openapi.json --output-path components/chat_client_service_api_client
```

The handwritten wrapper in `chat_client_service_api_client.client` provides a stable
surface for the adapter.
