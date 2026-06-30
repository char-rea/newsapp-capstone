from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import ArticleForm, NewsletterForm, RegisterForm, PublisherForm
from .models import Article, CustomUser, Newsletter, Publisher


# ── Helper ─────────────────────────────────────────────────────────────────────

def _assign_to_group(user):
    """Assign a newly created user to their role's permission group."""
    from django.contrib.auth.models import Group

    role_group_map = {
        'reader':     'Reader',
        'editor':     'Editor',
        'journalist': 'Journalist',
    }
    group_name = role_group_map.get(user.role)
    if group_name:
        try:
            user.groups.add(Group.objects.get(name=group_name))
        except Group.DoesNotExist:
            pass


# ── Auth Views ─────────────────────────────────────────────────────────────────

def register_view(request):
    """Register a new user and log them in immediately."""
    if request.user.is_authenticated:
        return redirect('home')

    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        _assign_to_group(user)
        login(request, user)
        messages.success(request, f"Welcome, {user.username}!")
        return redirect('home')

    return render(request, 'news/register.html', {'form': form})


def login_view(request):
    """Authenticate and log in a user."""
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not username or not password:
            messages.error(request, "Both fields are required.")
        else:
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                return redirect(request.GET.get('next', 'home'))
            messages.error(request, "Invalid username or password.")

    return render(request, 'news/login.html')


def logout_view(request):
    """Log out the current user."""
    logout(request)
    return redirect('login')


# ── Public Views ───────────────────────────────────────────────────────────────

def home_view(request):
    """Home page: recent approved articles and publisher highlights."""
    articles   = Article.objects.filter(approved=True).select_related('author', 'publisher')[:6]
    publishers = Publisher.objects.all()[:4]
    return render(request, 'news/home.html', {'articles': articles, 'publishers': publishers})


def article_list_view(request):
    """Browse all approved articles with optional search."""
    query    = request.GET.get('q', '').strip()
    articles = Article.objects.filter(approved=True).select_related('author', 'publisher')

    if query:
        articles = articles.filter(
            Q(title__icontains=query) | Q(content__icontains=query)
        )

    return render(request, 'news/article_list.html', {'articles': articles, 'query': query})


def article_detail_view(request, pk):
    """View a single approved article."""
    article = get_object_or_404(Article, pk=pk, approved=True)
    return render(request, 'news/article_detail.html', {'article': article})


def newsletter_list_view(request):
    """View all newsletters."""
    newsletters = Newsletter.objects.all().select_related('author')
    return render(request, 'news/newsletter_list.html', {'newsletters': newsletters})


def newsletter_detail_view(request, pk):
    """View a single newsletter."""
    newsletter = get_object_or_404(Newsletter, pk=pk)
    return render(request, 'news/newsletter_detail.html', {'newsletter': newsletter})


# ── Journalist Views ───────────────────────────────────────────────────────────

@login_required
def article_create_view(request):
    """Create a new article (journalists only)."""
    if not request.user.is_journalist:
        messages.error(request, "Only journalists can create articles.")
        return redirect('home')

    form = ArticleForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        article        = form.save(commit=False)
        article.author = request.user
        article.save()
        messages.success(request, "Article submitted for editor review.")
        return redirect('article_list')

    return render(request, 'news/article_form.html', {'form': form, 'action': 'Create'})


@login_required
def article_edit_view(request, pk):
    """Edit an article — journalists (own only) or editors (any)."""
    article = get_object_or_404(Article, pk=pk)

    if not (request.user.is_editor or
            (request.user.is_journalist and article.author == request.user)):
        messages.error(request, "You don't have permission to edit this article.")
        return redirect('article_list')

    form = ArticleForm(request.POST or None, instance=article)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Article updated.")
        return redirect('article_detail', pk=pk)

    return render(request, 'news/article_form.html', {'form': form, 'action': 'Edit', 'article': article})


@login_required
def article_delete_view(request, pk):
    """Delete an article — journalists (own) or editors (any)."""
    article = get_object_or_404(Article, pk=pk)

    if not (request.user.is_editor or
            (request.user.is_journalist and article.author == request.user)):
        messages.error(request, "You don't have permission to delete this article.")
        return redirect('article_list')

    if request.method == 'POST':
        article.delete()
        messages.success(request, "Article deleted.")
        return redirect('article_list')

    return render(request, 'news/article_confirm_delete.html', {'article': article})


@login_required
@login_required
def newsletter_create_view(request):
    """Create a newsletter (journalists/editors only)."""
    if not (request.user.is_journalist or request.user.is_editor):
        messages.error(request, "Only journalists and editors can create newsletters.")
        return redirect('newsletter_list')

    approved_articles = Article.objects.filter(approved=True).select_related('author')
    has_articles      = approved_articles.exists()

    if request.method == 'POST' and has_articles:
        title       = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        article_ids = request.POST.getlist('articles')

        if not title:
            messages.error(request, "Title is required.")
        else:
            newsletter        = Newsletter.objects.create(
                title=title,
                description=description,
                author=request.user
            )
            if article_ids:
                newsletter.articles.set(
                    Article.objects.filter(pk__in=article_ids, approved=True)
                )
            messages.success(request, "Newsletter created successfully.")
            return redirect('newsletter_detail', pk=newsletter.pk)

    form = NewsletterForm()
    return render(request, 'news/newsletter_form.html', {
        'form':              form,
        'action':            'Create',
        'approved_articles': approved_articles,
        'has_articles':      has_articles,
        'selected_articles': [],
    })


# ── Editor Views ───────────────────────────────────────────────────────────────

@login_required
def editor_dashboard_view(request):
    """Editor dashboard: pending articles awaiting approval."""
    if not request.user.is_editor:
        messages.error(request, "Access denied.")
        return redirect('home')

    pending  = Article.objects.filter(approved=False).select_related('author', 'publisher')
    approved = Article.objects.filter(approved=True).select_related('author', 'publisher')[:10]

    return render(request, 'news/editor_dashboard.html', {
        'pending_articles':  pending,
        'approved_articles': approved,
    })


@login_required
def approve_article_view(request, pk):
    """Approve or reject a pending article (editors only)."""
    if not request.user.is_editor:
        messages.error(request, "Only editors can approve articles.")
        return redirect('home')

    article = get_object_or_404(Article, pk=pk)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'approve':
            article.approved    = True
            article.approved_by = request.user
            article.approved_at = timezone.now()
            article.save()
            messages.success(
                request, f'"{article.title}" approved — subscribers notified.'
            )
        elif action == 'reject':
            article.delete()
            messages.warning(request, "Article rejected and removed.")

        return redirect('editor_dashboard')

    # Pass publishers so the edit form can offer publisher assignment
    publishers = Publisher.objects.all()
    return render(request, 'news/article_approve.html', {
        'article':    article,
        'publishers': publishers,
    })


# ── Profile & Subs ────────────────────────────────────────────────────

@login_required
@login_required
def profile_view(request):
    """
    User profile page.
    - Readers can manage their subscriptions.
    - Journalists can see all their articles (approved and pending)
      and edit or delete pending ones.
    """
    publishers  = Publisher.objects.all()
    journalists = CustomUser.objects.filter(role='journalist')

    if request.method == 'POST' and request.user.is_reader:
        publisher_ids  = request.POST.getlist('publishers')
        journalist_ids = request.POST.getlist('journalists')
        request.user.subscribed_publishers.set(publisher_ids)
        request.user.subscribed_journalists.set(journalist_ids)
        messages.success(request, "Subscriptions updated.")
        return redirect('profile')

    # Split journalist articles into approved and pending
    approved_articles = []
    pending_articles  = []
    if request.user.is_journalist:
        approved_articles = Article.objects.filter(
            author=request.user, approved=True
        ).order_by('-created_at')
        pending_articles = Article.objects.filter(
            author=request.user, approved=False
        ).order_by('-created_at')

    return render(request, 'news/profile.html', {
        'publishers':       publishers,
        'journalists':      journalists,
        'approved_articles': approved_articles,
        'pending_articles':  pending_articles,
    })

# ── Publisher ────────────────────────────────────────────────────

def publisher_list_view(request):
    """Public list of all publishers."""
    publishers = Publisher.objects.prefetch_related('editors', 'journalists', 'articles').all()
    return render(request, 'news/publisher_list.html', {'publishers': publishers})


@login_required
def publisher_create_view(request):
    """Create a new publisher (editors only)."""
    if not request.user.is_editor:
        messages.error(request, "Only editors can create publishers.")
        return redirect('publisher_list')

    form = PublisherForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, "Publisher created successfully.")
        return redirect('publisher_list')

    return render(request, 'news/publisher_form.html', {'form': form, 'action': 'Create'})


@login_required
def publisher_edit_view(request, pk):
    """Edit a publisher and reassign editors/journalists (editors only)."""
    if not request.user.is_editor:
        messages.error(request, "Only editors can edit publishers.")
        return redirect('publisher_list')

    publisher = get_object_or_404(Publisher, pk=pk)
    form      = PublisherForm(request.POST or None, instance=publisher)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f'"{publisher.name}" updated.')
        return redirect('publisher_list')

    return render(request, 'news/publisher_form.html', {
        'form':      form,
        'action':    'Edit',
        'publisher': publisher,
    })