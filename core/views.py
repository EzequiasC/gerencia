import csv
import re
import uuid
from decimal import Decimal, InvalidOperation
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.db import transaction
from django.contrib.auth.models import User
from django.db.models import Sum, Count, F
from django.db.models.functions import ExtractWeekDay

from core.models import Produto, HistoricoVenda, CaixaTurno
from core.forms import ProdutoForm, CustomUserCreationForm


# ======================================================================
# UTILITÁRIOS E SEGURANÇA
# ======================================================================

FORMAS_VALIDAS = {'dinheiro', 'pix', 'debito', 'credito'}

def parse_valor_monetario(texto):
    """
    Analisa um valor em texto e retorna um Decimal seguro.
    Bloqueia entradas maliciosas como notação científica (1e999) ou formatações duplas (20,00,00).
    """
    if not texto:
        return None
    
    texto_limpo = str(texto).strip().replace(',', '.')
    
    if not re.fullmatch(r'\d+(\.\d{1,2})?', texto_limpo):
        return None
        
    try:
        valor = Decimal(texto_limpo)
    except InvalidOperation:
        return None
        
    if valor < 0 or valor > Decimal('100000.00'):
        return None
        
    return valor

def staff_required(view_func):
    """
    Restringe áreas do sistema apenas a administradores (staff).
    """
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if not request.user.is_staff:
            messages.error(request, 'Você não tem permissão para acessar esta página.')
            return redirect('minha_home')
        return view_func(request, *args, **kwargs)
    return wrapper


# ======================================================================
# PÁGINAS PÚBLICAS E AUTENTICAÇÃO
# ======================================================================

def landing_page(request):
    return render(request, 'core/landing.html')

def fazer_login(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if not user.is_active:
                messages.error(request, 'Sua conta ainda não foi ativada pelo administrador.')
                return redirect('login')
            auth_login(request, user)
            return redirect('minha_home')
        else:
            messages.error(request, 'Usuário ou senha inválidos.')
    else:
        form = AuthenticationForm()
    return render(request, 'core/login.html', {'form': form})

def fazer_logout(request):
    auth_logout(request)
    return redirect('login')

def auto_registro(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False  
            user.is_staff = False
            user.save()
            messages.success(request, 'Conta cadastrada com sucesso! Aguarde a liberação do administrador.')
            return redirect('login')
        else:
            for erros in form.errors.values():
                for erro in erros:
                    messages.error(request, erro)
    else:
        form = CustomUserCreationForm()
        
    return render(request, 'core/auto_registro.html', {'form': form})

@login_required(login_url='login')
@staff_required
def cadastrar_usuario(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            if request.POST.get('is_staff') == 'on':
                user.is_staff = True
            user.is_active = True
            user.save()
            messages.success(request, f'Usuário "{user.username}" criado com sucesso!')
            return redirect('minha_home')
        else:
            for erros in form.errors.values():
                for erro in erros:
                    messages.error(request, erro)
    else:
        form = CustomUserCreationForm()
        
    return render(request, 'core/cadastrar_usuario.html', {'form': form})


# ======================================================================
# INVENTÁRIO (PRODUTOS)
# ======================================================================

@login_required(login_url='login')
def minha_home(request):
    termo_busca = request.GET.get('busca', '')
    categoria_filtro = request.GET.get('categoria', '')
    
    produtos_lista = Produto.objects.all().order_by('-id')
    
    if termo_busca:
        produtos_lista = produtos_lista.filter(name__icontains=termo_busca)
        
    if categoria_filtro:
        produtos_lista = produtos_lista.filter(categoria=categoria_filtro)
    
    totais_gerais = Produto.objects.aggregate(
        valor_total=Sum(F('preco') * F('quantidade_estoque')),
        lucro_total=Sum((F('preco') - F('preco_custo')) * F('quantidade_estoque'))
    )
    valor_total_geral = totais_gerais['valor_total'] or 0
    lucro_total_geral = totais_gerais['lucro_total'] or 0

    paginator = Paginator(produtos_lista, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    for p in page_obj:
        preco = p.preco or 0
        custo = p.preco_custo or 0
        qtd = p.quantidade_estoque or 0
        p.valor_total = preco * qtd
        p.lucro_total_item = (preco - custo) * qtd

    contexto = {
        'produtos': page_obj, 
        'valor_total_geral': valor_total_geral,
        'lucro_total_geral': lucro_total_geral,
        'termo_busca': termo_busca,
        'categoria_filtro': categoria_filtro,
        'categorias': Produto.CATEGORIAS_CHOICES,
    }
    return render(request, 'core/home.html', contexto)

@login_required(login_url='login')
@staff_required
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
@staff_required
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


# ======================================================================
# CARRINHO DE COMPRAS E VENDAS
# ======================================================================

@login_required(login_url='login')
@require_POST
def adicionar_ao_carrinho(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id)
    
    try:
        quantidade = int(request.POST.get('quantidade', 1))
        if quantidade < 1:
            raise ValueError
    except ValueError:
        messages.error(request, 'A quantidade informada é inválida (deve ser maior que zero).')
        return redirect('minha_home')
        
    if quantidade > produto.quantidade_estoque:
        messages.error(request, f'Estoque insuficiente! Só existem {produto.quantidade_estoque} unidades.')
        return redirect('minha_home')
        
    if 'cart' not in request.session:
        request.session['cart'] = {}
        
    cart = request.session['cart']
    str_id = str(produto_id)
    
    quantidade_atual = cart.get(str_id, 0)
    nova_quantidade = quantidade_atual + quantidade
    
    if nova_quantidade > produto.quantidade_estoque:
        messages.error(request, 'A quantidade total no carrinho excede o estoque disponível.')
        return redirect('minha_home')
        
    cart[str_id] = nova_quantidade
    request.session.modified = True
    
    messages.success(request, f'"{produto.name}" adicionado ao carrinho!')
    return redirect('minha_home')

@login_required(login_url='login')
@require_POST # <-- Prevenção contra alteração via GET
def atualizar_quantidade_carrinho(request, produto_id, acao):
    produto = get_object_or_404(Produto, id=produto_id)
    str_id = str(produto_id)
    
    if 'cart' in request.session and str_id in request.session['cart']:
        cart = request.session['cart']
        qtd_atual = cart[str_id]
        
        if acao == 'aumentar':
            if qtd_atual + 1 > produto.quantidade_estoque:
                messages.error(request, f'Estoque insuficiente! Máximo disponível: {produto.quantidade_estoque} un.')
            else:
                cart[str_id] += 1
                
        elif acao == 'diminuir':
            if qtd_atual > 1:
                cart[str_id] -= 1
            else:
                del cart[str_id]
                messages.info(request, f'"{produto.name}" removido do carrinho.')
                
        request.session.modified = True
        
    return redirect('ver_carrinho')

@login_required(login_url='login')
def ver_carrinho(request):
    cart = request.session.get('cart', {})
    itens_carrinho = []
    valor_total_carrinho = 0
    cart_modificado = False
    
    for produto_id, quantidade in list(cart.items()):
        produto = Produto.objects.filter(id=int(produto_id)).first()
        if not produto:
            del cart[produto_id]
            cart_modificado = True
            continue
            
        subtotal = produto.preco * quantidade
        valor_total_carrinho += subtotal
        
        itens_carrinho.append({
            'produto': produto,
            'quantidade': quantidade,
            'subtotal': subtotal
        })
        
    if cart_modificado:
        request.session.modified = True
        
    contexto = {
        'itens': itens_carrinho,
        'valor_total_carrinho': valor_total_carrinho
    }
    return render(request, 'core/carrinho.html', contexto)

@login_required(login_url='login')
@require_POST
def remover_do_carrinho(request, produto_id):
    cart = request.session.get('cart', {})
    str_id = str(produto_id)
    
    if str_id in cart:
        del cart[str_id]
        request.session.modified = True
        messages.success(request, 'Item removido do carrinho.')
        
    return redirect('ver_carrinho')

@login_required(login_url='login')
@require_POST
def finalizar_venda_carrinho(request):
    caixa_aberto = CaixaTurno.objects.filter(usuario=request.user, aberto=True).first()
    if not caixa_aberto:
        messages.error(request, 'Você precisa abrir o caixa antes de finalizar vendas.')
        return redirect('gerenciar_caixa')

    forma_pagamento = request.POST.get('forma_pagamento', '').strip().lower()
    if forma_pagamento not in FORMAS_VALIDAS:
        messages.error(request, 'Forma de pagamento inválida.')
        return redirect('ver_carrinho')

    valor_recebido_str = request.POST.get('valor_recebido', '0')
    cart = request.session.get('cart', {})
    
    if not cart:
        messages.error(request, 'Seu carrinho está vazio.')
        return redirect('ver_carrinho')
        
    itens_recibo = []
    valor_total_venda = Decimal('0.00')
    
    try:
        with transaction.atomic():
            p_ids = []
            for i in cart.keys():
                try:
                    p_ids.append(int(i))
                except (ValueError, TypeError):
                    pass
            
            produtos = {p.id: p for p in Produto.objects.select_for_update().filter(id__in=p_ids)}
            
            for pid_str, qtd in cart.items():
                try:
                    pid = int(pid_str)
                    qtd = int(qtd)
                except (ValueError, TypeError):
                    raise ValueError('Quantidade inválida no carrinho.')

                if qtd < 1:
                    raise ValueError('A quantidade do produto deve ser maior que zero.')

                produto = produtos.get(pid)
                if produto is None or qtd > produto.quantidade_estoque:
                    nome = produto.name if produto else 'um item'
                    raise ValueError(f'Estoque insuficiente para "{nome}". Nenhuma venda foi realizada.')
                
                subtotal = produto.preco * Decimal(qtd)
                valor_total_venda += subtotal

            troco = Decimal('0.00')
            valor_recebido = Decimal('0.00')
            if forma_pagamento == 'dinheiro':
                valor_recebido = parse_valor_monetario(valor_recebido_str)
                if valor_recebido is None:
                    raise ValueError('O valor em dinheiro recebido é inválido.')
                
                if valor_recebido < valor_total_venda:
                    raise ValueError('O valor recebido em dinheiro é menor que o total da compra.')
                
                troco = valor_recebido - valor_total_venda

            venda_lote_id = uuid.uuid4()

            for pid_str, qtd in cart.items():
                pid = int(pid_str)
                qtd = int(qtd)
                produto = produtos.get(pid)
                
                lucro_venda = produto.lucro_unitario * Decimal(qtd)
                subtotal = produto.preco * Decimal(qtd)
                
                HistoricoVenda.objects.create(
                    venda_uuid=venda_lote_id,
                    produto=produto,
                    nome_produto=produto.name,
                    quantidade=qtd,
                    preco_venda_unitario=produto.preco,
                    lucro_obtido=lucro_venda,
                    usuario=request.user,
                    caixa=caixa_aberto,
                    forma_pagamento=forma_pagamento # <--- Associa a forma de pagamento real (Dinheiro, PIX, etc)
                )
                
                itens_recibo.append({
                    'nome': produto.name,
                    'quantidade': qtd,
                    'preco_unitario': float(produto.preco),
                    'subtotal': float(subtotal)
                })
                
                produto.quantidade_estoque -= qtd
                produto.save()
                
    except ValueError as e:
        messages.error(request, str(e))
        return redirect('ver_carrinho')
        
    request.session['ultimo_recibo'] = {
        'itens': itens_recibo,
        'total': float(valor_total_venda),
        'forma_pagamento': forma_pagamento.upper(),
        'valor_recebido': float(valor_recebido) if forma_pagamento == 'dinheiro' else float(valor_total_venda),
        'troco': float(troco),
        'operador': request.user.username,
        'data': str(timezone.now().strftime('%d/%m/%Y %H:%M'))
    }
    request.session['cart'] = {}
    request.session.modified = True
    
    return redirect('comprovante_venda')


@login_required(login_url='login')
def realizar_venda(request, produto_id):
    # <-- 404 imediato bloqueia erro 500 caso o ID seja inválido
    produto_verificacao = get_object_or_404(Produto, id=produto_id) 
    
    caixa_aberto = CaixaTurno.objects.filter(usuario=request.user, aberto=True).first()
    if not caixa_aberto:
        messages.error(request, 'Você precisa abrir o caixa antes de realizar vendas.')
        return redirect('gerenciar_caixa')

    if request.method == 'POST':
        try:
            quantidade = int(request.POST.get('quantidade', 0))
            if quantidade <= 0:
                messages.error(request, 'A quantidade de venda deve ser maior que zero.')
                return redirect('realizar_venda', produto_id=produto_id)
            
            with transaction.atomic():
                produto = Produto.objects.select_for_update().get(id=produto_id)
                if quantidade > produto.quantidade_estoque:
                    messages.error(request, f'Estoque insuficiente! Só possui {produto.quantidade_estoque} un.')
                    return redirect('realizar_venda', produto_id=produto_id)
                
                lucro_venda = produto.lucro_unitario * quantidade
                venda_lote_id = uuid.uuid4()
                
                HistoricoVenda.objects.create(
                    venda_uuid=venda_lote_id,
                    produto=produto,
                    nome_produto=produto.name,
                    quantidade=quantidade,
                    preco_venda_unitario=produto.preco,
                    lucro_obtido=lucro_venda,
                    usuario=request.user,
                    caixa=caixa_aberto,
                    forma_pagamento='dinheiro' # <-- Assume dinheiro para vendas rápidas sem carrinho
                )
                
                produto.quantidade_estoque -= quantidade
                produto.save()
                
            messages.success(request, f'Venda de {quantidade}x "{produto.name}" registrada com sucesso!')
            return redirect('minha_home')
            
        except ValueError:
            messages.error(request, 'Por favor, digite um número válido.')
            return redirect('realizar_venda', produto_id=produto_id)
            
    return render(request, 'core/realizar_venda.html', {'produto': produto_verificacao})


@login_required(login_url='login')
def comprovante_venda(request):
    recibo = request.session.get('ultimo_recibo')
    if not recibo:
        messages.error(request, 'Nenhum recibo recente encontrado.')
        return redirect('minha_home')
        
    return render(request, 'core/comprovante.html', {'recibo': recibo})


# ======================================================================
# FLUXO DE CAIXA E HISTÓRICO
# ======================================================================

@login_required(login_url='login')
def gerenciar_caixa(request):
    caixa_aberto = CaixaTurno.objects.filter(usuario=request.user, aberto=True).first()
    
    if request.method == 'POST':
        acao = request.POST.get('acao')
        
        if acao == 'abrir':
            if caixa_aberto:
                messages.error(request, 'Você já possui um caixa aberto.')
            else:
                valor_inicial = parse_valor_monetario(request.POST.get('valor_inicial'))
                if valor_inicial is None:
                    messages.error(request, 'Valor inicial inválido. Use um número positivo válido.')
                else:
                    CaixaTurno.objects.create(usuario=request.user, valor_inicial=valor_inicial, aberto=True)
                    messages.success(request, 'Caixa aberto com sucesso! Bom turno de vendas.')
            return redirect('gerenciar_caixa')
            
        elif acao == 'fechar':
            if not caixa_aberto:
                messages.error(request, 'Não há nenhum caixa aberto para fechar.')
            else:
                valor_informado = parse_valor_monetario(request.POST.get('valor_informado'))
                if valor_informado is None:
                    messages.error(request, 'Valor informado inválido.')
                    return redirect('gerenciar_caixa')
                    
                # NOVO: Filtra APENAS DINHEIRO para o cálculo físico de fecho da gaveta
                vendas_turno_dinheiro = HistoricoVenda.objects.filter(caixa=caixa_aberto, forma_pagamento='dinheiro')
                total_vendas_dinheiro = sum(float(v.preco_venda_unitario) * v.quantidade for v in vendas_turno_dinheiro)
                
                valor_esperado = float(caixa_aberto.valor_inicial) + total_vendas_dinheiro
                
                valor_informado_f = float(valor_informado)
                valor_esperado_f = round(valor_esperado, 2)
                
                if round(valor_informado_f, 2) != valor_esperado_f:
                    diferenca = valor_informado_f - valor_esperado_f
                    if diferenca > 0:
                        messages.error(request, f'Erro: O caixa não bate! Estão a sobrar R$ {diferenca:.2f}.')
                    else:
                        messages.error(request, f'Erro: O caixa não bate! Estão a faltar R$ {abs(diferenca):.2f}.')
                    
                    return redirect('gerenciar_caixa')
                
                caixa_aberto.valor_informado = valor_informado_f
                
                # Regista o total global no caixa para efeitos de relatório
                vendas_turno_todas = HistoricoVenda.objects.filter(caixa=caixa_aberto)
                total_vendas_todas = sum(float(v.preco_venda_unitario) * v.quantidade for v in vendas_turno_todas)
                caixa_aberto.total_vendas = total_vendas_todas
                
                caixa_aberto.data_fechamento = timezone.now()
                caixa_aberto.aberto = False
                caixa_aberto.save()
                
                messages.success(request, 'Caixa fechado com sucesso! Os valores estão exatos.')
            return redirect('gerenciar_caixa')

    vendas_atuais = []
    total_parcial = 0
    total_geral_caixa = 0
    
    if caixa_aberto:
        vendas_atuais = HistoricoVenda.objects.filter(caixa=caixa_aberto).order_by('-data_venda')
        # Mostramos à direita apenas o que esperamos em dinheiro (total da gaveta + parcial)
        total_parcial = sum(float(v.preco_venda_unitario) * v.quantidade for v in vendas_atuais.filter(forma_pagamento='dinheiro'))
        total_geral_caixa = float(caixa_aberto.valor_inicial) + total_parcial

    contexto = {
        'caixa_aberto': caixa_aberto,
        'vendas_atuais': vendas_atuais,
        'total_parcial': total_parcial,
        'total_geral_caixa': total_geral_caixa,
    }
    return render(request, 'core/caixa.html', contexto)


@login_required(login_url='login')
@staff_required
def historico_vendas(request):
    vendas_list = HistoricoVenda.objects.all().order_by('-data_venda')
    vendas_todos = HistoricoVenda.objects.all()
    lucro_total_historico = sum(v.lucro_obtido for v in vendas_todos)
    
    vendas_por_operador = (
        vendas_todos.values('usuario__username')
        .annotate(total_faturado=Sum('lucro_obtido'), total_vendas=Count('id'))
    )
    
    operadores_nomes = [item['usuario__username'] if item['usuario__username'] else 'Sistema' for item in vendas_por_operador]
    operadores_lucros = [float(item['total_faturado'] or 0) for item in vendas_por_operador]

    dias_map = {1: 'Domingo', 2: 'Segunda', 3: 'Terça', 4: 'Quarta', 5: 'Quinta', 6: 'Sexta', 7: 'Sábado'}
    
    vendas_por_dia = (
        vendas_todos.annotate(dia_semana=ExtractWeekDay('data_venda'))
        .values('dia_semana')
        .annotate(qtd=Count('id'))
        .order_by('dia_semana')
    )
    
    dias_ordenados = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo']
    dias_contagem = {dia: 0 for dia in dias_ordenados}
    
    for item in vendas_por_dia:
        num_dia = item['dia_semana']
        nome_dia = dias_map.get(num_dia)
        if nome_dia in dias_ordenados:
            dias_contagem[nome_dia] = item['qtd']

    paginator = Paginator(vendas_list, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    contexto = {
        'vendas': page_obj,
        'lucro_total_historico': lucro_total_historico,
        'operadores_nomes': operadores_nomes,
        'operadores_lucros': operadores_lucros,
        'dias_labels': dias_ordenados,
        'dias_valores': list(dias_contagem.values()),
    }
    return render(request, 'core/historico_vendas.html', contexto)

@login_required(login_url='login')
@staff_required
@require_POST
def cancelar_venda(request, venda_id):
    venda = get_object_or_404(HistoricoVenda, id=venda_id)
    
    try:
        with transaction.atomic():
            if venda.produto:
                produto = Produto.objects.select_for_update().get(id=venda.produto.id)
                produto.quantidade_estoque += venda.quantidade
                produto.save()
            
            venda_nome = venda.nome_produto
            venda.delete()
            
        messages.success(request, f'Venda de "{venda_nome}" ({venda.quantidade} un.) estornada com sucesso e estoque devolvido!')
    except Exception as e:
        messages.error(request, f'Erro ao estornar venda: {str(e)}')
        
    return redirect('historico_vendas')

@login_required(login_url='login')
def historico_recibos(request):
    sete_dias_atras = timezone.now() - timedelta(days=7)
    
    recibos = HistoricoVenda.objects.filter(
        data_venda__gte=sete_dias_atras
    ).order_by('-data_venda')
    
    total_semana = sum(float(r.preco_venda_unitario) * r.quantidade for r in recibos)

    contexto = {
        'recibos': recibos,
        'total_semana': total_semana,
    }
    return render(request, 'core/recibos.html', contexto)


# ======================================================================
# GESTÃO EXECUTIVA (RELATÓRIOS E UTILIZADORES)
# ======================================================================

@login_required(login_url='login')
def gerenciar_usuarios(request):
    if not request.user.is_staff:
        messages.error(request, 'Acesso restrito a administradores.')
        return redirect('minha_home')
        
    usuarios = User.objects.all().order_by('-date_joined')
    return render(request, 'core/usuarios.html', {'usuarios': usuarios})

@login_required(login_url='login')
@require_POST
def alternar_status_usuario(request, user_id):
    if not request.user.is_staff:
        messages.error(request, 'Acesso restrito a administradores.')
        return redirect('minha_home')
        
    usuario = get_object_or_404(User, id=user_id)
    
    if usuario == request.user:
        messages.error(request, 'Você não pode alterar o status da sua própria conta.')
        return redirect('gerenciar_usuarios')
        
    usuario.is_active = not usuario.is_active
    usuario.save()
    
    status_txt = "ativado/aprovado" if usuario.is_active else "desativado/bloqueado"
    messages.success(request, f'O usuário "{usuario.username}" foi {status_txt} com sucesso!')
    return redirect('gerenciar_usuarios')

@login_required(login_url='login')
@staff_required
def relatorios(request):
    produtos = Produto.objects.all()
    
    total_produtos_cadastrados = produtos.count()
    total_itens_estoque = produtos.aggregate(Sum('quantidade_estoque'))['quantidade_estoque__sum'] or 0
    produtos_esgotados = produtos.filter(quantidade_estoque=0).count()
    
    valor_total_investido = sum(p.preco_custo * p.quantidade_estoque for p in produtos)
    valor_total_venda = sum(p.preco * p.quantidade_estoque for p in produtos)
    lucro_total_projetado = sum((p.preco - p.preco_custo) * p.quantidade_estoque for p in produtos)
    
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
@staff_required
def exportar_csv(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="relatorio_estoque.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Nome', 'Categoria', 'Preço Custo', 'Preço Venda', 'Estoque', 'Lucro Unitário'])
    
    # NOVO: Impede Injeção de Código em Planilhas Excel
    def sanitizar(texto):
        texto_str = str(texto)
        if texto_str.startswith(('=', '+', '-', '@')):
            return f"'{texto_str}"
        return texto_str
    
    for p in Produto.objects.all():
        writer.writerow([
            sanitizar(p.name), 
            sanitizar(p.categoria), 
            p.preco_custo, 
            p.preco, 
            p.quantidade_estoque, 
            p.lucro_unitario
        ])
        
    return response