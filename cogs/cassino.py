import discord
from discord.ext import commands
import random
import locale
import os
import json
import asyncio

# --- CAMINHO DE FICHEIRO CORRIGIDO E ROBUSTO ---
DIRETORIO_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQUIVO_ECONOMIA = os.path.join(DIRETORIO_RAIZ, "economia.json")

class BlackjackView(discord.ui.View):
    def __init__(self, autor_do_jogo, blackjack_cog):
        super().__init__(timeout=120.0)
        self.autor_do_jogo = autor_do_jogo
        self.blackjack_cog = blackjack_cog

    async def on_timeout(self):
        id_usuario = str(self.autor_do_jogo.id)
        if id_usuario in self.blackjack_cog.jogos_em_andamento:
            jogo = self.blackjack_cog.jogos_em_andamento[id_usuario]
            if jogo and jogo.get("mensagem_jogo"):
                embed = discord.Embed(title="🎲 Jogo de Blackjack 🎲", description="Jogo cancelado por inatividade.", color=discord.Color.dark_grey())
                self.desativar_botoes()
                await jogo["mensagem_jogo"].edit(embed=embed, view=self)
            if id_usuario in self.blackjack_cog.jogos_em_andamento:
                del self.blackjack_cog.jogos_em_andamento[id_usuario]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.autor_do_jogo.id:
            await interaction.response.send_message("Este não é o seu jogo! Use `!bj` para iniciar o seu.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Pedir Carta", style=discord.ButtonStyle.primary, emoji="➕")
    async def hit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.blackjack_cog.acao_pedir_carta(interaction, self)

    @discord.ui.button(label="Parar", style=discord.ButtonStyle.success, emoji="✋")
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.desativar_botoes()
        await self.blackjack_cog.acao_parar(interaction, self)

    def desativar_botoes(self):
        for item in self.children:
            item.disabled = True

class Cassino(commands.Cog):
    """Cog para todos os jogos de cassino e apostas."""

    def __init__(self, bot):
        self.bot = bot
        self.jogos_em_andamento = {}
        self.naipes = ['Paus', 'Ouros', 'Copas', 'Espadas']; self.ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        self.valores_cartas = {'2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10, 'J': 10, 'Q': 10, 'K': 10, 'A': 11}

    def format_brl(self, valor):
        """Formata um número para o padrão de moeda brasileiro."""
        try:
            return locale.currency(float(valor), grouping=True, symbol="R$")
        except (ValueError, TypeError, locale.Error):
            try:
                a = f'{float(valor):,.2f}'; b = a.replace(',', 'v').replace('.', ',').replace('v', '.'); return f"R$ {b}"
            except (ValueError, TypeError): return "R$ 0,00"

    async def carregar_dados_economia(self):
        if not os.path.exists(ARQUIVO_ECONOMIA) or os.path.getsize(ARQUIVO_ECONOMIA) == 0: return {}
        with open(ARQUIVO_ECONOMIA, 'r', encoding='utf-8') as f: return json.load(f)

    async def salvar_dados_economia(self, dados):
        with open(ARQUIVO_ECONOMIA, 'w', encoding='utf-8') as f: json.dump(dados, f, indent=4)

    def criar_baralho(self):
        baralho = [{'rank': r, 'naipe': n} for r in self.ranks for n in self.naipes]; random.shuffle(baralho); return baralho

    def calcular_pontos(self, mao):
        pontos = sum(self.valores_cartas[c['rank']] for c in mao)
        num_ases = sum(1 for c in mao if c['rank'] == 'A')
        while pontos > 21 and num_ases: pontos -= 10; num_ases -= 1
        return pontos

    def formatar_mao(self, mao):
        emojis = {'Paus': '♣️', 'Ouros': '♦️', 'Copas': '♥️', 'Espadas': '♠️'}
        return ' '.join([f"[`{c['rank']}{emojis[c['naipe']]}`]" for c in mao])

    @commands.command(name="blackjack", aliases=["bj"], help="Inicia um jogo de Vinte e Um.")
    async def blackjack(self, ctx, aposta_str: str):
        id_usuario = str(ctx.author.id)
        if id_usuario in self.jogos_em_andamento:
            await ctx.send("Você já tem um jogo em andamento! Finalize o jogo e/ou espere os botões sumirem.", delete_after=10); return
        
        async with self.bot.economy_lock:
            economia_cog = self.bot.get_cog('Economia')
            if not economia_cog: return await ctx.send("Erro fatal: Módulo de economia não encontrado.")
            await economia_cog.abrir_conta(ctx.author)
            dados = await self.carregar_dados_economia()
        
        saldo_carteira = dados.get(id_usuario, {}).get("carteira", 0)
        
        if aposta_str.lower() in ['all', 'allin', 'tudo']: aposta = saldo_carteira
        else:
            try: aposta = int(aposta_str)
            except ValueError: await ctx.send("❌ Aposta inválida. Use um número ou 'all'."); return
        
        if aposta <= 0: await ctx.send("A aposta deve ser positiva."); return
        if saldo_carteira < aposta: await ctx.send(f"Você não tem dinheiro suficiente! Saldo: {self.format_brl(saldo_carteira)}"); return
        
        baralho = self.criar_baralho()
        mao_jogador = [baralho.pop(), baralho.pop()]
        mao_casa = [baralho.pop(), baralho.pop()]
        
        self.jogos_em_andamento[id_usuario] = {"aposta": aposta, "baralho": baralho, "mao_jogador": mao_jogador, "mao_casa": mao_casa, "mensagem_jogo": None}
        
        view = BlackjackView(ctx.author, self)
        embed = self.criar_embed_jogo(ctx.author, "É a sua vez de jogar!")
        
        mensagem_jogo = await ctx.send(embed=embed, view=view)
        self.jogos_em_andamento[id_usuario]["mensagem_jogo"] = mensagem_jogo
        
        if self.calcular_pontos(mao_jogador) == 21:
            await self.finalizar_jogo(ctx.author, view, "blackjack_jogador")

    @blackjack.error
    async def blackjack_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("❓ Uso correto: `!bj <quantia>` ou `!bj all`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("❌ Aposta inválida. Use um número inteiro ou 'all'.")
        else: raise error

    async def acao_pedir_carta(self, interaction: discord.Interaction, view: BlackjackView):
        id_usuario = str(interaction.user.id); jogo = self.jogos_em_andamento[id_usuario]
        jogo["mao_jogador"].append(jogo["baralho"].pop())
        
        embed = self.criar_embed_jogo(interaction.user, "Você pediu uma carta. E agora?")
        await interaction.response.edit_message(embed=embed, view=view)

        if self.calcular_pontos(jogo["mao_jogador"]) > 21:
            await self.finalizar_jogo(interaction.user, view, "jogador_estourou")

    async def acao_parar(self, interaction: discord.Interaction, view: BlackjackView):
        await interaction.response.defer()
        await self.finalizar_jogo(interaction.user, view)

    async def finalizar_jogo(self, autor, view, resultado_forçado=None):
        id_usuario = str(autor.id)
        if id_usuario not in self.jogos_em_andamento: return
        
        jogo = self.jogos_em_andamento[id_usuario]
        view.desativar_botoes()
        
        mao_jogador = jogo["mao_jogador"]; mao_casa = jogo["mao_casa"]
        pontos_jogador = self.calcular_pontos(mao_jogador)
        
        if not resultado_forçado:
            pontos_casa = self.calcular_pontos(mao_casa)
            while pontos_casa < 17:
                mao_casa.append(jogo["baralho"].pop()); pontos_casa = self.calcular_pontos(mao_casa)
        
        resultado, valor_final = self.determinar_vencedor(pontos_jogador, self.calcular_pontos(mao_casa), jogo['aposta'], mao_jogador, mao_casa, resultado_forçado)
        
        async with self.bot.economy_lock:
            dados = await self.carregar_dados_economia()
            dados[id_usuario]["carteira"] = dados[id_usuario].get("carteira", 0) + valor_final
            await self.salvar_dados_economia(dados)
        
        embed = self.criar_embed_jogo(autor, resultado, final=True)
        await jogo["mensagem_jogo"].edit(embed=embed, view=view)
        
        await asyncio.sleep(15)
        
        if id_usuario in self.jogos_em_andamento:
            await jogo["mensagem_jogo"].edit(view=None)
            del self.jogos_em_andamento[id_usuario]

    def determinar_vencedor(self, pontos_jogador, pontos_casa, aposta, mao_jogador, mao_casa, resultado_forçado=None):
        if resultado_forçado == "jogador_estourou":
            return f"Você estourou com {pontos_jogador} pontos! Você perdeu.", -aposta
        
        blackjack_jogador = pontos_jogador == 21 and len(mao_jogador) == 2
        blackjack_casa = pontos_casa == 21 and len(mao_casa) == 2
        
        if resultado_forçado == "blackjack_jogador" or (blackjack_jogador and not blackjack_casa):
            return "Blackjack! Você ganhou!", int(aposta * 1.5)
        if blackjack_casa and not blackjack_jogador:
            return "A Casa fez um Blackjack! Você perdeu.", -aposta
        if pontos_casa > 21:
            return f"A Casa estourou com {pontos_casa} pontos! Você ganhou!", aposta
        if pontos_jogador > pontos_casa:
            return f"Você ganhou com {pontos_jogador} contra {pontos_casa}!", aposta
        if pontos_jogador < pontos_casa:
            return f"Você perdeu com {pontos_jogador} contra {pontos_casa}!", -aposta
        else:
            return f"Empate! Ambos com {pontos_jogador} pontos.", 0

    # (Dentro da classe Cassino, em cogs/cassino.py)

    def criar_embed_jogo(self, autor, status, final=False):
        id_usuario = str(autor.id)
        if id_usuario not in self.jogos_em_andamento: return discord.Embed(title="Jogo Terminado")
        
        jogo = self.jogos_em_andamento[id_usuario]
        aposta = jogo["aposta"]; mao_jogador = jogo["mao_jogador"]; mao_casa = jogo["mao_casa"]
        pontos_jogador = self.calcular_pontos(mao_jogador)
        
        # --- LÓGICA DE COR ATUALIZADA ---
        cor = discord.Color.dark_blue() # Cor padrão para o jogo em andamento
        
        status_lower = status.lower()
        if "ganhou" in status_lower or "blackjack!" in status_lower:
            cor = discord.Color.green()
        elif "perdeu" in status_lower or "estourou" in status_lower or "a casa fez um blackjack" in status_lower:
            cor = discord.Color.red()
        elif "empate" in status_lower:
            cor = discord.Color.light_grey()
        
        embed = discord.Embed(title="🎲 Jogo de Blackjack 🎲", description=f"**Aposta:** {self.format_brl(aposta)}\n**Status:** {status}", color=cor)
        embed.add_field(name=f"{autor.display_name} ({pontos_jogador} pontos)", value=self.formatar_mao(mao_jogador), inline=False)
        
        if final:
            embed.add_field(name=f"Casa ({self.calcular_pontos(mao_casa)} pontos)", value=self.formatar_mao(mao_casa), inline=False)
        else:
            embed.add_field(name=f"Casa ({self.calcular_pontos([mao_casa[0]])} pontos)", value=f"{self.formatar_mao([mao_casa[0]])} [`?`]", inline=False)
            
        return embed

async def setup(bot):
    await bot.add_cog(Cassino(bot))