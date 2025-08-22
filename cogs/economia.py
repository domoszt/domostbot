# -*- coding: utf-8 -*-

"""
Cog para o sistema de economia do bot, responsável por gerenciar
saldos, transações, empregos e eventos econômicos.

Arquitetura:
- A classe 'DataManager' lida com toda a lógica de I/O (leitura/escrita)
  do arquivo JSON, agindo como uma Camada de Acesso a Dados (DAL).
- A classe 'Economia' (o Cog) contém a lógica dos comandos, mas delega
  todas as operações de dados para o 'DataManager'.
- Isso desacopla a lógica dos comandos do método de armazenamento, facilitando
  a manutenção e futuras migrações (ex: para SQLite).
"""

# --- 1. Imports ---
import logging
import json
import random
from datetime import time, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, Union

import discord
from discord.ext import commands, tasks

# --- 2. Configuração e Constantes ---
# Usando logging, como definido no main.py
log = logging.getLogger(__name__)

# Usando pathlib para uma manipulação de caminhos mais robusta e legível
# __file__ -> economia.py | .parent -> /cogs | .parent -> diretório raiz
DIRETORIO_RAIZ = Path(__file__).parent.parent
ARQUIVO_ECONOMIA = DIRETORIO_RAIZ / "economia.json"

# IDs de canais e outras configurações deveriam ficar em um arquivo de config,
# mas por enquanto, constantes são uma boa prática.
CANAL_ANUNCIOS_ID = 1406712065061687447
TAXA_JUROS = 0.02
TAXA_IMPOSTO_RIQUEZA = 0.01

# --- 3. Camada de Acesso a Dados (Data Access Layer) ---

class DataManager:
    """
    Gerencia todas as operações de leitura e escrita do banco de dados (JSON).
    Isola a lógica de I/O do resto do cog.
    """
    def __init__(self, bot: commands.Bot, file_path: Path):
        self.bot = bot
        self.path = file_path
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        """Garante que o arquivo JSON exista, criando um vazio se necessário."""
        if not self.path.exists():
            log.warning(f"Arquivo de economia não encontrado. Criando um novo em: {self.path}")
            self.path.write_text("{}", encoding='utf-8')

    def _default_user_schema(self) -> Dict[str, Any]:
        """Retorna a estrutura padrão para um novo usuário."""
        return {
            "carteira": 500,
            "banco": 0,
            "acoes": {},
            "cc_stats": {
                "jogos": 0,
                "vitorias": 0,
                "total_apostado": 0,
                "lucro_total": 0
            }
        }

    async def _load_data(self) -> Dict[str, Any]:
        """Lê os dados do arquivo JSON de forma assíncrona."""
        # O lock aqui é menos crucial para leitura, mas garante consistência
        # se uma escrita estiver acontecendo.
        async with self.bot.economy_lock:
            try:
                with open(self.path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                log.error("Arquivo de economia corrompido ou não encontrado. Retornando dados vazios.")
                return {}

    async def _save_data(self, data: Dict[str, Any]) -> None:
        """Salva os dados no arquivo JSON de forma assíncrona."""
        async with self.bot.economy_lock:
            with open(self.path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)

    async def get_user_data(self, user_id: int) -> Dict[str, Any]:
        """
        Obtém os dados de um usuário. Cria a conta se não existir.
        Esta função substitui a necessidade de chamar 'abrir_conta' em cada comando.
        """
        user_id_str = str(user_id)
        dados = await self._load_data()
        
        if user_id_str not in dados:
            log.info(f"Criando nova conta para o usuário ID: {user_id_str}")
            dados[user_id_str] = self._default_user_schema()
            await self._save_data(dados)
        
        # Garante que chaves mais recentes sejam adicionadas a usuários antigos
        user_needs_update = False
        for key, value in self._default_user_schema().items():
            if key not in dados[user_id_str]:
                dados[user_id_str][key] = value
                user_needs_update = True
        
        if user_needs_update:
            await self._save_data(dados)

        return dados[user_id_str]

    async def update_balance(self, user_id: int, amount: float, account: str = 'carteira') -> bool:
        """
        Atualiza o saldo de um usuário em uma conta específica ('carteira' ou 'banco').
        Pode receber valores positivos ou negativos.
        """
        user_id_str = str(user_id)
        dados = await self._load_data()

        # Garante que a conta existe antes de atualizar
        if user_id_str not in dados:
            dados[user_id_str] = self._default_user_schema()

        if account in dados[user_id_str]:
            dados[user_id_str][account] += amount
            await self._save_data(dados)
            return True
        return False
    
    async def get_all_data(self) -> Dict[str, Any]:
        """Retorna todos os dados para operações em massa (rank, evento diário)."""
        return await self._load_data()

    async def save_all_data(self, data: Dict[str, Any]) -> None:
        """Salva a estrutura de dados completa. Usado por operações em massa."""
        await self._save_data(data)


# --- 4. O Cog de Economia ---

class Economia(commands.Cog):
    """Cog para o sistema de economia do bot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data_manager = DataManager(bot, ARQUIVO_ECONOMIA)
        self.evento_economico_diario.start()

    # --- Funções Auxiliares (Helpers) ---

    def _format_brl(self, valor: Union[int, float]) -> str:
        """Formata um número para o padrão de moeda brasileiro. Usa um fallback robusto."""
        # O locale foi movido para o main.py e sua configuração é global.
        # Aqui, apenas tentamos usá-lo.
        try:
            import locale
            locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
            return locale.currency(float(valor), grouping=True, symbol="R$")
        except (ValueError, TypeError, ImportError, locale.Error):
            # Fallback manual caso o locale não esteja disponível no sistema
            try:
                a = f'{float(valor):,.2f}'
                b = a.replace(',', 'v').replace('.', ',').replace('v', '.')
                return f"R$ {b}"
            except (ValueError, TypeError):
                return "R$ 0,00"

    async def _parse_amount(self, ctx: commands.Context, balance: float, amount_str: str) -> int:
        """
        Converte o argumento de quantia (ex: '100', 'tudo') em um inteiro.
        Envia mensagens de erro diretamente ao contexto.
        """
        if amount_str.lower() in ['tudo', 'all']:
            return int(balance)
        
        try:
            amount = int(amount_str)
            if amount <= 0:
                await ctx.send("A quantia deve ser um número positivo!")
                return None
            return amount
        except ValueError:
            await ctx.send("Por favor, insira um número válido ou 'tudo'.")
            return None

    # --- Tarefa Diária (Daily Task) ---

    @tasks.loop(time=time(hour=18, minute=0, second=0, tzinfo=timezone(timedelta(hours=-3))))
    async def evento_economico_diario(self):
        """Processa juros e impostos para todos os usuários diariamente."""
        log.info("[EVENTO DIÁRIO] Iniciando ciclo de juros e impostos...")
        
        dados = await self.data_manager.get_all_data()
        
        cofre_antes = dados.get("cofre_impostos", 0)
        impostos_diarios = dados.get("impostos_diarios", {})
        impostos_jogos_dia = impostos_diarios.get("jogos", 0)
        impostos_mercado_dia = impostos_diarios.get("mercado", 0)
        
        total_juros_pagos = 0
        total_impostos_riqueza = 0

        ids_usuarios = [user_id for user_id in dados if user_id.isdigit()]
        
        for user_id in ids_usuarios:
            user = dados[user_id]
            banco = user.get("banco", 0)
            carteira = user.get("carteira", 0)

            # 1. Calcular e adicionar juros
            juros = banco * TAXA_JUROS
            user["banco"] += juros
            total_juros_pagos += juros

            # 2. Calcular imposto sobre a riqueza total
            riqueza_total = user["banco"] + carteira
            imposto = riqueza_total * TAXA_IMPOSTO_RIQUEZA
            total_impostos_riqueza += imposto

            # 3. Deduzir imposto (primeiro da carteira, depois do banco)
            if carteira >= imposto:
                user["carteira"] -= imposto
            else:
                imposto_restante = imposto - carteira
                user["carteira"] = 0
                user["banco"] -= imposto_restante
            
            # Truncar para valores inteiros (representando centavos, se preferir)
            user["carteira"] = int(user["carteira"])
            user["banco"] = int(user["banco"])

        # Atualizar cofre e zerar contadores diários
        dados["cofre_impostos"] = int(cofre_antes + total_impostos_riqueza)
        dados["impostos_diarios"] = {"jogos": 0, "mercado": 0}
        
        await self.data_manager.save_all_data(dados)
        log.info(f"[EVENTO DIÁRIO] Ciclo concluído. Juros pagos: {total_juros_pagos}, Impostos de Riqueza: {total_impostos_riqueza}")

        # Anunciar no canal
        canal = self.bot.get_channel(CANAL_ANUNCIOS_ID)
        if canal:
            impostos_totais_dia = impostos_jogos_dia + impostos_mercado_dia + total_impostos_riqueza
            embed = discord.Embed(
                title="💰 Resumo Econômico Diário 💰",
                description="Juros foram pagos e os impostos do dia foram recolhidos!",
                color=discord.Color.gold()
            )
            embed.add_field(name="Total de Juros Pagos aos Cidadãos", value=f"🟢 `{self._format_brl(total_juros_pagos)}`", inline=False)
            embed.add_field(name="Total de Impostos Arrecadados Hoje", value=f"🔴 `{self._format_brl(impostos_totais_dia)}`", inline=False)
            embed.add_field(name="Saldo Total do Cofre Público", value=f"🏦 `{self._format_brl(dados['cofre_impostos'])}`", inline=False)
            await canal.send(embed=embed)

    @evento_economico_diario.before_loop
    async def before_evento_economico_diario(self):
        await self.bot.wait_until_ready()

    # --- Comandos do Usuário ---

    @commands.command(name="saldo", aliases=["carteira", "bal"], help="Mostra o seu saldo.")
    async def saldo(self, ctx: commands.Context, membro: discord.Member = None):
        membro = membro or ctx.author
        
        user_data = await self.data_manager.get_user_data(membro.id)
        
        embed = discord.Embed(title=f"💰 Saldo de {membro.display_name}", color=discord.Color.green())
        embed.add_field(name="Carteira", value=f"`{self._format_brl(user_data['carteira'])}`", inline=True)
        embed.add_field(name="Banco", value=f"`{self._format_brl(user_data['banco'])}`", inline=True)
        if membro.avatar:
            embed.set_thumbnail(url=membro.avatar.url)
        await ctx.send(embed=embed)

    @commands.cooldown(1, 3600, commands.BucketType.user)
    @commands.command(name="trabalhar", aliases=["work"], help="Trabalhe para ganhar dinheiro.")
    async def trabalhar(self, ctx: commands.Context):
        ganhos = random.randint(100, 500)
        
        await self.data_manager.update_balance(ctx.author.id, ganhos, 'carteira')
        
        embed = discord.Embed(
            title="👨‍💻 Hora do Trabalho!",
            description=f"Você trabalhou e ganhou **{self._format_brl(ganhos)}**!",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    @commands.command(name="depositar", aliases=["dep"], help="Deposita dinheiro no banco.")
    async def depositar(self, ctx: commands.Context, quantia_str: str):
        user_data = await self.data_manager.get_user_data(ctx.author.id)
        saldo_carteira = user_data.get('carteira', 0)
        
        quantia = await self._parse_amount(ctx, saldo_carteira, quantia_str)
        if quantia is None: return

        if saldo_carteira < quantia:
            await ctx.send("Você não tem dinheiro suficiente na carteira para depositar essa quantia.")
            return

        await self.data_manager.update_balance(ctx.author.id, -quantia, 'carteira')
        await self.data_manager.update_balance(ctx.author.id, quantia, 'banco')

        embed = discord.Embed(
            title="🏦 Depósito Realizado",
            description=f"Você depositou **{self._format_brl(quantia)}** no banco.",
            color=discord.Color.blurple()
        )
        await ctx.send(embed=embed)

    @commands.command(name="sacar", aliases=["saque"], help="Saca dinheiro do banco.")
    async def sacar(self, ctx: commands.Context, quantia_str: str):
        user_data = await self.data_manager.get_user_data(ctx.author.id)
        saldo_banco = user_data.get('banco', 0)
        
        quantia = await self._parse_amount(ctx, saldo_banco, quantia_str)
        if quantia is None:
            return

        if saldo_banco < quantia:
            await ctx.send("Você não tem dinheiro suficiente no banco para sacar essa quantia.")
            return

        # Realiza a transação de forma atômica (embora com JSON seja simulado)
        await self.data_manager.update_balance(ctx.author.id, quantia, 'carteira')
        await self.data_manager.update_balance(ctx.author.id, -quantia, 'banco')

        embed = discord.Embed(
            title="💵 Saque Realizado",
            description=f"Você sacou **{self._format_brl(quantia)}** do banco.",
            color=discord.Color.dark_teal()
        )
        await ctx.send(embed=embed)

    @commands.command(name="pagar", aliases=["pay", "pix"], help="Transfere dinheiro para outro membro.")
    async def pagar(self, ctx: commands.Context, receptor: discord.Member, quantia: int):
        pagador = ctx.author

        if receptor.bot or pagador == receptor:
            await ctx.send("Você não pode transferir dinheiro para si mesmo ou para um bot.")
            return
        if quantia <= 0:
            await ctx.send("A quantia a ser paga deve ser positiva!")
            return

        dados_pagador = await self.data_manager.get_user_data(pagador.id)
        if dados_pagador['carteira'] < quantia:
            await ctx.send(f"Você não tem dinheiro suficiente na carteira para fazer essa transferência!")
            return
        
        # Garante que a conta do receptor exista antes da transferência
        await self.data_manager.get_user_data(receptor.id)

        # Realiza a transação
        await self.data_manager.update_balance(pagador.id, -quantia, 'carteira')
        await self.data_manager.update_balance(receptor.id, quantia, 'carteira')

        embed = discord.Embed(
            title="💸 Transferência Realizada!",
            description=f"**{pagador.display_name}** transferiu **{self._format_brl(quantia)}** para **{receptor.display_name}**.",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed)

    @commands.cooldown(1, 300, commands.BucketType.user)
    @commands.command(name="roubar", help="Tente roubar de outro membro.")
    async def roubar(self, ctx: commands.Context, alvo: discord.Member):
        autor = ctx.author
        
        if alvo.bot or alvo == autor:
            await ctx.send("Você não pode roubar a si mesmo ou a um bot.")
            return

        dados_autor = await self.data_manager.get_user_data(autor.id)
        dados_alvo = await self.data_manager.get_user_data(alvo.id)

        saldo_carteira_alvo = dados_alvo.get("carteira", 0)
        saldo_carteira_autor = dados_autor.get("carteira", 0)

        # Validações
        if saldo_carteira_alvo < 200:
            await ctx.send(f"{alvo.display_name} é pobre demais para valer o risco do roubo (precisa ter no mínimo {self._format_brl(200)}).")
            return
        if saldo_carteira_autor < 100:
            await ctx.send(f"Você precisa de pelo menos {self._format_brl(100)} na carteira para tentar um roubo e arcar com a possível multa.")
            return
        
        # Lógica do Roubo (40% de chance de sucesso)
        if random.randint(1, 100) <= 40:
            # Sucesso
            quantia_roubada = int(saldo_carteira_alvo * random.uniform(0.10, 0.50))
            await self.data_manager.update_balance(autor.id, quantia_roubada, 'carteira')
            await self.data_manager.update_balance(alvo.id, -quantia_roubada, 'carteira')
            embed = discord.Embed(
                title="🏴‍☠️ Roubo Bem-Sucedido!",
                description=f"Você foi sorrateiro e roubou **{self._format_brl(quantia_roubada)}** de {alvo.mention}!",
                color=discord.Color.dark_green()
            )
        else:
            # Falha
            multa = int(saldo_carteira_autor * random.uniform(0.05, 0.20))
            await self.data_manager.update_balance(autor.id, -multa, 'carteira')
            embed = discord.Embed(
                title="🚨 Falha no Roubo!",
                description=f"Você foi apanhado! Para escapar, você pagou uma multa de **{self._format_brl(multa)}**.",
                color=discord.Color.dark_red()
            )
            
        await ctx.send(embed=embed)

    @commands.command(name="topricos", aliases=["rank", "top"], help="Mostra o ranking dos mais ricos.")
    async def topricos(self, ctx: commands.Context):
        todos_os_dados = await self.data_manager.get_all_data()

        dados_usuarios = {
            user_id: data for user_id, data in todos_os_dados.items() 
            if user_id.isdigit()
        }

        if not dados_usuarios:
            await ctx.send("Ainda não há ninguém no ranking para exibir!")
            return

        ranking_ordenado = sorted(
            dados_usuarios.items(),
            key=lambda item: item[1].get('carteira', 0) + item[1].get('banco', 0),
            reverse=True
        )
        
        limite_exibicao = min(5, len(ranking_ordenado))

        # 1. Começamos a descrição com o cabeçalho
        descricao_final = f"Top {limite_exibicao} membros com a maior riqueza (Carteira + Banco):\n"

        # 2. Criamos uma lista de strings, uma para cada jogador
        linhas_do_ranking = []
        for i, (id_usuario, dados_usuario) in enumerate(ranking_ordenado[:limite_exibicao]):
            try:
                membro = await self.bot.fetch_user(int(id_usuario))
                nome_membro = membro.name
            except discord.NotFound:
                nome_membro = f"Ex-Membro ({id_usuario[-4:]})"
            
            carteira = dados_usuario.get('carteira', 0)
            banco = dados_usuario.get('banco', 0)
            total = carteira + banco

            if i == 0: prefixo = "🥇"
            elif i == 1: prefixo = "🥈"
            elif i == 2: prefixo = "🥉"
            else: prefixo = f"{i + 1}"

            valor_total_fmt = self._format_brl(total)
            valor_carteira_fmt = self._format_brl(carteira)
            valor_banco_fmt = self._format_brl(banco)
            
            # Monta o bloco de texto para cada usuário
            bloco_usuario = (
                f"**{prefixo}. {nome_membro}**\n"
                f"**``{valor_total_fmt}`` (Total)**\n"
                f"└ Carteira: ``{valor_carteira_fmt}``\n"
                f"└ Banco: ``{valor_banco_fmt}``"
            )
            linhas_do_ranking.append(bloco_usuario)

        # 3. Juntamos tudo na descrição principal, separado por uma linha em branco
        descricao_final += "\n\n".join(linhas_do_ranking)
        
        # 4. Criamos o embed final apenas com a descrição
        embed = discord.Embed(
            title="🏆 Ranking de Riqueza Total 🏆",
            description=descricao_final,
            color=discord.Color.gold() # Voltando para a cor dourada, mais padrão
        )

        await ctx.send(embed=embed)

async def setup(bot: commands.Bot):
    """Função de entrada para carregar o Cog."""
    await bot.add_cog(Economia(bot))
