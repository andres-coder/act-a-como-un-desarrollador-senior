from django.http import HttpResponseForbidden


class SuperuserAdminMiddleware:
    """Reserve Django's global administration site for system superusers."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.path_info.startswith('/admin/')
            and request.user.is_authenticated
            and not request.user.is_superuser
        ):
            return HttpResponseForbidden('El panel del sistema es exclusivo del superadministrador.')
        return self.get_response(request)
