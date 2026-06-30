from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import Article, CustomUser, Newsletter, Publisher


class RegisterForm(UserCreationForm):
    """Registration form with role selection and unique email validation."""
    email = forms.EmailField(required=True)

    class Meta:
        model  = CustomUser
        fields = ['username', 'email', 'first_name', 'last_name', 'role', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})

    def clean_email(self):
        """Reject registration if the email address is already in use."""
        email = self.cleaned_data.get('email', '').strip().lower()
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "An account with this email address already exists. "
                "Please use a different email or log in."
            )
        return email


class ArticleForm(forms.ModelForm):
    """Form for journalists to create or edit articles."""

    class Meta:
        model  = Article
        fields = ['title', 'content', 'publisher']
        widgets = {
            'title':     forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Article title'}),
            'content':   forms.Textarea(attrs={'class': 'form-control', 'rows': 12}),
            'publisher': forms.Select(attrs={'class': 'form-control'}),
        }


class NewsletterForm(forms.ModelForm):
    """Form for creating or editing newsletters."""

    class Meta:
        model  = Newsletter
        fields = ['title', 'description', 'articles']
        widgets = {
            'title':       forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'articles':    forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only allow approved articles in newsletters
        self.fields['articles'].queryset = Article.objects.filter(approved=True)


class PublisherForm(forms.ModelForm):
    """Form for editors to create or edit publishers and assign staff."""

    class Meta:
        model  = Publisher
        fields = ['name', 'description', 'editors', 'journalists']
        widgets = {
            'name':        forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Publisher name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'editors':     forms.CheckboxSelectMultiple(),
            'journalists': forms.CheckboxSelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show users with the correct roles in each field
        self.fields['editors'].queryset     = CustomUser.objects.filter(role='editor')
        self.fields['journalists'].queryset = CustomUser.objects.filter(role='journalist')
        self.fields['editors'].required     = False
        self.fields['journalists'].required = False