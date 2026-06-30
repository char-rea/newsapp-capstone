from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsJournalist(BasePermission):
    """Allow access only to journalists."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'journalist'


class IsEditor(BasePermission):
    """Allow access only to editors."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'editor'


class IsReader(BasePermission):
    """Allow access only to readers."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'reader'


class IsJournalistOrEditor(BasePermission):
    """Allow journalists and editors (content creators)."""
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role in ('journalist', 'editor')
        )


class IsJournalistOrEditorOrReadOnly(BasePermission):
    """Read-only for readers; full access for journalists/editors."""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.role in ('journalist', 'editor')