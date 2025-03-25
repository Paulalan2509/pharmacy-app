from django import forms
from .models import ForumThread, ForumReply

class ThreadForm(forms.ModelForm):
    class Meta:
        model = ForumThread
        fields = ['title', 'content']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 5, 'class': 'w-full p-2 border rounded'}),
            'title': forms.TextInput(attrs={'class': 'w-full p-2 border rounded'})
        }

class ReplyForm(forms.ModelForm):
    class Meta:
        model = ForumReply
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 3, 'class': 'w-full p-2 border rounded'})
        }

