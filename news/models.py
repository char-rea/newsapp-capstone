from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings


class CustomUser(AbstractUser):
    """
    Extended user model with role-based access.
    Roles: reader, editor, journalist.
    Reader fields store subscriptions; journalist fields use reverse FKs.
    """

    ROLE_CHOICES = [
        ('reader',     'Reader'),
        ('editor',     'Editor'),
        ('journalist', 'Journalist'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='reader')

    # ── Reader-only fields ─────────────────────────────────────────────────────
    # Set to None/empty for non-readers automatically in save()
    subscribed_publishers = models.ManyToManyField(
        'Publisher',
        related_name='subscribers',
        blank=True,
        help_text="Publishers this reader subscribes to."
    )
    subscribed_journalists = models.ManyToManyField(
        'self',
        related_name='followers',
        blank=True,
        symmetrical=False,
        help_text="Journalists this reader subscribes to."
    )

    def save(self, *args, **kwargs):
        """Clear subscription fields for non-reader roles after save."""
        super().save(*args, **kwargs)
        if self.role != 'reader':
            self.subscribed_publishers.clear()
            self.subscribed_journalists.clear()

    # ── Convenience properties ─────────────────────────────────────────────────
    @property
    def is_reader(self):
        return self.role == 'reader'

    @property
    def is_editor(self):
        return self.role == 'editor'

    @property
    def is_journalist(self):
        return self.role == 'journalist'

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


class Publisher(models.Model):
    """
    A publication that groups multiple journalists under editor oversight.
    Journalists and editors are tracked via ManyToMany.
    """

    name        = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    # Staff members of this publisher
    editors = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='editing_publishers',
        blank=True,
        limit_choices_to={'role': 'editor'}
    )
    journalists = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='writing_publishers',
        blank=True,
        limit_choices_to={'role': 'journalist'}
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Article(models.Model):
    """
    A news article authored by a journalist.
    Can be independent (no publisher) or published under a Publisher.
    Approval is managed by editors and triggers email/API notifications.
    """

    title      = models.CharField(max_length=500)
    content    = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved   = models.BooleanField(default=False)

    # Author must be a journalist (enforced in forms/serializers)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='authored_articles',
        limit_choices_to={'role': 'journalist'}
    )

    # Optional publisher link (None = independent article)
    publisher = models.ForeignKey(
        Publisher,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='articles',
        help_text="Leave blank for independent articles."
    )

    # Approval tracking
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_articles'
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class Newsletter(models.Model):
    """
    A curated collection of approved articles.
    Created and managed by journalists or editors.
    Viewable by all authenticated users.
    """

    title       = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='authored_newsletters'
    )
    articles = models.ManyToManyField(
        Article,
        related_name='newsletters',
        blank=True
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class ApprovedArticleLog(models.Model):
    """
    Internal log created when an article is approved and POSTed
    to /api/approved/. Simulates external distribution.
    """

    article    = models.ForeignKey(Article, on_delete=models.CASCADE, related_name='approval_logs')
    logged_at  = models.DateTimeField(auto_now_add=True)
    payload    = models.JSONField()

    class Meta:
        ordering = ['-logged_at']

    def __str__(self):
        return f"Log: {self.article.title} @ {self.logged_at:%Y-%m-%d %H:%M}"