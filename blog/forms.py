from django import forms
from .models import BlogPost, BlogComment


class BlogPostForm(forms.ModelForm):
    """
    Form for creating and updating blog posts
    """
    class Meta:
        model = BlogPost
        fields = [
            'title',
            'content',
            'category',
            'featured_image',
            'status',
            'meta_description',
            'tags'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control'}),
            'meta_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class BlogCommentForm(forms.ModelForm):
    """
    Form for submitting blog comments
    """
    class Meta:
        model = BlogComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Write your comment here...'
            })
        }