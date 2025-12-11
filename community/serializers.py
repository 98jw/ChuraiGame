from rest_framework import serializers
from .models import Post, Comment

# 댓글 직렬화
class CommentSerializer(serializers.ModelSerializer):
    author_name = serializers.ReadOnlyField(source='author.nickname')
    is_liked = serializers.SerializerMethodField()
    likes_count = serializers.IntegerField(source='like_users.count', read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'content', 'author_name', 'created_at', 'is_liked', 'likes_count']
        read_only_fields = ['author']

    def get_is_liked(self, obj):
        user = self.context['request'].user
        if user.is_authenticated:
            return obj.like_users.filter(pk=user.pk).exists()
        return False

# 게시글 직렬화
class PostSerializer(serializers.ModelSerializer):
    author_name = serializers.ReadOnlyField(source='author.nickname')
    comments = CommentSerializer(many=True, read_only=True) # 게시글 볼 때 댓글도 같이 봄
    comments_count = serializers.IntegerField(source='comments.count', read_only=True)
    is_liked = serializers.SerializerMethodField()
    likes_count = serializers.IntegerField(source='like_users.count', read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ['id', 'category', 'title', 'content', 'image', 'video', 'image_url', 'author_name', 'created_at', 'updated_at', 'comments', 'comments_count', 'is_liked', 'likes_count']
        read_only_fields = ['author']

    def get_is_liked(self, obj):
        user = self.context['request'].user
        if user.is_authenticated:
            return obj.like_users.filter(pk=user.pk).exists()
        return False
        
    def get_image_url(self, obj):
        if obj.image:
            return obj.image.url
        return None