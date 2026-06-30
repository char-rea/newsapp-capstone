"""
Unit tests for the NewsApp REST API.
Covers: role-based access, subscriptions, article CRUD,
editor approval, newsletters, and signal logic (with mocking).
"""
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Article, ApprovedArticleLog, CustomUser, Newsletter, Publisher


# ── Shared Helpers ─────────────────────────────────────────────────────────────

def make_user(username, role, password='StrongPass!99'):
    """Create and return a test user with the given role."""
    return CustomUser.objects.create_user(
        username=username,
        email=f'{username}@test.com',
        password=password,
        role=role,
    )


def jwt_token(user):
    """Return a JWT access token string for a user."""
    return str(RefreshToken.for_user(user).access_token)


def setup_groups():
    """Ensure the three role groups exist in the test database."""
    for name in ('Reader', 'Editor', 'Journalist'):
        Group.objects.get_or_create(name=name)


# ── 1. Authenticated Access Per Role ──────────────────────────────────────────

@patch('news.signals._send_approval_notifications')
class AuthenticationTests(APITestCase):
    """
    Verify unauthenticated requests are blocked and each role
    can access the articles endpoint correctly.
    The patch stops real email/HTTP calls firing as a side effect.
    """

    def setUp(self):
        setup_groups()
        self.journalist = make_user('j1', 'journalist')
        self.reader     = make_user('r1', 'reader')
        self.client     = APIClient()

        self.article = Article.objects.create(
            title='Published', content='Body.', author=self.journalist, approved=True
        )

    def auth(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {jwt_token(user)}')

    def test_unauthenticated_request_is_blocked(self, mock_notify):
        """No token → 401 Unauthorized."""
        response = self.client.get(reverse('api_article_list'))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_reader_can_access_articles(self, mock_notify):
        """Valid reader token → 200 OK."""
        self.auth(self.reader)
        response = self.client.get(reverse('api_article_list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_authenticated_journalist_can_access_articles(self, mock_notify):
        """Valid journalist token → 200 OK."""
        self.auth(self.journalist)
        response = self.client.get(reverse('api_article_list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)


# ── 2. Reader Subscribed Content ──────────────────────────────────────────────

@patch('news.signals._send_approval_notifications')
class SubscribedArticlesTests(APITestCase):
    """
    The API should return only articles from a reader's
    subscribed publishers and journalists.
    """

    def setUp(self):
        setup_groups()
        self.journalist_subscribed   = make_user('j1', 'journalist')
        self.journalist_unsubscribed = make_user('j2', 'journalist')
        self.reader = make_user('r1', 'reader')
        self.pub    = Publisher.objects.create(name='Tech Weekly')

        self.subscribed_article = Article.objects.create(
            title='Subscribed Article', content='Body.',
            author=self.journalist_subscribed, approved=True
        )
        self.unsubscribed_article = Article.objects.create(
            title='Unsubscribed Article', content='Body.',
            author=self.journalist_unsubscribed, approved=True
        )
        self.publisher_article = Article.objects.create(
            title='Publisher Article', content='Body.',
            author=self.journalist_unsubscribed,
            publisher=self.pub, approved=True
        )

        self.reader.subscribed_journalists.add(self.journalist_subscribed)
        self.reader.subscribed_publishers.add(self.pub)

        self.client = APIClient()

    def auth(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {jwt_token(user)}')

    def test_reader_sees_subscribed_journalist_article(self, mock_notify):
        """Reader receives articles from journalists they follow."""
        self.auth(self.reader)
        response = self.client.get(reverse('api_subscribed_articles'))
        titles = [a['title'] for a in response.data]
        self.assertIn('Subscribed Article', titles)

    def test_reader_sees_subscribed_publisher_article(self, mock_notify):
        """Reader receives articles from publishers they follow."""
        self.auth(self.reader)
        response = self.client.get(reverse('api_subscribed_articles'))
        titles = [a['title'] for a in response.data]
        self.assertIn('Publisher Article', titles)

    def test_reader_does_not_see_unsubscribed_article(self, mock_notify):
        """Reader does NOT receive articles from sources they don't follow."""
        self.auth(self.reader)
        response = self.client.get(reverse('api_subscribed_articles'))
        titles = [a['title'] for a in response.data]
        self.assertNotIn('Unsubscribed Article', titles)


# ── 3. Journalist Can Create Articles ─────────────────────────────────────────

@patch('news.signals._send_approval_notifications')
class JournalistArticleTests(APITestCase):
    """Journalists can create articles; readers cannot."""

    def setUp(self):
        setup_groups()
        self.journalist = make_user('j1', 'journalist')
        self.reader     = make_user('r1', 'reader')
        self.client     = APIClient()

    def auth(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {jwt_token(user)}')

    def test_journalist_can_create_article(self, mock_notify):
        """Success: journalist POSTs a new article → 201 Created."""
        self.auth(self.journalist)
        response = self.client.post(
            reverse('api_article_list'),
            {'title': 'My Story', 'content': 'Article body.'}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'My Story')

    def test_reader_cannot_create_article(self, mock_notify):
        """Failure: reader tries to POST an article → 403 Forbidden."""
        self.auth(self.reader)
        response = self.client.post(
            reverse('api_article_list'),
            {'title': 'Attempted', 'content': 'Not allowed.'}
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ── 4. Editor Can Approve and Delete ──────────────────────────────────────────

@patch('news.signals._send_approval_notifications')
class EditorPermissionTests(APITestCase):
    """Editors can approve pending articles and delete any article."""

    def setUp(self):
        setup_groups()
        self.journalist = make_user('j1', 'journalist')
        self.editor     = make_user('e1', 'editor')
        self.reader     = make_user('r1', 'reader')
        self.client     = APIClient()

        self.pending_article = Article.objects.create(
            title='Pending', content='Body.', author=self.journalist, approved=False
        )
        self.approved_article = Article.objects.create(
            title='Live Article', content='Body.', author=self.journalist, approved=True
        )

    def auth(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {jwt_token(user)}')

    def test_editor_can_approve_article(self, mock_notify):
        """Success: editor approves a pending article → 200 OK, approved=True."""
        self.auth(self.editor)
        response = self.client.post(
            reverse('api_article_approve', kwargs={'pk': self.pending_article.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending_article.refresh_from_db()
        self.assertTrue(self.pending_article.approved)

    def test_reader_cannot_approve_article(self, mock_notify):
        """Failure: reader tries to approve → 403 Forbidden."""
        self.auth(self.reader)
        response = self.client.post(
            reverse('api_article_approve', kwargs={'pk': self.pending_article.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_editor_can_delete_article(self, mock_notify):
        """Success: editor deletes an article → 204 No Content."""
        self.auth(self.editor)
        response = self.client.delete(
            reverse('api_article_detail', kwargs={'pk': self.approved_article.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

    def test_reader_cannot_delete_article(self, mock_notify):
        """Failure: reader tries to delete → 403 Forbidden."""
        self.auth(self.reader)
        response = self.client.delete(
            reverse('api_article_detail', kwargs={'pk': self.approved_article.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ── 5. Newsletters Behave Correctly ───────────────────────────────────────────

@patch('news.signals._send_approval_notifications')
class NewsletterTests(APITestCase):
    """
    Readers can view newsletters.
    Journalists can create newsletters.
    Readers cannot create newsletters.
    """

    def setUp(self):
        setup_groups()
        self.journalist = make_user('j1', 'journalist')
        self.reader     = make_user('r1', 'reader')
        self.client     = APIClient()

        self.article = Article.objects.create(
            title='Article 1', content='Body.', author=self.journalist, approved=True
        )
        self.newsletter = Newsletter.objects.create(
            title='Weekly Digest', description='Top stories.', author=self.journalist
        )
        self.newsletter.articles.add(self.article)

    def auth(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {jwt_token(user)}')

    def test_reader_can_view_newsletters(self, mock_notify):
        """Success: reader retrieves newsletter list → 200 OK."""
        self.auth(self.reader)
        response = self.client.get(reverse('api_newsletter_list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_journalist_can_create_newsletter(self, mock_notify):
        """Success: journalist creates a newsletter → 201 Created."""
        self.auth(self.journalist)
        data = {
            'title': 'New Edition',
            'description': 'Desc.',
            'article_ids': [self.article.pk]
        }
        response = self.client.post(reverse('api_newsletter_list'), data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_reader_cannot_create_newsletter(self, mock_notify):
        """Failure: reader tries to create a newsletter → 403 Forbidden."""
        self.auth(self.reader)
        data = {'title': 'Sneaky NL', 'description': 'Nope.'}
        response = self.client.post(reverse('api_newsletter_list'), data, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


# ── 6. Signal Logic with Mocking ──────────────────────────────────────────────

class SignalLogicTests(TestCase):
    """
    Tests that approval triggers the correct side effects.
    Uses mocking so no real emails or HTTP calls are made.
    These tests call the signal helper functions directly.
    """

    def setUp(self):
        self.journalist = make_user('j1', 'journalist')
        self.reader     = make_user('r1', 'reader')

        self.article = Article.objects.create(
            title='Signal Test', content='Body.',
            author=self.journalist, approved=False
        )
        # Reader follows the journalist
        self.reader.subscribed_journalists.add(self.journalist)

    @patch('news.signals.send_mail')
    def test_email_sent_to_subscriber_on_approval(self, mock_send_mail):
        """
        Success: when an article is approved, an email is sent to
        the subscribed reader.
        """
        from news.signals import _notify_subscribers_by_email

        _notify_subscribers_by_email(self.article)

        mock_send_mail.assert_called_once()
        _, kwargs = mock_send_mail.call_args
        self.assertIn(self.reader.email, kwargs['recipient_list'])

    @patch('news.signals.requests.post')
    def test_internal_api_called_on_approval(self, mock_post):
        """
        Success: approval triggers a POST to /api/approved/
        with the correct article data.
        """
        from news.signals import _post_to_internal_api

        mock_post.return_value = MagicMock(raise_for_status=lambda: None)

        _post_to_internal_api(self.article)

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        self.assertEqual(call_kwargs['json']['article_id'], self.article.pk)

    @patch('news.signals.requests.post')
    def test_internal_api_failure_does_not_crash_app(self, mock_post):
        """
        Failure: if the internal API is unreachable, the app should
        log the error gracefully rather than raising an exception.
        """
        import requests as req
        from news.signals import _post_to_internal_api

        mock_post.side_effect = req.exceptions.ConnectionError("refused")

        try:
            _post_to_internal_api(self.article)
        except Exception:
            self.fail("Signal crashed the app on a failed API connection.")