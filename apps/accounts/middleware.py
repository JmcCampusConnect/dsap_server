from apps.audit.models import AuditLog


class ImpersonationAuditMiddleware:
    """
    Middleware that automatically records an 'IMPERSONATED_REQUEST' audit log
    for every mutating HTTP request (POST, PUT, PATCH, DELETE) made under an
    impersonation session.

    This guarantees end-to-end traceability for every state-changing operation,
    capturing both the target user context (request.user) and the real administrator
    (via token claims / AuditLog impersonator fields).
    """

    MUTATING_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}
    EXCLUDED_PATHS = {
        '/api/auth/impersonate/',
        '/api/auth/impersonate/exit/',
    }

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if (
            request.method in self.MUTATING_METHODS
            and request.path not in self.EXCLUDED_PATHS
        ):
            token = getattr(request, 'auth', None)
            payload = getattr(token, 'payload', {}) if token else {}
            if payload.get('is_impersonation'):
                try:
                    AuditLog.log(
                        request=request,
                        action='IMPERSONATED_REQUEST',
                        object_repr=f"Impersonated {request.method} {request.path}",
                        changes={
                            'method': request.method,
                            'path': request.path,
                            'status_code': response.status_code,
                            'session_id': payload.get('impersonation_session_id'),
                        },
                    )
                except Exception:
                    # Logging failure must never crash the user's request
                    pass

        return response
