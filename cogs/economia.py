import discord
from discord.ext import commands, tasks
import json
import os
import random
import asyncio
import locale
from datetime import time, timezone, timedelta

# --- CAMINHO DE FICHEIRO CORRIGIDO E ROBUSTO ---
DIRETORIO_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQUIVO_ECONOMIA = os.path.join(DIRETORIO_RAIZ, "economia.json")

# --- CONFIGURAÇÃO ---
CANAL_ANUNCIOS_ID = 1406712065061687447 # Certifique-se de que este ID de canal está correto

class Economia(commands.Cog):
    """Cog para o sistema de economia do bot."""

    def __init__(self, bot):
        self.bot = bot
        self.carregar_dados_iniciais()
        self.evento_economico_diario.start()

    def format_brl(self, valor):
        """Formata um número para o padrão de moeda brasileiro."""
        try:
            return locale.currency(float(valor), grouping=True, symbol="R$")
        except (ValueError, TypeError, locale.Error):
            try:
                a = f'{float(valor):,.2f}'
                b = a.replace(',', 'v').replace('.', ',').replace('v', '.')
                return f"R$ {b}"
            except (ValueError, TypeError):
                return "R$ 0,00"

    def carregar_dados_iniciais(self):
        if not os.path.exists(ARQUIVO_ECONOMIA):
            with open(ARQUIVO_ECONOMIA, 'w', encoding='utf-8') as f: json.dump({}, f)

    async def carregar_dados(self):
        if not os.path.exists(ARQUIVO_ECONOMIA) or os.path.getsize(ARQUIVO_ECONOMIA) == 0:
            return {}
        with open(ARQUIVO_ECONOMIA, 'r', encoding='utf-8') as f:
            return json.load(f)

    async def salvar_dados(self, dados):
        with open(ARQUIVO_ECONOMIA, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=4)

    async def abrir_conta(self, usuario: discord.Member):
        dados = await self.carregar_dados()
        id_usuario = str(usuario.id)
        precisa_salvar = False
        if id_usuario not in dados:
            dados[id_usuario] = {"carteira": 500, "banco": 0}
            precisa_salvar = True
        chaves_padrao = {"acoes": {}, "cc_stats": {"jogos": 0, "vitorias": 0, "total_apostado": 0, "lucro_total": 0}}
        for chave, valor_padrao in chaves_padrao.items():
            if chave not in dados[id_usuario]:
                dados[id_usuario][chave] = valor_padrao
                precisa_salvar = True
        if precisa_salvar:
            await self.salvar_dados(dados)

    @tasks.loop(time=time(hour=3, minute=0, second=0, tzinfo=timezone(timedelta(hours=-3))))
    async def evento_economico_diario(self):
        dados_para_anuncio = {}
        async with self.bot.economy_lock:
            print("\n--- [EVENTO DIÁRIO] Iniciando ciclo de juros e impostos... ---")
            dados = await self.carregar_dados()
            cofre_antes = dados.get("cofre_impostos", 0)
            impostos_diarios = dados.get("impostos_diarios", {})
            impostos_jogos_dia = impostos_diarios.get("jogos", 0); impostos_mercado_dia = impostos_diarios.get("mercado", 0)
            total_juros = 0; impostos_riqueza = 0
            ids_usuarios = [id_ for id_ in dados if id_.isdigit()]
            for id_usuario in ids_usuarios:
                banco = dados[id_usuario].get("banco", 0); juros = banco * 0.02
                dados[id_usuario]["banco"] = banco + juros; total_juros += juros
                carteira = dados[id_usuario].get("carteira", 0); riqueza = carteira + dados[id_usuario]["banco"]
                imposto = riqueza * 0.01; impostos_riqueza += imposto
                if carteira >= imposto: dados[id_usuario]["carteira"] -= imposto
                else: imp_restante = imposto - carteira; dados[id_usuario]["carteira"] = 0; dados[id_usuario]["banco"] -= imp_restante
                c_antiga = dados[id_usuario]["carteira"]; b_antigo = dados[id_usuario]["banco"]
                dados[id_usuario]["carteira"] = int(c_antiga); dados[id_usuario]["banco"] = int(b_antigo)
                centavos = (c_antiga - dados[id_usuario]["carteira"]) + (b_antigo - dados[id_usuario]["banco"])
                impostos_riqueza += centavos
            dados["cofre_impostos"] = cofre_antes + impostos_riqueza
            dados["impostos_diarios"] = {"jogos": 0, "mercado": 0}
            await self.salvar_dados(dados)
            dados_para_anuncio = {"total_juros": total_juros, "impostos_jogos": impostos_jogos_dia, "impostos_mercado": impostos_mercado_dia, "impostos_riqueza": impostos_riqueza, "cofre_final": dados["cofre_impostos"]}
        
        if dados_para_anuncio:
            canal = self.bot.get_channel(CANAL_ANUNCIOS_ID)
            if canal:
                impostos_totais_dia = dados_para_anuncio["impostos_jogos"] + dados_para_anuncio["impostos_mercado"] + dados_para_anuncio["impostos_riqueza"]
                embed = discord.Embed(title="💰 Resumo Económico Diário 💰", description="Juros pagos e impostos recolhidos!", color=discord.Color.gold())
                embed.add_field(name="Total de Juros Pagos", value=f"🟢 `{self.format_brl(dados_para_anuncio['total_juros'])}`", inline=False)
                embed.add_field(name="Total de Impostos Arrecadados Hoje", value=f"🔴 `{self.format_brl(impostos_totais_dia)}`", inline=False)
                embed.add_field(name="Saldo Total do Cofre Público", value=f"🏦 `{self.format_brl(dados_para_anuncio['cofre_final'])}`", inline=False)
                await canal.send(embed=embed)
        print(f"--- [EVENTO DIÁRIO] Ciclo concluído. ---")

    @evento_economico_diario.before_loop
    async def before_evento_economico_diario(self):
        await self.bot.wait_until_ready()

    @commands.command(name="saldo", aliases=["carteira", "bal"], help="Mostra o seu saldo.")
    async def saldo(self, ctx, membro: discord.Member = None):
        if membro is None: membro = ctx.author
        # Apenas ler dados não precisa estritamente do lock, mas abrir conta sim
        async with self.bot.economy_lock:
            await self.abrir_conta(membro)
            dados = await self.carregar_dados()
        id_usuario = str(membro.id)
        saldo_carteira = dados[id_usuario].get("carteira", 0); saldo_banco = dados[id_usuario].get("banco", 0)
        embed = discord.Embed(title=f"💰 Saldo de {membro.display_name}", color=discord.Color.green())
        embed.add_field(name="Carteira", value=f"`{self.format_brl(saldo_carteira)}`", inline=True); embed.add_field(name="Banco", value=f"`{self.format_brl(saldo_banco)}`", inline=True)
        embed.set_thumbnail(url=membro.avatar.url)
        await ctx.send(embed=embed)

    @commands.cooldown(1, 3600, commands.BucketType.user)
    @commands.command(name="trabalhar", aliases=["work"], help="Trabalhe para ganhar dinheiro.")
    async def trabalhar(self, ctx):
        ganhos = random.randint(100, 500)
        async with self.bot.economy_lock:
            await self.abrir_conta(ctx.author)
            dados = await self.carregar_dados()
            dados[str(ctx.author.id)]["carteira"] = dados[str(ctx.author.id)].get("carteira", 0) + ganhos
            await self.salvar_dados(dados)
        embed = discord.Embed(title="👨‍💻 Hora do Trabalho!", description=f"Você ganhou **{self.format_brl(ganhos)}**!", color=discord.Color.blue())
        await ctx.send(embed=embed)

    @commands.cooldown(1, 86400, commands.BucketType.user)
    @commands.command(name="diario", aliases=["daily"], help="Receba sua recompensa diária.")
    async def diario(self, ctx):
        recompensa = 200
        async with self.bot.economy_lock:
            await self.abrir_conta(ctx.author)
            dados = await self.carregar_dados()
            dados[str(ctx.author.id)]["carteira"] = dados[str(ctx.author.id)].get("carteira", 0) + recompensa
            await self.salvar_dados(dados)
        embed = discord.Embed(title="🎁 Recompensa Diária!", description=f"Você coletou a recompensa diária de **{self.format_brl(recompensa)}**!", color=discord.Color.magenta())
        await ctx.send(embed=embed)

    @commands.cooldown(1, 300, commands.BucketType.user)
    @commands.command(name="roubar", help="Tente roubar de outro membro.")
    async def roubar(self, ctx, alvo: discord.Member):
        autor = ctx.author; embed = None
        if alvo.bot or alvo == autor: await ctx.send("Ação inválida."); return
        async with self.bot.economy_lock:
            await self.abrir_conta(autor); await self.abrir_conta(alvo)
            dados = await self.carregar_dados()
            id_autor = str(autor.id); id_alvo = str(alvo.id)
            saldo_alvo = dados[id_alvo].get("carteira", 0); saldo_autor = dados[id_autor].get("carteira", 0)
            if saldo_alvo < 200: await ctx.send(f"{alvo.display_name} é pobre demais."); return
            if saldo_autor < 100: await ctx.send(f"Você precisa de pelo menos {self.format_brl(100)} para tentar."); return
            if random.randint(1, 100) <= 40:
                quantia = int(saldo_alvo * random.uniform(0.10, 0.50))
                dados[id_alvo]["carteira"] -= quantia; dados[id_autor]["carteira"] += quantia
                embed = discord.Embed(title="🏴‍☠️ Roubo Bem-Sucedido!", description=f"Você roubou **{self.format_brl(quantia)}** de {alvo.mention}!", color=discord.Color.dark_green())
            else:
                multa = int(saldo_autor * random.uniform(0.05, 0.20))
                dados[id_autor]["carteira"] -= multa
                embed = discord.Embed(title="🚨 Falha no Roubo!", description=f"Você foi apanhado e pagou uma multa de **{self.format_brl(multa)}**.", color=discord.Color.dark_red())
            await self.salvar_dados(dados)
        if embed: await ctx.send(embed=embed)

    @commands.command(name="pagar", aliases=["pay", "pix"], help="Transfere dinheiro para outro membro.")
    async def pagar(self, ctx, receptor: discord.Member, quantia: int):
        pagador = ctx.author
        if receptor.bot or pagador == receptor or quantia <= 0: await ctx.send("Ação inválida."); return
        async with self.bot.economy_lock:
            await self.abrir_conta(pagador); await self.abrir_conta(receptor)
            dados = await self.carregar_dados()
            id_pagador, id_receptor = str(pagador.id), str(receptor.id)
            if dados[id_pagador].get("carteira", 0) < quantia: await ctx.send(f"Você não tem dinheiro suficiente!"); return
            dados[id_pagador]["carteira"] -= quantia; dados[id_receptor]["carteira"] = dados[id_receptor].get("carteira", 0) + quantia
            await self.salvar_dados(dados)
        embed = discord.Embed(title="💸 Transferência Realizada!", description=f"**{pagador.display_name}** transferiu **{self.format_brl(quantia)}** para **{receptor.display_name}**.", color=discord.Color.gold())
        await ctx.send(embed=embed)

    @commands.command(name="topricos", aliases=["rank", "top"], help="Mostra o ranking dos mais ricos.")
    async def topricos(self, ctx):
        dados = await self.carregar_dados()
        dados_usuarios = {k: v for k, v in dados.items() if k.isdigit()}
        if len(dados_usuarios) < 1: await ctx.send("Ninguém no ranking ainda!"); return
        ranking_ordenado = sorted(dados_usuarios.items(), key=lambda i: i[1].get('carteira', 0) + i[1].get('banco', 0), reverse=True)
        embed = discord.Embed(title="🏆 Ranking de Riqueza Total 🏆", description="Top 5 membros com a maior riqueza (Carteira + Banco):", color=discord.Color.gold())
        for i, (id_usuario, d_usuario) in enumerate(ranking_ordenado[:5]):
            try: membro = await ctx.guild.fetch_member(int(id_usuario)); nome_membro = membro.display_name
            except discord.NotFound: nome_membro = f"Membro Desconhecido ({id_usuario[-4:]})"
            carteira = d_usuario.get('carteira', 0); banco = d_usuario.get('banco', 0); total = carteira + banco
            prefixo = f"{i + 1}."
            if i == 0: prefixo = "🥇."
            elif i == 1: prefixo = "🥈."
            elif i == 2: prefixo = "🥉."
            valor_fmt = f"**`{self.format_brl(total)}` (Total)**"
            if carteira > 0: valor_fmt += f"\n└ `Carteira:` {self.format_brl(carteira)}"
            if banco > 0: valor_fmt += f"\n└ `Banco:` {self.format_brl(banco)}"
            embed.add_field(name=f"{prefixo} {nome_membro}", value=valor_fmt, inline=False)
        await ctx.send(embed=embed)

    @commands.command(name="depositar", aliases=["dep"], help="Deposita dinheiro no banco.")
    async def depositar(self, ctx, quantia: str):
        async with self.bot.economy_lock:
            await self.abrir_conta(ctx.author); dados = await self.carregar_dados()
            id_usuario, saldo_carteira = str(ctx.author.id), dados[str(ctx.author.id)].get("carteira", 0)
            if quantia.lower() in ['tudo', 'all']: quantia_a_depositar = saldo_carteira
            else:
                try: quantia_a_depositar = int(quantia)
                except ValueError: await ctx.send("Insira um número válido ou 'tudo'."); return
            if quantia_a_depositar <= 0: await ctx.send("A quantia deve ser positiva!"); return
            if saldo_carteira < quantia_a_depositar: await ctx.send("Você não tem dinheiro suficiente."); return
            dados[id_usuario]["carteira"] -= quantia_a_depositar; dados[id_usuario]["banco"] = dados[id_usuario].get("banco", 0) + quantia_a_depositar
            await self.salvar_dados(dados)
        embed = discord.Embed(title="🏦 Depósito Realizado", description=f"Você depositou **{self.format_brl(quantia_a_depositar)}** no banco.", color=discord.Color.blurple())
        await ctx.send(embed=embed)

    @commands.command(name="sacar", aliases=["saque"], help="Saca dinheiro do banco.")
    async def sacar(self, ctx, quantia: str):
        async with self.bot.economy_lock:
            await self.abrir_conta(ctx.author); dados = await self.carregar_dados()
            id_usuario, saldo_banco = str(ctx.author.id), dados[str(ctx.author.id)].get("banco", 0)
            if quantia.lower() in ['tudo', 'all']: quantia_a_sacar = saldo_banco
            else:
                try: quantia_a_sacar = int(quantia)
                except ValueError: await ctx.send("Insira um número válido ou 'tudo'."); return
            if quantia_a_sacar <= 0: await ctx.send("A quantia deve ser positiva!"); return
            if saldo_banco < quantia_a_sacar: await ctx.send("Você não tem dinheiro suficiente no banco."); return
            dados[id_usuario]["banco"] -= quantia_a_sacar; dados[id_usuario]["carteira"] = dados[id_usuario].get("carteira", 0) + quantia_a_sacar
            await self.salvar_dados(dados)
        embed = discord.Embed(title="💵 Saque Realizado", description=f"Você sacou **{self.format_brl(quantia_a_sacar)}** do banco.", color=discord.Color.dark_teal())
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Economia(bot))