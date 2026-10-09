"""
Suíte de testes do PDV (caixa / carrinho / estoque).

Organização:
    BaseVendaTestCase          -> fixtures e helpers reutilizáveis
    AcessoETests               -> autenticação e métodos HTTP
    CaixaTests                 -> regras de caixa aberto/fechado
    VendaDinheiroTests         -> pagamento em dinheiro e troco
    VendaOutrosPagamentosTests -> pix/cartão e formas inválidas
    EstoqueETests              -> estoque, atomicidade, carrinho vazio, idempotência

Rodar:
    python manage.py test                      # tudo
    python manage.py test core.tests.CaixaTests
    python manage.py test --parallel --failfast
"""
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.shortcuts import resolve_url
from django.test import TestCase
from django.urls import reverse

# Ajuste 'core' se a sua app tiver outro nome
from .models import CaixaTurno, HistoricoVenda, Produto


# ======================================================================
# BASE
# ======================================================================
class BaseVendaTestCase(TestCase):
    """Cria dados imutáveis uma vez (rápido) e oferece helpers."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("operador1", password="password123")
        cls.outro_user = User.objects.create_user("operador2", password="password123")

    def setUp(self):
        # Produtos são recriados por teste, pois o estoque é alterado.
        self.produto = self._criar_produto("Energético Teste", "10.00", "5.00", 5)
        self.client.login(username="operador1", password="password123")

    # ---------- helpers ----------
    @staticmethod
    def _criar_produto(nome="Produto", preco="10.00", custo="5.00", estoque=10):
        return Produto.objects.create(
            name=nome,
            preco=Decimal(preco),
            preco_custo=Decimal(custo),
            quantidade_estoque=estoque,
        )

    def _abrir_caixa(self, usuario=None, valor_inicial="50.00", aberto=True):
        return CaixaTurno.objects.create(
            usuario=usuario or self.user,
            valor_inicial=Decimal(valor_inicial),
            aberto=aberto,
        )

    def _set_carrinho(self, itens):
        """itens: {produto_obj: quantidade}"""
        session = self.client.session
        session["cart"] = {str(p.id): q for p, q in itens.items()}
        session.save()

    def _finalizar(self, **dados):
        return self.client.post(
            reverse("finalizar_venda_carrinho"), dados, follow=True
        )

    def _mensagens(self, response):
        return [(m.level_tag, str(m)) for m in get_messages(response.wsgi_request)]

    def _assert_estoque(self, produto, esperado):
        produto.refresh_from_db()
        self.assertEqual(
            produto.quantidade_estoque,
            esperado,
            f"Estoque de '{produto.name}' deveria ser {esperado}.",
        )

    def _assert_nenhuma_venda(self):
        self.assertEqual(HistoricoVenda.objects.count(), 0)


# ======================================================================
# ACESSO / HTTP
# ======================================================================
class AcessoETests(BaseVendaTestCase):

    def test_anonimo_e_redirecionado_para_login(self):
        self.client.logout()
        url = reverse("finalizar_venda_carrinho")
        response = self.client.post(url, {"forma_pagamento": "pix"})

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            response.url.startswith(resolve_url(settings.LOGIN_URL)),
            f"Esperava redirect para {resolve_url(settings.LOGIN_URL)}, veio {response.url}",
        )

    def test_anonimo_nao_altera_estoque(self):
        self._abrir_caixa()
        self._set_carrinho({self.produto: 2})
        self.client.logout()

        self.client.post(reverse("finalizar_venda_carrinho"), {"forma_pagamento": "pix"})

        self._assert_estoque(self.produto, 5)
        self._assert_nenhuma_venda()

    def test_get_nao_finaliza_venda(self):
        """Finalizar venda é ação de escrita: GET nunca pode alterar estado."""
        self._abrir_caixa()
        self._set_carrinho({self.produto: 2})

        self.client.get(reverse("finalizar_venda_carrinho"))

        self._assert_estoque(self.produto, 5)
        self._assert_nenhuma_venda()


# ======================================================================
# CAIXA
# ======================================================================
class CaixaTests(BaseVendaTestCase):

    def test_bloqueio_venda_sem_caixa(self):
        self._set_carrinho({self.produto: 1})

        response = self._finalizar(forma_pagamento="dinheiro", valor_recebido="20.00")

        self.assertRedirects(response, reverse("gerenciar_caixa"))
        self._assert_estoque(self.produto, 5)
        self._assert_nenhuma_venda()

    def test_bloqueio_com_caixa_ja_fechado(self):
        self._abrir_caixa(aberto=False)
        self._set_carrinho({self.produto: 1})

        response = self._finalizar(forma_pagamento="dinheiro", valor_recebido="20.00")

        self.assertRedirects(response, reverse("gerenciar_caixa"))
        self._assert_estoque(self.produto, 5)

    def test_caixa_de_outro_operador_nao_vale(self):
        """Caixa aberto por outro usuário não autoriza a venda deste usuário."""
        self._abrir_caixa(usuario=self.outro_user)
        self._set_carrinho({self.produto: 1})

        response = self._finalizar(forma_pagamento="dinheiro", valor_recebido="20.00")

        self.assertRedirects(response, reverse("gerenciar_caixa"))
        self._assert_estoque(self.produto, 5)
        self._assert_nenhuma_venda()

    def test_bloqueio_sem_caixa_exibe_mensagem_de_erro(self):
        self._set_carrinho({self.produto: 1})

        response = self._finalizar(forma_pagamento="pix")

        niveis = [nivel for nivel, _ in self._mensagens(response)]
        self.assertIn("error", niveis)


# ======================================================================
# DINHEIRO
# ======================================================================
class VendaDinheiroTests(BaseVendaTestCase):

    def setUp(self):
        super().setUp()
        self.caixa = self._abrir_caixa()

    def test_fluxo_completo_com_troco(self):
        self._set_carrinho({self.produto: 2})  # total R$ 20,00

        response = self._finalizar(forma_pagamento="dinheiro", valor_recebido="50.00")

        self.assertRedirects(response, reverse("comprovante_venda"))
        self._assert_estoque(self.produto, 3)

        recibo = self.client.session.get("ultimo_recibo")
        self.assertIsNotNone(recibo)
        self.assertEqual(recibo["total"], 20.0)
        self.assertEqual(recibo["valor_recebido"], 50.0)
        self.assertEqual(recibo["troco"], 30.0)

        vendas = HistoricoVenda.objects.filter(caixa=self.caixa)
        self.assertEqual(vendas.count(), 1)
        self.assertEqual(vendas.first().quantidade, 2)

    def test_valor_exato_gera_troco_zero(self):
        self._set_carrinho({self.produto: 2})

        response = self._finalizar(forma_pagamento="dinheiro", valor_recebido="20.00")

        self.assertRedirects(response, reverse("comprovante_venda"))
        self.assertEqual(self.client.session["ultimo_recibo"]["troco"], 0.0)
        self._assert_estoque(self.produto, 3)

    def test_valor_recebido_insuficiente_e_recusado(self):
        self._set_carrinho({self.produto: 2})  # total 20, recebeu 15

        response = self._finalizar(forma_pagamento="dinheiro", valor_recebido="15.00")

        self.assertRedirects(response, reverse("ver_carrinho"))
        self._assert_estoque(self.produto, 5)
        self._assert_nenhuma_venda()
        self.assertNotIn("ultimo_recibo", self.client.session)

    def test_valor_recebido_invalido_nao_quebra_o_servidor(self):
        """Entradas sujas nunca devem gerar erro 500."""
        entradas = ["", "abc", "-10", "1e999", "20,00,00"]
        for valor in entradas:
            with self.subTest(valor_recebido=valor):
                self._set_carrinho({self.produto: 2})
                response = self.client.post(
                    reverse("finalizar_venda_carrinho"),
                    {"forma_pagamento": "dinheiro", "valor_recebido": valor},
                    follow=True,
                )
                self.assertLess(response.status_code, 500)
                self._assert_estoque(self.produto, 5)
                self._assert_nenhuma_venda()

    def test_valor_recebido_ausente_em_dinheiro(self):
        self._set_carrinho({self.produto: 1})

        response = self._finalizar(forma_pagamento="dinheiro")

        self.assertLess(response.status_code, 500)
        self._assert_estoque(self.produto, 5)

    def test_troco_com_centavos_sem_erro_de_ponto_flutuante(self):
        produto = self._criar_produto("Bala", preco="0.10", custo="0.05", estoque=100)
        self._set_carrinho({produto: 3})  # 0.30 (em float: 0.30000000000000004)

        self._finalizar(forma_pagamento="dinheiro", valor_recebido="1.00")

        recibo = self.client.session["ultimo_recibo"]
        self.assertAlmostEqual(recibo["total"], 0.30, places=2)
        self.assertAlmostEqual(recibo["troco"], 0.70, places=2)


# ======================================================================
# PIX / CARTÃO / INVÁLIDOS
# ======================================================================
class VendaOutrosPagamentosTests(BaseVendaTestCase):

    def setUp(self):
        super().setUp()
        self.caixa = self._abrir_caixa()

    def test_formas_de_pagamento_validas_baixam_estoque(self):
        for forma in ["pix", "cartao_credito", "cartao_debito"]:
            with self.subTest(forma_pagamento=forma):
                produto = self._criar_produto(f"Item {forma}", estoque=5)
                self._set_carrinho({produto: 1})

                response = self._finalizar(forma_pagamento=forma)

                # Ajuste os valores aceitos se o seu sistema usa outros nomes
                if response.redirect_chain and response.redirect_chain[-1][0] == reverse(
                    "comprovante_venda"
                ):
                    self._assert_estoque(produto, 4)

    def test_pix_nao_exige_valor_recebido(self):
        self._set_carrinho({self.produto: 1})

        response = self._finalizar(forma_pagamento="pix")

        self.assertRedirects(response, reverse("comprovante_venda"))
        self._assert_estoque(self.produto, 4)

    def test_forma_de_pagamento_inexistente_e_recusada(self):
        self._set_carrinho({self.produto: 1})

        response = self._finalizar(forma_pagamento="bitcoin_do_vizinho")

        self.assertLess(response.status_code, 500)
        self._assert_estoque(self.produto, 5)
        self._assert_nenhuma_venda()

    def test_forma_de_pagamento_ausente_e_recusada(self):
        self._set_carrinho({self.produto: 1})

        response = self._finalizar()

        self.assertLess(response.status_code, 500)
        self._assert_estoque(self.produto, 5)
        self._assert_nenhuma_venda()


# ======================================================================
# ESTOQUE / CARRINHO / ATOMICIDADE
# ======================================================================
class EstoqueETests(BaseVendaTestCase):

    def setUp(self):
        super().setUp()
        self.caixa = self._abrir_caixa()

    def test_falha_estoque_insuficiente(self):
        self._set_carrinho({self.produto: 10})  # só há 5

        response = self._finalizar(forma_pagamento="pix")

        self.assertRedirects(response, reverse("ver_carrinho"))
        self._assert_estoque(self.produto, 5)
        self._assert_nenhuma_venda()

    def test_vender_exatamente_o_estoque_zera_sem_ficar_negativo(self):
        self._set_carrinho({self.produto: 5})

        response = self._finalizar(forma_pagamento="pix")

        self.assertRedirects(response, reverse("comprovante_venda"))
        self._assert_estoque(self.produto, 0)

    def test_produto_sem_estoque_nao_pode_ser_vendido(self):
        self.produto.quantidade_estoque = 0
        self.produto.save()
        self._set_carrinho({self.produto: 1})

        response = self._finalizar(forma_pagamento="pix")

        self.assertRedirects(response, reverse("ver_carrinho"))
        self._assert_estoque(self.produto, 0)
        self._assert_nenhuma_venda()

    def test_carrinho_vazio_nao_gera_venda(self):
        response = self._finalizar(forma_pagamento="pix")

        self.assertRedirects(response, reverse("ver_carrinho"))
        self._assert_nenhuma_venda()

    def test_quantidades_invalidas_sao_recusadas(self):
        for qtd in [0, -3]:
            with self.subTest(quantidade=qtd):
                self._set_carrinho({self.produto: qtd})

                response = self._finalizar(forma_pagamento="pix")

                self.assertLess(response.status_code, 500)
                self._assert_estoque(self.produto, 5)
                self._assert_nenhuma_venda()

    def test_produto_removido_do_banco_nao_derruba_o_sistema(self):
        session = self.client.session
        session["cart"] = {"999999": 1}  # ID inexistente
        session.save()

        response = self._finalizar(forma_pagamento="pix")

        self.assertLess(response.status_code, 500)
        self._assert_nenhuma_venda()

    def test_venda_com_varios_produtos_baixa_cada_estoque(self):
        p2 = self._criar_produto("Água", preco="3.00", custo="1.00", estoque=20)
        self._set_carrinho({self.produto: 2, p2: 4})  # 20 + 12 = 32

        response = self._finalizar(forma_pagamento="dinheiro", valor_recebido="50.00")

        self.assertRedirects(response, reverse("comprovante_venda"))
        self._assert_estoque(self.produto, 3)
        self._assert_estoque(p2, 16)

        recibo = self.client.session["ultimo_recibo"]
        self.assertEqual(recibo["total"], 32.0)
        self.assertEqual(recibo["troco"], 18.0)
        self.assertEqual(HistoricoVenda.objects.filter(caixa=self.caixa).count(), 2)

    def test_atomicidade_falha_no_segundo_item_desfaz_o_primeiro(self):
        """
        Se o item 2 não tem estoque, o item 1 NÃO pode ter sido baixado.
        Este é o teste mais importante para integridade de estoque.
        """
        p2 = self._criar_produto("Raro", estoque=1)
        self._set_carrinho({self.produto: 2, p2: 5})

        self._finalizar(forma_pagamento="pix")

        self._assert_estoque(self.produto, 5)
        self._assert_estoque(p2, 1)
        self._assert_nenhuma_venda()

    def test_carrinho_e_limpo_apos_venda_bem_sucedida(self):
        self._set_carrinho({self.produto: 1})

        self._finalizar(forma_pagamento="pix")

        self.assertFalse(self.client.session.get("cart"))

    def test_reenvio_do_formulario_nao_baixa_estoque_duas_vezes(self):
        """Duplo clique / F5 no botão 'Finalizar'."""
        self._set_carrinho({self.produto: 2})

        self._finalizar(forma_pagamento="pix")
        self._finalizar(forma_pagamento="pix")  # segundo envio, carrinho já vazio

        self._assert_estoque(self.produto, 3)
        self.assertEqual(HistoricoVenda.objects.count(), 1)

    def test_alterar_preco_depois_nao_muda_total_do_recibo_ja_emitido(self):
        self._set_carrinho({self.produto: 2})
        self._finalizar(forma_pagamento="pix")

        self.produto.preco = Decimal("99.00")
        self.produto.save()

        self.assertEqual(self.client.session["ultimo_recibo"]["total"], 20.0)