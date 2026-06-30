"""
urls.py

URL routing configuration for the News application.
"""

from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import api_views, views

urlpatterns = [

    # ── Web ──────────────────────────────────────────────────────────────
    path('',                                views.home_view,              name='home'),
    path('articles/',                       views.article_list_view,      name='article_list'),
    path('articles/create/',                views.article_create_view,    name='article_create'),
    path('articles/<int:pk>/',              views.article_detail_view,    name='article_detail'),
    path('articles/<int:pk>/edit/',         views.article_edit_view,      name='article_edit'),
    path('articles/<int:pk>/delete/',       views.article_delete_view,    name='article_delete'),
    path('editor/',                         views.editor_dashboard_view,  name='editor_dashboard'),
    path('editor/approve/<int:pk>/',        views.approve_article_view,   name='approve_article'),
    path('newsletters/',                    views.newsletter_list_view,   name='newsletter_list'),
    path('newsletters/create/',             views.newsletter_create_view, name='newsletter_create'),
    path('newsletters/<int:pk>/',           views.newsletter_detail_view, name='newsletter_detail'),
    path('login/',                          views.login_view,             name='login'),
    path('logout/',                         views.logout_view,            name='logout'),
    path('register/',                       views.register_view,          name='register'),
    path('profile/',                        views.profile_view,           name='profile'),

# ── API Auth ─────────────────────────────────────────────────────
    path('api/token/',                      TokenObtainPairView.as_view(),  name='token_obtain_pair'),
    path('api/token/refresh/',              TokenRefreshView.as_view(),     name='token_refresh'),

    # ── REST API: Articles ─────────────────────────────────────────────────────
    path('api/articles/',                   api_views.ArticleListCreateAPIView.as_view(),            name='api_article_list'),
    path('api/articles/subscribed/',        api_views.SubscribedArticlesAPIView.as_view(),           name='api_subscribed_articles'),
    path('api/articles/<int:pk>/',          api_views.ArticleRetrieveUpdateDestroyAPIView.as_view(), name='api_article_detail'),
    path('api/articles/<int:pk>/approve/',  api_views.ArticleApproveAPIView.as_view(),               name='api_article_approve'),

    # ── REST API: Log ───────────────────────────────────────
    path('api/approved/',                   api_views.ApprovedArticleLogAPIView.as_view(),           name='api_approved_log'),

    # ── REST API: Newsletters ──────────────────────────────────────────────────
    path('api/newsletters/',                api_views.NewsletterListCreateAPIView.as_view(),             name='api_newsletter_list'),
    path('api/newsletters/<int:pk>/',       api_views.NewsletterRetrieveUpdateDestroyAPIView.as_view(),  name='api_newsletter_detail'),

    # ── Publishers ─────────────────────────────────────────────────────────────────
    path('publishers/',                views.publisher_list_view,   name='publisher_list'),
    path('publishers/create/',         views.publisher_create_view, name='publisher_create'),
    path('publishers/<int:pk>/edit/',  views.publisher_edit_view,   name='publisher_edit'),
]
