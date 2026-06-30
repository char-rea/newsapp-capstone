from django.conf import settings
from django.db.models import Q
from django.utils import timezone
from rest_framework import generics, status, views
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Article, ApprovedArticleLog, Newsletter
from .permissions import IsEditor, IsJournalist, IsJournalistOrEditor
from .serializers import (
    ArticleSerializer,
    ApprovedArticleLogSerializer,
    NewsletterSerializer,
)


# ── Articles ───────────────────────────────────────────────────────────────────

class ArticleListCreateAPIView(generics.ListCreateAPIView):
    """
    GET  /api/articles/ — All approved articles (any authenticated user).
    POST /api/articles/ — Create article (journalists only).
    """
    serializer_class = ArticleSerializer

    def get_queryset(self):
        return Article.objects.filter(approved=True).select_related('author', 'publisher')

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsJournalist()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class ArticleRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/articles/<id>/ — Retrieve a single article.
    PUT    /api/articles/<id>/ — Update (journalists own; editors any).
    DELETE /api/articles/<id>/ — Delete (editors only).
    """
    serializer_class = ArticleSerializer

    def get_queryset(self):
        """Restrict unapproved articles to editors and the owning journalist."""
        user = self.request.user
        if user.role == 'editor':
            return Article.objects.all()
        if user.role == 'journalist':
            return Article.objects.filter(Q(approved=True) | Q(author=user))
        return Article.objects.filter(approved=True)

    def get_permissions(self):
        if self.request.method == 'DELETE':
            return [IsEditor()]
        if self.request.method in ('PUT', 'PATCH'):
            return [IsJournalistOrEditor()]
        return [IsAuthenticated()]

    def update(self, request, *args, **kwargs):
        """Journalists can only edit their own articles."""
        article = self.get_object()
        if request.user.is_journalist and article.author != request.user:
            return Response(
                {'error': 'You can only edit your own articles.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)


class SubscribedArticlesAPIView(generics.ListAPIView):
    """GET /api/articles/subscribed/ — Articles from the reader's subscriptions."""
    serializer_class   = ArticleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user

        # Only readers have subscriptions — return empty for other roles
        if not user.is_reader:
            return Article.objects.none()

        # Articles from subscribed publishers
        from_publishers = Article.objects.filter(
            approved=True,
            publisher__in=user.subscribed_publishers.all()
        )
        # Articles from subscribed journalists
        from_journalists = Article.objects.filter(
            approved=True,
            author__in=user.subscribed_journalists.all()
        )

        return (from_publishers | from_journalists).distinct()


class ArticleApproveAPIView(views.APIView):
    """POST /api/articles/<id>/approve/ — Approve an article (editors only)."""
    permission_classes = [IsEditor]

    def post(self, request, pk):
        try:
            article = Article.objects.get(pk=pk)
        except Article.DoesNotExist:
            return Response(
                {'error': 'Article not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        if article.approved:
            return Response(
                {'message': 'Article is already approved.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Approve — triggers pre_save/post_save signals
        article.approved    = True
        article.approved_by = request.user
        article.approved_at = timezone.now()
        article.save()

        return Response(
            {'message': f'"{article.title}" approved. Subscribers will be notified.'},
            status=status.HTTP_200_OK
        )


# ── Log ──────────────────────────────────────────────────────

class ApprovedArticleLogAPIView(views.APIView):
    """
    POST /api/approved/ — Internal endpoint called by signals after article approval.
    Authenticated via a shared API key header, not JWT.
    """
    # Bypass JWT auth — this is an internal server-to-server call
    authentication_classes = []
    permission_classes     = []

    def post(self, request):
        # Validate the internal API key from the request header
        api_key = request.headers.get('X-Internal-Api-Key', '')
        if api_key != settings.INTERNAL_API_KEY:
            return Response(
                {'error': 'Unauthorized.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        article_id = request.data.get('article_id')
        if not article_id:
            return Response(
                {'error': 'article_id is required.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            article = Article.objects.get(pk=article_id)
        except Article.DoesNotExist:
            return Response(
                {'error': 'Article not found.'},
                status=status.HTTP_404_NOT_FOUND
            )

        log = ApprovedArticleLog.objects.create(article=article, payload=request.data)
        serializer = ApprovedArticleLogSerializer(log)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


# ── Newsletters ────────────────────────────────────────────────────────────────

class NewsletterListCreateAPIView(generics.ListCreateAPIView):
    """
    GET  /api/newsletters/ — All newsletters (any authenticated user).
    POST /api/newsletters/ — Create newsletter (journalists/editors only).
    """
    serializer_class = NewsletterSerializer

    def get_queryset(self):
        return Newsletter.objects.all().select_related('author').prefetch_related('articles')

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsJournalistOrEditor()]
        return [IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class NewsletterRetrieveUpdateDestroyAPIView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/newsletters/<id>/ — Retrieve a newsletter.
    PUT    /api/newsletters/<id>/ — Update (journalists/editors).
    DELETE /api/newsletters/<id>/ — Delete (journalists/editors).
    """
    serializer_class = NewsletterSerializer
    queryset         = Newsletter.objects.all()

    def get_permissions(self):
        if self.request.method in ('PUT', 'PATCH', 'DELETE'):
            return [IsJournalistOrEditor()]
        return [IsAuthenticated()]