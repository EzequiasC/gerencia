from django import forms
from core.models import Produto
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

class ProdutoForm(forms.ModelForm):
    class Meta:
        model = Produto
        fields = ['name', 'preco_custo', 'preco', 'quantidade_estoque', 'categoria']
        
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'preco_custo': forms.NumberInput(attrs={'class': 'form-control'}),
            'preco': forms.NumberInput(attrs={'class': 'form-control'}),
            'quantidade_estoque': forms.NumberInput(attrs={'class': 'form-control'}),
            'categoria': forms.Select(attrs={'class': 'form-control'}),
        }

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Nome de utilizador'
        self.fields['username'].help_text = 'Obrigatório. 150 caracteres ou menos. Apenas letras, números e os símbolos @/./+/-/_.'
        
        if 'password1' in self.fields:
            self.fields['password1'].label = 'Palavra-passe'
            self.fields['password1'].help_text = 'A palavra-passe deve ter pelo menos 8 caracteres e não pode ser demasiado comum.'
            
        if 'password2' in self.fields:
            self.fields['password2'].label = 'Confirmação da palavra-passe'
            self.fields['password2'].help_text = 'Introduza exatamente a mesma palavra-passe para confirmação.'