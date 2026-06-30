from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Article, ApprovedArticleLog, Newsletter, Publisher

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = ['id', 'username', 'email', 'role', 'first_name', 'last_name']
        read_only_fields = ['id']


class PublisherSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Publisher
        fields = ['id', 'name', 'description', 'created_at']
        read_only_fields = ['id', 'created_at']


class ArticleSerializer(serializers.ModelSerializer):
    author     = UserSerializer(read_only=True)
    publisher  = PublisherSerializer(read_only=True)

    # Write-only field so clients can assign a publisher by ID
    publisher_id = serializers.PrimaryKeyRelatedField(
        queryset=Publisher.objects.all(),
        source='publisher',
        write_only=True,
        required=False,
        allow_null=True
    )

    class Meta:
        model  = Article
        fields = [
            'id', 'title', 'content', 'author',
            'publisher', 'publisher_id',
            'created_at', 'updated_at',
            'approved', 'approved_at', 'approved_by',
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_at',
            'approved', 'approved_at', 'approved_by', 'author',
        ]

    def validate(self, data):
        """Ensure only journalists can author articles."""
        request = self.context.get('request')
        if request and not request.user.is_journalist:
            raise serializers.ValidationError("Only journalists can create articles.")
        return data

    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)


class NewsletterSerializer(serializers.ModelSerializer):
    author   = UserSerializer(read_only=True)
    articles = ArticleSerializer(many=True, read_only=True)

    # Write-only: accept article IDs to associate with the newsletter
    article_ids = serializers.PrimaryKeyRelatedField(
        queryset=Article.objects.filter(approved=True),
        source='articles',
        many=True,
        write_only=True,
        required=False
    )

    class Meta:
        model  = Newsletter
        fields = [
            'id', 'title', 'description', 'created_at', 'updated_at',
            'author', 'articles', 'article_ids',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'author']

    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        return super().create(validated_data)


class ApprovedArticleLogSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ApprovedArticleLog
        fields = ['id', 'article', 'logged_at', 'payload']
        read_only_fields = ['id', 'logged_at']


class RegisterSerializer(serializers.ModelSerializer):
    """Handles new user registration via API."""
    password  = serializers.CharField(write_only=True, min_length=8)
    password2 = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model  = User
        fields = ['username', 'email', 'password', 'password2', 'role', 'first_name', 'last_name']

    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError("Passwords do not match.")
        return data

    def create(self, validated_data):
        validated_data.pop('password2')
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user