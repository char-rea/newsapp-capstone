import logging
import threading

import requests
from django.conf import settings
from django.core.mail import send_mail
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Article

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Article)
def track_approval_state(sender, instance, **kwargs):
    """
    Before saving, record whether the article was already approved in the DB.
    This prevents duplicate notifications on subsequent saves after approval.
    """
    if instance.pk:
        try:
            old = Article.objects.get(pk=instance.pk)
            instance._was_approved = old.approved
        except Article.DoesNotExist:
            instance._was_approved = False
    else:
        instance._was_approved = False


@receiver(post_save, sender=Article)
def on_article_approved(sender, instance, created, **kwargs):
    """
    After saving, if the article just transitioned to approved:
      1. Email all relevant subscribers.
      2. POST to the internal /api/approved/ endpoint.
    Both run in a background thread to avoid blocking the request.
    """
    was_approved = getattr(instance, '_was_approved', False)

    if instance.approved and not was_approved:

        if not instance.approved_at:
            Article.objects.filter(pk=instance.pk).update(approved_at=timezone.now())

        # Pass only the article PK to the thread — re-fetch inside the thread
        # to avoid accessing stale or garbage-collected DB objects
        article_pk = instance.pk

        thread = threading.Thread(
            target=_send_approval_notifications,
            args=(article_pk,),
            daemon=True
        )
        thread.start()


def _send_approval_notifications(article_pk):
    """
    Re-fetch the article fresh from the DB before sending notifications.
    This prevents 'DoesNotExist' errors when running inside a background thread.
    """
    try:
        article = Article.objects.select_related(
            'author', 'publisher'
        ).get(pk=article_pk)
    except Article.DoesNotExist:
        logger.warning("Article pk=%s no longer exists — skipping notifications.", article_pk)
        return

    _notify_subscribers_by_email(article)
    _post_to_internal_api(article)


def _notify_subscribers_by_email(article):
    """
    Collect subscriber emails from:
      - Readers subscribed to the article's author (journalist)
      - Readers subscribed to the article's publisher (if applicable)
    """
    from .models import CustomUser

    subscriber_emails = set()

    journalist_subscribers = CustomUser.objects.filter(
        subscribed_journalists=article.author,
        role='reader'
    ).values_list('email', flat=True)
    subscriber_emails.update(journalist_subscribers)

    if article.publisher:
        publisher_subscribers = CustomUser.objects.filter(
            subscribed_publishers=article.publisher,
            role='reader'
        ).values_list('email', flat=True)
        subscriber_emails.update(publisher_subscribers)

    subscriber_emails = {e for e in subscriber_emails if e}

    if not subscriber_emails:
        logger.info("No subscribers to notify for: %s", article.title)
        return

    author_name    = article.author.get_full_name() or article.author.username
    publisher_name = article.publisher.name if article.publisher else "Independent"
    subject = f"New Article: {article.title}"
    message = (
        f"A new article has been published!\n\n"
        f"Title:     {article.title}\n"
        f"Author:    {author_name}\n"
        f"Publisher: {publisher_name}\n\n"
        f"{article.content[:300]}...\n\n"
        f"Visit the News App to read the full article."
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=list(subscriber_emails),
            fail_silently=False,
        )
        logger.info(
            "Emailed %d subscriber(s) about: %s",
            len(subscriber_emails), article.title
        )
    except Exception as exc:
        logger.error("Failed to send subscriber emails: %s", exc)


def _post_to_internal_api(article):
    """
    POST approved article metadata to the internal /api/approved/ endpoint.
    """
    url = f"{settings.INTERNAL_API_URL}/api/approved/"

    payload = {
        'article_id': article.pk,
        'title':      article.title,
        'author':     article.author.username,
        'publisher':  article.publisher.name if article.publisher else None,
        'approved_at': str(article.approved_at or timezone.now()),
    }
    headers = {
        'Content-Type':       'application/json',
        'X-Internal-Api-Key': settings.INTERNAL_API_KEY,
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        response.raise_for_status()
        logger.info("Logged approved article to internal API: %s", article.title)
    except requests.exceptions.RequestException as exc:
        logger.error("Failed to POST to internal API: %s", exc)