from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils import timezone
from .models import CustomUser, Publisher, Article, Newsletter, ApprovedArticleLog


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display  = ['username', 'email', 'role', 'is_staff', 'is_active']
    list_filter   = ['role', 'is_staff']
    search_fields = ['username', 'email']

    fieldsets = UserAdmin.fieldsets + (
        ('Role & Subscriptions', {
            'fields': ('role', 'subscribed_publishers', 'subscribed_journalists')
        }),
    )
    filter_horizontal = [
        'subscribed_publishers', 'subscribed_journalists',
        'groups', 'user_permissions'
    ]


@admin.register(Publisher)
class PublisherAdmin(admin.ModelAdmin):
    list_display   = ['name', 'created_at']
    search_fields  = ['name']
    filter_horizontal = ['editors', 'journalists']


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display  = ['title', 'author', 'publisher', 'approved', 'created_at']
    list_filter   = ['approved', 'publisher']
    search_fields = ['title', 'content']
    actions       = ['bulk_approve']

    def bulk_approve(self, request, queryset):
        """Approve all selected articles via the admin."""
        for article in queryset.filter(approved=False):
            article.approved    = True
            article.approved_by = request.user
            article.approved_at = timezone.now()
            article.save()  # Triggers signals
        self.message_user(request, f"{queryset.count()} article(s) approved.")

    bulk_approve.short_description = "Approve selected articles"


@admin.register(Newsletter)
class NewsletterAdmin(admin.ModelAdmin):
    list_display      = ['title', 'author', 'created_at']
    search_fields     = ['title']
    filter_horizontal = ['articles']


@admin.register(ApprovedArticleLog)
class ApprovedArticleLogAdmin(admin.ModelAdmin):
    list_display  = ['article', 'logged_at']
    readonly_fields = ['article', 'logged_at', 'payload']