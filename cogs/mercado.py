import discord
from discord.ext import commands, tasks
import json
import os
import random
import traceback
import locale
import matplotlib
matplotlib.use('Agg') # Otimização de memória para servidores
import matplotlib.pyplot as plt
from datetime import datetime, timezone, timedelta

# --- CAMINHOS DE FICHEIRO CORRIGIDOS E ROBUSTOS ---
DIRETORIO_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQUIVO_MERCADO = os.path.join(DIRETORIO_RAIZ, "mercado.json")
ARQUIVO_ECONOMIA = os.path.join(DIRETORIO_RAIZ, "economia.json")
ARQUIVO_HISTORICO = os.path.join(DIRETORIO_RAIZ, "historico_mercado.json")

# --- CONFIGURAÇÃO ---
CANAL_ANUNCIOS_MERCADO_ID = 1407388860392144968 # Certifique-se de que este ID de canal está correto

plt.style.use('dark_background')

class Mercado(commands.Cog):
    """Cog para o sistema de bolsa de valores com tendências e gráficos."""

    def __init__(self, bot):
        self.bot = bot
        self.carregar_dados_iniciais_historico()
        self.update_prices.start()

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

    # --- Funções Auxiliares ---
    def carregar_dados_iniciais_historico(self):
        if not os.path.exists(ARQUIVO_HISTORICO):
            with open(ARQUIVO_HISTORICO, 'w', encoding='utf-8') as f: json.dump({}, f)

    async def carregar_dados_mercado(self):
        if not os.path.exists(ARQUIVO_MERCADO) or os.path.getsize(ARQUIVO_MERCADO) == 0: return {}
        with open(ARQUIVO_MERCADO, 'r', encoding='utf-8') as f: return json.load(f)
    async def salvar_dados_mercado(self, dados):
        with open(ARQUIVO_MERCADO, 'w', encoding='utf-8') as f: json.dump(dados, f, indent=4)
    async def carregar_dados_economia(self):
        if not os.path.exists(ARQUIVO_ECONOMIA) or os.path.getsize(ARQUIVO_ECONOMIA) == 0: return {}
        with open(ARQUIVO_ECONOMIA, 'r', encoding='utf-8') as f: return json.load(f)
    async def salvar_dados_economia(self, dados):
        with open(ARQUIVO_ECONOMIA, 'w', encoding='utf-8') as f: json.dump(dados, f, indent=4)
    async def carregar_dados_historico(self):
        if not os.path.exists(ARQUIVO_HISTORICO) or os.path.getsize(ARQUIVO_HISTORICO) == 0: return {}
        with open(ARQUIVO_HISTORICO, 'r', encoding='utf-8') as f: return json.load(f)
    async def salvar_dados_historico(self, dados):
        with open(ARQUIVO_HISTORICO, 'w', encoding='utf-8') as f: json.dump(dados, f, indent=4)

    @tasks.loop(minutes=5)
    async def update_prices(self):
        mercado = await self.carregar_dados_mercado()
        historico = await self.carregar_dados_historico()
        for simbolo in mercado:
            preco_atual = mercado[simbolo]["preco"]; tendencia_atual = mercado[simbolo].get("tendencia", "estavel")
            mercado[simbolo]["preco_anterior"] = preco_atual
            if tendencia_atual == "alta": mudanca_percentual = random.uniform(-0.03, 0.10)
            elif tendencia_atual == "baixa": mudanca_percentual = random.uniform(-0.10, 0.03)
            else: mudanca_percentual = random.uniform(-0.05, 0.05)
            novo_preco = preco_atual * (1 + mudanca_percentual)
            if novo_preco < 1: novo_preco = 1.0
            mercado[simbolo]["preco"] = round(novo_preco, 2)
            if random.randint(1, 4) == 1: mercado[simbolo]["tendencia"] = random.choice(["alta", "baixa", "estavel"])
            if simbolo not in historico: historico[simbolo] = []
            historico[simbolo].append(round(novo_preco, 2))
            if len(historico[simbolo]) > 10: historico[simbolo] = historico[simbolo][-10:]
        await self.salvar_dados_mercado(mercado)
        await self.salvar_dados_historico(historico)
        
        fuso_horario_brasilia = timezone(timedelta(hours=-3))
        hora_atual_br = datetime.now(fuso_horario_brasilia)
        hora_formatada = hora_atual_br.strftime('%H:%M:%S')
        print(f"[Mercado Cog] Preços e histórico atualizados às {hora_formatada} (BRT).")

        canal = self.bot.get_channel(CANAL_ANUNCIOS_MERCADO_ID)
        if canal:
            embed = discord.Embed(title="🔔 Atualização do Mercado!", description="Os preços das ações foram atualizados!", color=discord.Color.blue())
            embed.set_footer(text=f"Última atualização às {hora_formatada} (Horário de Brasília)")
            try:
                await canal.send(embed=embed)
            except Exception as e:
                print(f"Erro ao enviar anúncio do mercado: {e}")

    @update_prices.before_loop
    async def before_update_prices(self):
        await self.bot.wait_until_ready()

    @commands.command(name="mercado", aliases=["acoes", "bolsa"], help="Mostra os preços das ações.")
    async def mercado(self, ctx):
        dados = await self.carregar_dados_mercado()
        embed = discord.Embed(title="📈 Mercado de Ações 📉", description="Cotações em tempo real com tendências.", color=discord.Color.dark_blue())
        for simbolo, info in dados.items():
            preco = info["preco"]; preco_ant = info.get("preco_anterior", preco)
            if preco > preco_ant: emoji = "🔺"
            elif preco < preco_ant: emoji = "🔻"
            else: emoji = "🔸"
            mudanca_pct = ((preco - preco_ant) / preco_ant * 100) if preco_ant > 0 else 0
            embed.add_field(name=f"{emoji} **{info['nome']} ({simbolo})**", value=f"`{self.format_brl(preco)}` (`{mudanca_pct:+.2f}%`)", inline=True)
        embed.set_footer(text="Os preços são atualizados a cada 5 minutos.")
        await ctx.send(embed=embed)

    @commands.command(name="comprar", help="Compra ações de uma empresa.")
    async def comprar(self, ctx, simbolo: str, quantidade: int):
        simbolo_upper = simbolo.upper()
        if quantidade <= 0: await ctx.send("A quantidade deve ser positiva."); return
        async with self.bot.economy_lock:
            mercado = await self.carregar_dados_mercado()
            if simbolo_upper not in mercado:
                await ctx.send(f"A ação `{simbolo_upper}` não existe."); return
            
            economia_cog = self.bot.get_cog('Economia')
            await economia_cog.abrir_conta(ctx.author)
            economia = await self.carregar_dados_economia()
            
            id_usuario = str(ctx.author.id)
            preco_por_acao = mercado[simbolo_upper]["preco"]
            custo_total = preco_por_acao * quantidade
            
            if economia[id_usuario].get("carteira", 0) < custo_total:
                await ctx.send(f"Dinheiro insuficiente! Custo: `{self.format_brl(custo_total)}`."); return
            
            economia[id_usuario]["carteira"] -= custo_total
            portfolio = economia[id_usuario].get("acoes", {})
            if simbolo_upper in portfolio and isinstance(portfolio.get(simbolo_upper), dict):
                qt_antiga = portfolio[simbolo_upper]["quantidade"]; preco_medio_antigo = portfolio[simbolo_upper]["preco_medio_compra"]
                novo_preco_medio = ((qt_antiga * preco_medio_antigo) + (quantidade * preco_por_acao)) / (qt_antiga + quantidade)
                portfolio[simbolo_upper]["quantidade"] += quantidade; portfolio[simbolo_upper]["preco_medio_compra"] = round(novo_preco_medio, 2)
            else:
                portfolio[simbolo_upper] = {"quantidade": quantidade, "preco_medio_compra": preco_por_acao}
            economia[id_usuario]["acoes"] = portfolio
            await self.salvar_dados_economia(economia)
        
        embed = discord.Embed(title="✅ Compra Realizada!", description=f"Você comprou **{quantidade}** ações de **{mercado[simbolo_upper]['nome']}**.", color=discord.Color.brand_green())
        embed.add_field(name="Custo Total", value=f"`{self.format_brl(custo_total)}`"); embed.set_footer(text=f"Preço por ação: {self.format_brl(preco_por_acao)}")
        await ctx.send(embed=embed)

    @commands.command(name="vender", help="Vende ações de uma empresa.")
    async def vender(self, ctx, simbolo: str, quantidade_str: str):
        simbolo_upper = simbolo.upper()
        async with self.bot.economy_lock:
            mercado = await self.carregar_dados_mercado()
            if simbolo_upper not in mercado: await ctx.send(f"A ação `{simbolo_upper}` não existe."); return
            
            economia = await self.carregar_dados_economia()
            id_usuario = str(ctx.author.id)
            portfolio = economia.get(id_usuario, {}).get("acoes", {})
            if simbolo_upper not in portfolio: await ctx.send(f"Você não possui ações da `{simbolo_upper}`."); return
            
            info_acao = portfolio[simbolo_upper]
            if not isinstance(info_acao, dict): await ctx.send(f"Seus dados para a ação `{simbolo_upper}` estão desatualizados."); return
            
            acoes_possuidas = info_acao["quantidade"]
            if quantidade_str.lower() in ['tudo', 'all']: quantidade_a_vender = acoes_possuidas
            else:
                try: quantidade_a_vender = int(quantidade_str)
                except ValueError: await ctx.send("Insira um número válido ou 'tudo'."); return
            
            if quantidade_a_vender <= 0: await ctx.send("A quantidade deve ser positiva."); return
            if acoes_possuidas < quantidade_a_vender: await ctx.send(f"Você só possui {acoes_possuidas} ações."); return
            
            preco_por_acao_venda = mercado[simbolo_upper]["preco"]; preco_medio_compra = info_acao["preco_medio_compra"]
            lucro_total = (preco_por_acao_venda - preco_medio_compra) * quantidade_a_vender
            ganho_bruto = preco_por_acao_venda * quantidade_a_vender; imposto = 0
            
            if lucro_total > 0:
                imposto = lucro_total * 0.05
                economia["cofre_impostos"] = economia.get("cofre_impostos", 0) + imposto
                impostos_diarios = economia.get("impostos_diarios", {}); impostos_diarios["mercado"] = impostos_diarios.get("mercado", 0) + imposto; economia["impostos_diarios"] = impostos_diarios
            
            ganho_liquido = ganho_bruto - imposto
            economia[id_usuario]["carteira"] += ganho_liquido
            portfolio[simbolo_upper]["quantidade"] -= quantidade_a_vender
            if portfolio[simbolo_upper]["quantidade"] == 0: del portfolio[simbolo_upper]
            
            await self.salvar_dados_economia(economia)
        
        embed = discord.Embed(title="💰 Venda Realizada!", description=f"Você vendeu **{quantidade_a_vender}** ações de **{mercado[simbolo_upper]['nome']}**.", color=discord.Color.from_rgb(20, 150, 40))
        footer_text = f"Preço por ação: {self.format_brl(preco_por_acao_venda)}"
        if imposto > 0:
            embed.add_field(name="Total Recebido (Líquido)", value=f"`{self.format_brl(ganho_liquido)}`")
            embed.set_footer(text=f"{footer_text} | Imposto sobre o lucro: {self.format_brl(imposto)}")
        else:
            embed.add_field(name="Total Recebido", value=f"`{self.format_brl(ganho_liquido)}`")
            embed.set_footer(text=footer_text)
        await ctx.send(embed=embed)

    @commands.command(name="portfolio", aliases=["ptf"], help="Mostra as suas ações.")
    async def portfolio(self, ctx, membro: discord.Member = None):
        if membro is None: membro = ctx.author
        async with self.bot.economy_lock:
            economia = await self.carregar_dados_economia()
        mercado = await self.carregar_dados_mercado()
        
        id_usuario = str(membro.id)
        portfolio_usuario = economia.get(id_usuario, {}).get("acoes", {})
        if not portfolio_usuario: await ctx.send(f"{membro.display_name} ainda não possui ações."); return
        
        embed = discord.Embed(title=f"💼 Portfólio de Ações de {membro.display_name}", color=membro.color)
        embed.set_thumbnail(url=membro.avatar.url)
        valor_total_portfolio = 0; investimento_total = 0; acoes_invalidas = 0
        
        for simbolo, info_acao in portfolio_usuario.items():
            if simbolo in mercado and isinstance(info_acao, dict):
                quantidade = info_acao["quantidade"]; preco_compra_medio = info_acao["preco_medio_compra"]; preco_atual = mercado[simbolo]["preco"]
                valor_investido = quantidade * preco_compra_medio; valor_atual_holding = quantidade * preco_atual; lucro_prejuizo = valor_atual_holding - valor_investido
                investimento_total += valor_investido; valor_total_portfolio += valor_atual_holding
                emoji_lucro = "🟢" if lucro_prejuizo >= 0 else "🔴"
                embed.add_field(name=f"{mercado[simbolo]['nome']} ({simbolo})", value=f"**Qt:** `{quantidade}` | **Valor:** `{self.format_brl(valor_atual_holding)}`\n{emoji_lucro} **L/P:** `{self.format_brl(lucro_prejuizo)}`", inline=True)
            else: acoes_invalidas += 1
            
        lucro_total_portfolio = valor_total_portfolio - investimento_total
        emoji_total = "🟢" if lucro_total_portfolio >= 0 else "🔴"
        embed.description = f"**Valor Total Estimado:** `{self.format_brl(valor_total_portfolio)}`\n{emoji_total} **Lucro/Prejuízo Total:** `{self.format_brl(lucro_total_portfolio)}`"
        if acoes_invalidas > 0: embed.set_footer(text=f"Aviso: {acoes_invalidas} tipo(s) de ação no seu portfólio estão com dados desatualizados.")
        await ctx.send(embed=embed)
    
    @commands.command(name="grafico", help="Mostra o gráfico histórico de uma ação.")
    async def grafico(self, ctx, simbolo: str):
        simbolo_upper = simbolo.upper(); mercado = await self.carregar_dados_mercado(); historico = await self.carregar_dados_historico()
        if simbolo_upper not in mercado: await ctx.send(f"A ação `{simbolo_upper}` não existe."); return
        if simbolo_upper not in historico or len(historico[simbolo_upper]) < 2: await ctx.send(f"Ainda não há dados históricos suficientes."); return
        
        precos = historico[simbolo_upper]
        fig, ax = plt.subplots(figsize=(10, 5), dpi=100)
        cor_linha = 'g' if precos[-1] >= precos[0] else 'r'
        ax.plot(precos, color=cor_linha, linewidth=2)
        ax.set_title(f"Histórico de Preços de {mercado[simbolo_upper]['nome']} ({simbolo_upper})", color='white', fontsize=16)
        ax.set_xlabel("Tempo (Atualizações a cada 5 min)", color='gray'); ax.set_ylabel("Preço (R$)", color='gray')
        ax.grid(True, color='gray', linestyle='--', linewidth=0.5, alpha=0.5)
        nome_ficheiro = "grafico.png"; fig.savefig(nome_ficheiro, bbox_inches='tight', transparent=True); plt.close(fig)
        
        file = discord.File(nome_ficheiro, filename="grafico.png")
        embed = discord.Embed(title=f"Análise Gráfica de {simbolo_upper}", description=f"A exibir o histórico das últimas **{len(precos)}** atualizações.", color=discord.Color.green() if cor_linha == 'g' else discord.Color.red())
        embed.set_image(url=f"attachment://{nome_ficheiro}")
        
        await ctx.send(embed=embed, file=file)
        os.remove(nome_ficheiro)

async def setup(bot):
    await bot.add_cog(Mercado(bot))