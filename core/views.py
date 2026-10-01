from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator
from core.models import Produto
from core.forms import ProdutoForm
from django.http import HttpResponse
import csv
from django.db.models import Sum, Count
from core.models import Produto, HistoricoVenda
from django.db.models.functions import ExtractWeekDay
from .forms import ProdutoForm, CustomUserCreationForm



def landing_page(request):
    return render(request, 'core/landing.html')

def is_admin(user):
    return user.is_staff


def fazer_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('minha_home')
        else:
            messages.error(request, 'Utilizador ou senha inválidos.')
    else:
        form = AuthenticationForm()
    return render(request, 'core/login.html', {'form': form})

def fazer_logout(request):
    logout(request)
    return redirect('login')

def auto_registro(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_staff = False  # Segurança: garante que contas públicas nunca nascem como admin
            user.save()
            messages.success(request, 'Conta criada com sucesso! Faça login para começar.')
            return redirect('login')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = UserCreationForm()
        
    return render(request, 'core/auto_registro.html', {'form': form})


@login_required(login_url='login')
@user_passes_test(is_admin, login_url='/')
def cadastrar_usuario(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST) # <-- Alterado aqui
        if form.is_valid():
            user = form.save(commit=False)
            if request.POST.get('is_staff') == 'on':
                user.is_staff = True
            user.save()
            messages.success(request, f'Utilizador "{user.username}" criado com sucesso!')
            return redirect('minha_home')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = CustomUserCreationForm() # <-- E aqui
        
    return render(request, 'core/cadastrar_usuario.html', {'form': form})


def auto_registro(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_staff = False 
            user.save()
            messages.success(request, 'Conta criada com sucesso! Faça login para começar.')
            return redirect('login')
        else:
            for error in form.errors.values():
                messages.error(request, error)
    else:
        form = CustomUserCreationForm()
        
    return render(request, 'core/auto_registro.html', {'form': form})

@login_required(login_url='login')
def minha_home(request):
    termo_busca = request.GET.get('busca', '')
    
    if termo_busca:
        produtos_lista = Produto.objects.filter(name__icontains=termo_busca).order_by('-id')
    else:
        produtos_lista = Produto.objects.all().order_by('-id')
    
    valor_total_geral = 0
    lucro_total_geral = 0
    
    for p in produtos_lista:
        valor_total_geral += (p.preco * p.quantidade_estoque)
        lucro_total_geral += (p.lucro_unitario * p.quantidade_estoque)

    paginator = Paginator(produtos_lista, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    for p in page_obj:
        p.valor_total = p.preco * p.quantidade_estoque
        p.lucro_total_item = p.lucro_unitario * p.quantidade_estoque

    contexto = {
        'produtos': page_obj, 
        'valor_total_geral': valor_total_geral,
        'lucro_total_geral': lucro_total_geral,
        'termo_busca': termo_busca
    }
    return render(request, 'core/home.html', contexto)

@login_required(login_url='login')
@user_passes_test(is_admin, login_url='/')
def adicionar_produto(request):
    if request.method == 'POST':
        form = ProdutoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Produto cadastrado com sucesso!')
            return redirect('minha_home')
    else:
        form = ProdutoForm()
    
    contexto = {'form': form}
    return render(request, 'core/adicionar_produto.html', contexto)

@login_required(login_url='login')
@user_passes_test(is_admin, login_url='/')
def editar_produto(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id)
    
    if request.method == 'POST':
        form = ProdutoForm(request.POST, instance=produto)
        if form.is_valid():
            form.save()
            messages.success(request, f'Produto "{produto.name}" atualizado com sucesso!')
            return redirect('minha_home')
    else:
        form = ProdutoForm(instance=produto)
        
    contexto = {'form': form, 'produto': produto}
    return render(request, 'core/editar_produto.html', contexto)

@login_required(login_url='login')
def realizar_venda(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id)
    
    if request.method == 'POST':
        try:
            quantidade = int(request.POST.get('quantidade', 0))
            
            if quantidade <= 0:
                messages.error(request, 'A quantidade de venda deve ser maior que zero.')
            elif quantidade > produto.quantidade_estoque:
                messages.error(request, f'Estoque insuficiente! Só possui {produto.quantidade_estoque} un.')
            else:
                lucro_venda = produto.lucro_unitario * quantidade
                
                HistoricoVenda.objects.create(
                    produto=produto,
                    nome_produto=produto.name,
                    quantidade=quantidade,
                    preco_venda_unitario=produto.preco,
                    lucro_obtido=lucro_venda,
                    usuario=request.user
                )
                
                produto.quantidade_estoque -= quantidade
                produto.save()
                
                messages.success(request, f'Venda de {quantidade}x "{produto.name}" registada com sucesso!')
                return redirect('minha_home')
                
        except ValueError:
            messages.error(request, 'Por favor, digite um número válido.')
            
    return render(request, 'core/realizar_venda.html', {'produto': produto})

@login_required(login_url='login')
@user_passes_test(is_admin, login_url='/')
def historico_vendas(request):
    vendas = HistoricoVenda.objects.all().order_by('-data_venda')
    lucro_total_historico = sum(v.lucro_obtido for v in vendas)
    
    vendas_por_operador = (
        vendas.values('usuario__username')
        .annotate(total_faturado=Sum('lucro_obtido'), total_vendas=Count('id'))
    )
    
    operadores_nomes = [item['usuario__username'] if item['usuario__username'] else 'Sistema' for item in vendas_por_operador]
    operadores_lucros = [float(item['total_faturado'] or 0) for item in vendas_por_operador]

    dias_map = {1: 'Domingo', 2: 'Segunda', 3: 'Terça', 4: 'Quarta', 5: 'Quinta', 6: 'Sexta', 7: 'Sábado'}
    
    vendas_por_dia = (
        vendas.annotate(dia_semana=ExtractWeekDay('data_venda'))
        .values('dia_semana')
        .annotate(qtd=Count('id'))
        .order_by('dia_semana')
    )
    
    dias_ordenados = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
    dias_contagem = {dia: 0 for dia in dias_ordenados}
    
    for item in vendas_por_dia:
        num_dia = item['dia_semana']
        nome_dia = dias_map.get(num_dia)
        if nome_dia in dias_contagem:
            dias_contagem[nome_dia] = item['qtd']

    contexto = {
        'vendas': vendas,
        'lucro_total_historico': lucro_total_historico,
        'operadores_nomes': operadores_nomes,
        'operadores_lucros': operadores_lucros,
        'dias_labels': dias_ordenados,
        'dias_valores': list(dias_contagem.values()),
    }
    return render(request, 'core/historico_vendas.html', contexto)

@login_required(login_url='login')
@user_passes_test(is_admin, login_url='/')
def relatorios(request):
    produtos = Produto.objects.all()
    
    total_produtos_cadastrados = produtos.count()
    total_itens_estoque = produtos.aggregate(Sum('quantidade_estoque'))['quantidade_estoque__sum'] or 0
    produtos_esgotados = produtos.filter(quantidade_estoque=0).count()
    
    # Totais financeiros
    valor_total_investido = sum(p.preco_custo * p.quantidade_estoque for p in produtos)
    valor_total_venda = sum(p.preco * p.quantidade_estoque for p in produtos)
    lucro_total_projetado = sum((p.preco - p.preco_custo) * p.quantidade_estoque for p in produtos)
    
    # Destaques
    produto_maior_margem = max(produtos, key=lambda p: p.lucro_unitario) if produtos.exists() else None
    produto_mais_valioso = max(produtos, key=lambda p: (p.preco * p.quantidade_estoque)) if produtos.exists() else None
    produtos_baixo_estoque = produtos.filter(quantidade_estoque__gt=0).order_by('quantidade_estoque')[:3]

    categorias_dados = {}
    for cat_nome, _ in Produto.CATEGORIAS_CHOICES:
        prods_cat = produtos.filter(categoria=cat_nome)
        lucro_cat = sum((p.preco - p.preco_custo) * p.quantidade_estoque for p in prods_cat)
        if prods_cat.exists():
            categorias_dados[cat_nome] = float(lucro_cat)

    contexto = {
        'total_produtos_cadastrados': total_produtos_cadastrados,
        'total_itens_estoque': total_itens_estoque,
        'produtos_esgotados': produtos_esgotados,
        'valor_total_investido': valor_total_investido,
        'valor_total_venda': valor_total_venda,
        'lucro_total_projetado': lucro_total_projetado,
        'produto_maior_margem': produto_maior_margem,
        'produto_mais_valioso': produto_mais_valioso,
        'produtos_baixo_estoque': produtos_baixo_estoque,
        'categorias_nomes': list(categorias_dados.keys()),
        'categorias_valores': list(categorias_dados.values()),
    }
    return render(request, 'core/relatorios.html', contexto)

@login_required(login_url='login')
@user_passes_test(is_admin, login_url='/')
def exportar_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="relatorio_estoque.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Nome', 'Categoria', 'Preco Custo', 'Preco Venda', 'Estoque', 'Lucro Unitario'])
    
    for p in Produto.objects.all():
        writer.writerow([p.name, p.categoria, p.preco_custo, p.preco, p.quantidade_estoque, p.lucro_unitario])
        
    return response