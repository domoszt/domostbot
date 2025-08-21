import discord
from discord.ext import commands
import random
import locale
import os
import json
import asyncio

# Caminho para o ficheiro de economia
DIRETORIO_RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARQUIVO_ECONOMIA = os.path.join(DIRETORIO_RAIZ, "economia.json")

# --- VIEW PARA O DESAFIO DE BLACKJACK ---
class ChallengeView(discord.ui.View):
    def __init__(self, desafiante, desafiado, aposta, cassino_cog):
        super().__init__(timeout=180.0)
        self.desafiante = desafiante
        self.desafiado = desafiado
        self.aposta = aposta
        self.cassino_cog = cassino_cog
        self.accepted = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.desafiado.id:
            await interaction.response.send_message("Este desafio não é para si!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Aceitar", style=discord.ButtonStyle.success, emoji="✅")
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.accepted = True; self.stop()

    @discord.ui.button(label="Recusar", style=discord.ButtonStyle.danger, emoji="✖️")
    async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.accepted = False; self.stop()

# --- VIEW PARA O JOGO 1V1 ---
class PVPBlackjackView(discord.ui.View):
    def __init__(self, jogo_id, cassino_cog):
        super().__init__(timeout=180.0)
        self.jogo_id = jogo_id
        self.cassino_cog = cassino_cog

    async def on_timeout(self):
        await self.cassino_cog.handle_timeout(self.jogo_id, self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        jogo = self.cassino_cog.jogos_em_andamento.get(self.jogo_id)
        if not jogo: return False
        if interaction.user.id not in jogo["jogadores"]:
            await interaction.response.send_message("Este não é o seu jogo!", ephemeral=True)
            return False
        if interaction.user.id != jogo["turno_de"]:
            await interaction.response.send_message("Não é a sua vez de jogar!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Pedir Carta", style=discord.ButtonStyle.primary, emoji="➕")
    async def hit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cassino_cog.pvp_acao_pedir_carta(interaction, self.jogo_id, self)

    @discord.ui.button(label="Parar", style=discord.ButtonStyle.success, emoji="✋")
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cassino_cog.pvp_acao_parar(interaction, self.jogo_id, self)
    
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

    # ... (Funções auxiliares como format_brl, carregar_dados, etc., continuam iguais)
    def format_brl(self, valor):
        try: return locale.currency(float(valor), grouping=True, symbol="R$")
        except:
            try: a = f'{float(valor):,.2f}'; b = a.replace(',', 'v').replace('.', ',').replace('v', '.'); return f"R$ {b}"
            except: return "R$ 0,00"
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

    @commands.command(name="bjdesafio", help="Desafia outro membro para um jogo de Blackjack 1v1.")
    async def bjdesafio(self, ctx, oponente: discord.Member, aposta_str: str):
        desafiante = ctx.author
        if oponente.bot or oponente == desafiante: await ctx.send("Desafio inválido."); return
        if any(g for g in self.jogos_em_andamento.values() if g['jogadores'].get(desafiante.id) or g['jogadores'].get(oponente.id)):
            await ctx.send("Um dos jogadores já está numa partida."); return
        
        economia_cog = self.bot.get_cog('Economia')
        if not economia_cog: return await ctx.send("Erro fatal: Módulo de economia não encontrado.")
        
        async with self.bot.economy_lock:
            await economia_cog.abrir_conta(desafiante); await economia_cog.abrir_conta(oponente)
            dados = await self.carregar_dados_economia()
        
        saldo_desafiante = dados.get(str(desafiante.id), {}).get("carteira", 0)
        
        if aposta_str.lower() in ['all', 'allin', 'tudo']: aposta = saldo_desafiante
        else:
            try: aposta = int(aposta_str)
            except ValueError: await ctx.send("❌ Aposta inválida. Use um número ou 'all'."); return
        
        if aposta <= 0: await ctx.send("A aposta deve ser positiva."); return
        if saldo_desafiante < aposta: await ctx.send(f"Você não tem {self.format_brl(aposta)} para apostar!"); return
        
        view = ChallengeView(desafiante, oponente, aposta, self)
        embed = discord.Embed(title="⚔️ Desafio de Blackjack! ⚔️", description=f"{desafiante.mention} desafiou {oponente.mention} para uma partida valendo **{self.format_brl(aposta)}**!", color=discord.Color.orange())
        embed.set_footer(text=f"{oponente.display_name}, você tem 3 minutos para responder.")
        mensagem_desafio = await ctx.send(content=oponente.mention, embed=embed, view=view)
        await view.wait()

        if view.accepted is None:
            embed.description = "O desafio expirou."; embed.color = discord.Color.dark_grey()
            await mensagem_desafio.edit(content=None, embed=embed, view=None); return
        elif not view.accepted:
            embed.description = f"✖️ {oponente.mention} **RECUSOU** o desafio."; embed.color = discord.Color.red()
            await mensagem_desafio.edit(content=None, embed=embed, view=None); return
        
        async with self.bot.economy_lock:
            dados = await self.carregar_dados_economia()
            if dados.get(str(oponente.id), {}).get("carteira", 0) < aposta:
                embed.description = f"{oponente.mention} não tem dinheiro suficiente para aceitar a aposta."; embed.color = discord.Color.red()
                await mensagem_desafio.edit(content=None, embed=embed, view=None); return
            dados[str(desafiante.id)]["carteira"] -= aposta
            dados[str(oponente.id)]["carteira"] -= aposta
            await self.salvar_dados_economia(dados)

        baralho = self.criar_baralho()
        jogo_id = mensagem_desafio.id
        jogo = {
            "jogadores": {desafiante.id: desafiante, oponente.id: oponente}, "aposta": aposta, "pote": aposta * 2, "baralho": baralho,
            "maos": {desafiante.id: [baralho.pop(), baralho.pop()], oponente.id: [baralho.pop(), baralho.pop()]},
            "turno_de": desafiante.id, "jogadores_pararam": [], "mensagem_jogo": mensagem_desafio
        }
        self.jogos_em_andamento[jogo_id] = jogo
        
        pvp_view = PVPBlackjackView(jogo_id, self)
        embed_jogo = self.criar_embed_pvp(jogo_id)
        await mensagem_desafio.edit(content=f"É a vez de {desafiante.mention}!", embed=embed_jogo, view=pvp_view)

    def criar_embed_pvp(self, jogo_id, status_final=None):
        jogo = self.jogos_em_andamento.get(jogo_id)
        if not jogo: return discord.Embed(title="Jogo Terminado", color=discord.Color.dark_grey())
        
        ids = list(jogo["jogadores"].keys());
        
        cor = discord.Color.blurple(); desc = f"**Pote Total:** {self.format_brl(jogo['pote'])}"
        if status_final:
            desc += f"\n\n**Resultado:** {status_final}"
            if "ganhou" in status_final.lower(): cor = discord.Color.green()
            elif "perdeu" in status_final.lower() or "estourou" in status_final.lower(): cor = discord.Color.red()
            elif "empate" in status_final.lower(): cor = discord.Color.light_grey()
        else:
            jogador_do_turno = jogo["jogadores"].get(jogo["turno_de"])
            if jogador_do_turno: desc += f"\n\nÉ a vez de **{jogador_do_turno.mention}** jogar."

        embed = discord.Embed(title="⚔️ Blackjack 1 vs 1 ⚔️", description=desc, color=cor)
        
        for user_id in ids:
            user = jogo["jogadores"][user_id]; mao = jogo["maos"][user_id]; pontos = self.calcular_pontos(mao)
            
            # --- LÓGICA DE EXIBIÇÃO CORRIGIDA ---
            # Mostra as cartas completas se for o turno do jogador, se ele já parou, ou se o jogo acabou
            if status_final or user_id == jogo["turno_de"] or user_id in jogo["jogadores_pararam"]:
                valor_campo = self.formatar_mao(mao)
                nome_campo = f"Mão de {user.display_name} ({pontos} pontos)"
            else: # Esconde a segunda carta do oponente
                valor_campo = f"{self.formatar_mao([mao[0]])} [`?`]"
                nome_campo = f"Mão de {user.display_name} ({self.calcular_pontos([mao[0]])}+ pontos)"
            embed.add_field(name=nome_campo, value=valor_campo, inline=False)
        return embed

    async def pvp_acao_pedir_carta(self, interaction: discord.Interaction, jogo_id, view):
        jogo = self.jogos_em_andamento.get(jogo_id);
        if not jogo: await interaction.response.edit_message(content="Este jogo já terminou.", view=None, embed=None); return
        
        id_jogador = interaction.user.id; jogo["maos"][id_jogador].append(jogo["baralho"].pop())
        
        if self.calcular_pontos(jogo["maos"][id_jogador]) > 21:
            await self.pvp_acao_parar(interaction, jogo_id, view); return

        embed = self.criar_embed_pvp(jogo_id)
        await interaction.response.edit_message(embed=embed, view=view)

    async def pvp_acao_parar(self, interaction: discord.Interaction, jogo_id, view):
        jogo = self.jogos_em_andamento.get(jogo_id);
        if not jogo: await interaction.response.edit_message(content="Este jogo já terminou.", view=None, embed=None); return

        id_jogador_atual = interaction.user.id
        if id_jogador_atual not in jogo["jogadores_pararam"]:
            jogo["jogadores_pararam"].append(id_jogador_atual)

        outro_jogador_id = [id_ for id_ in jogo["jogadores"] if id_ != id_jogador_atual][0]
        
        if outro_jogador_id not in jogo["jogadores_pararam"]:
            jogo["turno_de"] = outro_jogador_id
            embed = self.criar_embed_pvp(jogo_id)
            outro_jogador = jogo["jogadores"][outro_jogador_id]
            await interaction.response.edit_message(content=f"É a vez de {outro_jogador.mention}!", embed=embed, view=view)
        else:
            await self.finalizar_jogo_pvp(interaction, jogo_id, view)

    async def finalizar_jogo_pvp(self, interaction: discord.Interaction, jogo_id, view):
        if not interaction.response.is_done():
            await interaction.response.defer()
            
        jogo = self.jogos_em_andamento.get(jogo_id);
        if not jogo: return
        
        view.stop(); view.desativar_botoes()
        ids = list(jogo["jogadores"].keys()); p1_id, p2_id = ids[0], ids[1]
        p1, p2 = jogo["jogadores"][p1_id], jogo["jogadores"][p2_id]
        pontos1, pontos2 = self.calcular_pontos(jogo["maos"][p1_id]), self.calcular_pontos(jogo["maos"][p2_id])
        vencedor_id, status_final = None, ""
        
        if pontos1 > 21 and pontos2 > 21: status_final = "Ambos estouraram! A aposta vai para o cofre público."
        elif pontos1 > 21: status_final = f"{p1.display_name} estourou! **{p2.display_name} ganhou!**"; vencedor_id = p2_id
        elif pontos2 > 21: status_final = f"{p2.display_name} estourou! **{p1.display_name} ganhou!**"; vencedor_id = p1_id
        elif pontos1 > pontos2: status_final = f"**{p1.display_name} ganhou** com {pontos1} contra {pontos2}!"; vencedor_id = p1_id
        elif pontos2 > pontos1: status_final = f"**{p2.display_name} ganhou** com {pontos2} contra {pontos1}!"; vencedor_id = p2_id
        else: status_final = f"Empate com {pontos1} pontos! O dinheiro foi devolvido."

        async with self.bot.economy_lock:
            dados = await self.carregar_dados_economia()
            if vencedor_id: dados[str(vencedor_id)]["carteira"] = dados[str(vencedor_id)].get("carteira", 0) + jogo["pote"]
            elif "Empate" in status_final:
                dados[str(p1_id)]["carteira"] += jogo["aposta"]; dados[str(p2_id)]["carteira"] += jogo["aposta"]
            else: dados["cofre_impostos"] = dados.get("cofre_impostos", 0) + jogo["pote"]
            await self.salvar_dados_economia(dados)

        embed = self.criar_embed_pvp(jogo_id, status_final=status_final)
        await jogo["mensagem_jogo"].edit(content=f"**Fim de Jogo!**", embed=embed, view=view)
        
        await asyncio.sleep(20)
        if jogo_id in self.jogos_em_andamento:
            await jogo["mensagem_jogo"].edit(view=None)
            del self.jogos_em_andamento[jogo_id]

    async def handle_timeout(self, jogo_id, view):
        if jogo_id not in self.jogos_em_andamento: return
        jogo = self.jogos_em_andamento.get(jogo_id)
        if not jogo: return
        view.stop()
        ids = list(jogo["jogadores"].keys())
        status_final = "Jogo cancelado por inatividade. O dinheiro foi devolvido."
        async with self.bot.economy_lock:
            dados = await self.carregar_dados_economia()
            dados[str(ids[0])]["carteira"] += jogo["aposta"]; dados[str(ids[1])]["carteira"] += jogo["aposta"]
            await self.salvar_dados_economia(dados)
        embed = self.criar_embed_pvp(jogo_id, status_final=status_final)
        await jogo["mensagem_jogo"].edit(content=None, embed=embed, view=view)
        if jogo_id in self.jogos_em_andamento: del self.jogos_em_andamento[jogo_id]

async def setup(bot):
    await bot.add_cog(Cassino(bot))