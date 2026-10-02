from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone

class Produto(models.Model):
    CATEGORIAS_CHOICES = (
        ('Bebidas', 'Bebidas'),
        ('Alimentos', 'Alimentos'),
        ('Limpeza', 'Limpeza'),
        ('Eletrónicos', 'Eletrónicos'),
        ('Outros', 'Outros'),
    )

    name = models.CharField(max_length=100)
    preco_custo = models.DecimalField(max_digits=10, decimal_places=2)
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    quantidade_estoque = models.IntegerField()
    
    categoria = models.CharField(
        max_length=50, 
        choices=CATEGORIAS_CHOICES, 
        default='Outros' 
    )

    @property
    def lucro_unitario(self):
        return self.preco - self.preco_custo

    def __str__(self):
        return self.name


class CaixaTurno(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    valor_inicial = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    data_abertura = models.DateTimeField(auto_now_add=True)
    data_fechamento = models.DateTimeField(null=True, blank=True)
    valor_informado = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    total_vendas = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    aberto = models.BooleanField(default=True)

    def __str__(self):
        status = "Aberto" if self.aberto else "Fechado"
        return f"Caixa #{self.id} - {self.usuario.username} ({status})"

class HistoricoVenda(models.Model):
    produto = models.ForeignKey(Produto, on_delete=models.SET_NULL, null=True)
    nome_produto = models.CharField(max_length=100)
    quantidade = models.IntegerField()
    preco_venda_unitario = models.DecimalField(max_digits=10, decimal_places=2)
    lucro_obtido = models.DecimalField(max_digits=10, decimal_places=2)
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    data_venda = models.DateTimeField(auto_now_add=True)
    caixa = models.ForeignKey(CaixaTurno, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Venda de {self.quantidade}x {self.nome_produto} por {self.usuario.username if self.usuario else 'Desconhecido'}"

