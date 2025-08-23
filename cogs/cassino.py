# cassino.py (VERSÃO FINAL COMPLETA)

# --- 1. Imports ---
import logging
import random
from typing import Dict, Any, List

import discord
from discord.ext import commands

# --- 2. Setup do Logger ---
log = logging.getLogger(__name__)

# --- 3. Classes de Lógica Pura do Jogo ---

class Card:
    """Representa uma única carta de baralho."""
    def __init__(self, rank: str, suit: str):
        self.rank = rank
        self.suit = suit
        self.value = self._get_value()

    def _get_value(self) -> int:
        if self.rank in ['J', 'Q', 'K']: return 10
        if self.rank == 'A': return 11
        return int(self.rank)

    def __str__(self) -> str:
        emojis = {'Paus': '♣️', 'Ouros': '♦️', 'Copas': '♥️', 'Espadas': '♠️'}
        return f"[`{self.rank}{emojis[self.suit]}`]"

class Deck:
    """Representa um baralho de cartas que pode ser embaralhado."""
    def __init__(self):
        suits = ['Paus', 'Ouros', 'Copas', 'Espadas']
        ranks = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A']
        self.cards = [Card(rank, suit) for rank in ranks for suit in suits]
        self.shuffle()

    def shuffle(self): random.shuffle(self.cards)
    def deal(self) -> Card: return self.cards.pop()

class Hand:
    """Representa a mão de um jogador, com cálculo de pontos."""
    def __init__(self): self.cards: List[Card] = []

    @property
    def points(self) -> int:
        total = sum(card.value for card in self.cards)
        num_aces = sum(1 for card in self.cards if card.rank == 'A')
        while total > 21 and num_aces > 0:
            total -= 10
            num_aces -= 1
        return total

    def add_card(self, card: Card): self.cards.append(card)
    def __str__(self) -> str: return ' '.join(str(card) for card in self.cards)

class BlackjackPvEGame:
    """Contém o estado e a lógica para uma única partida de Blackjack PvE."""
    def __init__(self, player: discord.Member, bet: int):
        self.player, self.bet, self.deck = player, bet, Deck()
        self.player_hand, self.dealer_hand = Hand(), Hand()
        self.is_finished, self.status, self.payout = False, "", 0
        for _ in range(2): self.player_hand.add_card(self.deck.deal()); self.dealer_hand.add_card(self.deck.deal())

    def hit(self):
        if self.is_finished: return
        self.player_hand.add_card(self.deck.deal())
        if self.player_hand.points > 21: self.stand()

    def stand(self):
        if self.is_finished: return
        while self.dealer_hand.points < 17: self.dealer_hand.add_card(self.deck.deal())
        self._determine_winner()

    def _determine_winner(self):
        p_pts, d_pts = self.player_hand.points, self.dealer_hand.points
        p_bj = p_pts == 21 and len(self.player_hand.cards) == 2
        d_bj = d_pts == 21 and len(self.dealer_hand.cards) == 2
        if p_bj and not d_bj: self.status, self.payout = "Blackjack! Você ganhou!", int(self.bet * 2.5)
        elif p_pts > 21: self.status, self.payout = f"Você estourou com {p_pts} pontos! Você perdeu.", 0
        elif d_bj and not p_bj: self.status, self.payout = "A Casa fez um Blackjack! Você perdeu.", 0
        elif d_pts > 21: self.status, self.payout = f"A Casa estourou com {d_pts} pontos! Você ganhou!", self.bet * 2
        elif p_pts > d_pts: self.status, self.payout = f"Você ganhou com {p_pts} contra {d_pts}!", self.bet * 2
        elif d_pts > p_pts: self.status, self.payout = f"Você perdeu com {p_pts} contra {d_pts}!", 0
        else: self.status, self.payout = f"Empate com {p_pts} pontos! Aposta devolvida.", self.bet
        self.is_finished = True

class BlackjackPvPGame:
    """Contém o estado e a lógica para uma única partida de Blackjack PvP."""
    def __init__(self, player1: discord.Member, player2: discord.Member, bet: int):
        self.players = {player1.id: player1, player2.id: player2}
        self.bet, self.pot, self.deck = bet, bet * 2, Deck()
        self.hands = {p_id: Hand() for p_id in self.players.keys()}
        self.turn_of, self.players_who_stood = player1.id, []
        self.is_finished, self.status, self.winner_id = False, "", None
        for _ in range(2):
            for p_id in self.players: self.hands[p_id].add_card(self.deck.deal())

    def get_opponent_id(self, p_id: int) -> int: return [pid for pid in self.players if pid != p_id][0]

    def hit(self, p_id: int):
        if self.is_finished or p_id != self.turn_of: return
        self.hands[p_id].add_card(self.deck.deal())
        if self.hands[p_id].points > 21: self.stand(p_id)

    def stand(self, p_id: int):
        if self.is_finished or p_id != self.turn_of: return
        self.players_who_stood.append(p_id)
        opponent_id = self.get_opponent_id(p_id)
        if opponent_id not in self.players_who_stood: self.turn_of = opponent_id
        else: self._determine_winner()

    def _determine_winner(self):
        p1_id, p2_id = self.players.keys()
        p1, p2 = self.players[p1_id], self.players[p2_id]
        p1_pts, p2_pts = self.hands[p1_id].points, self.hands[p2_id].points
        if p1_pts > 21 and p2_pts > 21: self.status, self.winner_id = "Ambos estouraram! A aposta vai para o cofre.", None
        elif p1_pts > 21: self.status, self.winner_id = f"{p1.display_name} estourou! **{p2.display_name} ganhou!**", p2_id
        elif p2_pts > 21: self.status, self.winner_id = f"{p2.display_name} estourou! **{p1.display_name} ganhou!**", p1_id
        elif p1_pts > p2_pts: self.status, self.winner_id = f"**{p1.display_name} ganhou** com {p1_pts} contra {p2_pts}!", p1_id
        elif p2_pts > p1_pts: self.status, self.winner_id = f"**{p2.display_name} ganhou** com {p2_pts} contra {p1_pts}!", p2_id
        else: self.status, self.winner_id = f"Empate com {p1_pts} pontos! O dinheiro foi devolvido.", 0
        self.is_finished = True

class GameManager:
    """Gerencia o ciclo de vida de todos os jogos ativos."""
    def __init__(self): self.active_games: Dict[int, Any] = {}
    def start_pve_game(self, p, b) -> BlackjackPvEGame: self.active_games[p.id] = g = BlackjackPvEGame(p, b); return g
    def start_pvp_game(self, p1, p2, b, msg_id) -> BlackjackPvPGame: self.active_games[msg_id] = g = BlackjackPvPGame(p1, p2, b); return g
    def get_game(self, g_id: int) -> Any: return self.active_games.get(g_id)
    def end_game(self, g_id: int):
        if g_id in self.active_games: del self.active_games[g_id]

        # --- 4. Views (Interface do Usuário) ---

class BlackjackView_PvE(discord.ui.View):
    def __init__(self, game: BlackjackPvEGame, cog: 'Cassino'):
        super().__init__(timeout=120.0)
        self.game = game
        self.cog = cog
        self.message: discord.Message = None

    async def on_timeout(self):
        # Evita chamar o handler se o jogo já terminou normalmente
        if not self.game.is_finished:
            await self.cog.handle_timeout_pve(self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.game.player.id:
            await interaction.response.send_message("Este não é o seu jogo!", ephemeral=True)
            return False
        return True
    
    def disable_buttons(self):
        for item in self.children:
            item.disabled = True

    async def update_message(self, interaction: discord.Interaction):
        """Função centralizada para atualizar a mensagem do jogo."""
        embed = self.cog.create_embed_pve(self.game)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Pedir Carta", style=discord.ButtonStyle.primary, emoji="➕")
    async def hit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.game.hit()
        if self.game.is_finished:
            await self.cog.finalize_game_pve(interaction, self)
        else:
            await self.update_message(interaction)

    @discord.ui.button(label="Parar", style=discord.ButtonStyle.success, emoji="✋")
    async def stand_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.game.stand()
        await self.cog.finalize_game_pve(interaction, self)

class ChallengeView(discord.ui.View):
    def __init__(self, desafiado_id: int):
        super().__init__(timeout=180.0)
        self.desafiado_id = desafiado_id
        self.accepted = None # Pode ser True, False ou None (timeout)
    async def interaction_check(self, i: discord.Interaction) -> bool:
        if i.user.id != self.desafiado_id:
            await i.response.send_message("Este desafio não é para si!", ephemeral=True)
            return False
        return True
    @discord.ui.button(label="Aceitar", style=discord.ButtonStyle.success, emoji="✅")
    async def accept(self, i: discord.Interaction, b: discord.ui.Button):
        self.accepted = True
        self.stop()
    @discord.ui.button(label="Recusar", style=discord.ButtonStyle.danger, emoji="✖️")
    async def decline(self, i: discord.Interaction, b: discord.ui.Button):
        self.accepted = False
        self.stop()

class PVPBlackjackView(discord.ui.View):
    def __init__(self, game: BlackjackPvPGame, cog: 'Cassino'):
        super().__init__(timeout=180.0)
        self.game = game; self.cog = cog; self.message: discord.Message = None
    async def on_timeout(self):
        if not self.game.is_finished:
            await self.cog.handle_timeout_pvp(self)
    async def interaction_check(self, i: discord.Interaction) -> bool:
        if i.user.id not in self.game.players: await i.response.send_message("Este não é o seu jogo!", ephemeral=True); return False
        if i.user.id != self.game.turn_of: await i.response.send_message("Não é a sua vez de jogar!", ephemeral=True); return False
        return True
    def disable_buttons(self):
        for item in self.children: item.disabled = True
    async def update_message(self, i: discord.Interaction, content: str = None):
        embed = self.cog.create_embed_pvp(self.game)
        await i.response.edit_message(content=content, embed=embed, view=self)
    @discord.ui.button(label="Pedir Carta", style=discord.ButtonStyle.primary, emoji="➕")
    async def hit(self, i: discord.Interaction, b: discord.ui.Button):
        self.game.hit(i.user.id)
        if self.game.is_finished: await self.cog.finalize_game_pvp(i, self)
        else: await self.update_message(i, content=f"É a vez de {self.game.players[self.game.turn_of].mention}!")
    @discord.ui.button(label="Parar", style=discord.ButtonStyle.success, emoji="✋")
    async def stand(self, i: discord.Interaction, b: discord.ui.Button):
        self.game.stand(i.user.id)
        if self.game.is_finished: await self.cog.finalize_game_pvp(i, self)
        else: await self.update_message(i, content=f"É a vez de {self.game.players[self.game.turn_of].mention}!")

# --- 5. O Cog Principal ---

class Cassino(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot, self.game_manager, self.data_manager = bot, GameManager(), None
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Garante que o DataManager da Economia seja carregado."""
        economia_cog = self.bot.get_cog('Economia')
        if economia_cog and hasattr(economia_cog, 'data_manager'):
            self.data_manager = economia_cog.data_manager
            log.info("Cog 'Cassino' carregado e conectado ao DataManager da Economia.")
        else:
            log.error("O Cog 'Cassino' não conseguiu encontrar o DataManager da Economia. A funcionalidade será limitada.")

    def format_brl(self, valor):
        try:
            import locale
            locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
            return locale.currency(float(valor), grouping=True, symbol="R$")
        except:
            try:
                a = f'{float(valor):,.2f}'
                b = a.replace(',', 'v').replace('.', ',').replace('v', '.')
                return f"R$ {b}"
            except:
                return "R$ 0,00"
        
    # --- Lógica de Finalização e Timeouts ---
    async def finalize_game_pve(self, interaction: discord.Interaction, view: BlackjackView_PvE):
        game = view.game; view.disable_buttons()
        if game.payout > 0:
            await self.data_manager.update_balance(game.player.id, game.payout, 'carteira')
        self.game_manager.end_game(game.player.id)
        await view.update_message(interaction)
        log.info(f"Jogo de Blackjack PvE finalizado para {game.player.name}. Resultado: {game.status}")

    async def finalize_game_pvp(self, interaction: discord.Interaction, view: PVPBlackjackView):
        game = view.game; view.disable_buttons()
        # Pagar vencedor ou devolver em caso de empate
        if game.winner_id is not None and game.winner_id != 0:
            await self.data_manager.update_balance(game.winner_id, game.pot)
        elif game.winner_id == 0: # Empate
            for p_id in game.players: await self.data_manager.update_balance(p_id, game.bet)
        # Lógica para cofre público se ambos estourarem
        elif game.winner_id is None:
            dados = await self.data_manager.get_all_data()
            dados["cofre_impostos"] = dados.get("cofre_impostos", 0) + game.pot
            await self.data_manager.save_all_data(dados)

        await view.update_message(interaction, content="**Fim de Jogo!**")
        self.game_manager.end_game(view.message.id)
        log.info(f"Jogo de Blackjack PvP finalizado. Vencedor ID: {game.winner_id}")

    async def handle_timeout_pve(self, view: BlackjackView_PvE):
        game = view.game; view.disable_buttons()
        log.warning(f"Jogo de Blackjack PvE para {game.player.name} expirou (timeout).")
        # Neste caso, a aposta já foi debitada e é perdida.
        embed = discord.Embed(title="🎲 Jogo Terminado 🎲", description=f"Jogo cancelado por inatividade. A aposta de {self.format_brl(game.bet)} foi perdida.", color=discord.Color.dark_grey())
        if view.message: await view.message.edit(embed=embed, view=view)
        self.game_manager.end_game(game.player.id)

    async def handle_timeout_pvp(self, view: PVPBlackjackView):
        game = view.game; view.disable_buttons()
        log.warning("Jogo de Blackjack PvP expirou (timeout).")
        # Regra de negócio: em timeout de PvP, o dinheiro é devolvido
        for p_id in game.players:
            await self.data_manager.update_balance(p_id, game.bet)
        embed = self.create_embed_pvp(game, status_override="Jogo cancelado por inatividade. As apostas foram devolvidas.")
        if view.message: await view.message.edit(content=None, embed=embed, view=view)
        self.game_manager.end_game(view.message.id)

    # --- Métodos para Criar Embeds ---
    def create_embed_pve(self, game: BlackjackPvEGame) -> discord.Embed:
        status = game.status or "É a sua vez de jogar!"
        cor = discord.Color.dark_green()
        if game.is_finished:
            if game.payout > game.bet: cor = discord.Color.green()
            elif game.payout == 0: cor = discord.Color.red()
            elif game.payout == game.bet: cor = discord.Color.light_grey()
            if "Blackjack" in game.status: cor = discord.Color.gold()
        embed = discord.Embed(title="🎲 Jogo de Blackjack 🎲", description=f"**Aposta:** {self.format_brl(game.bet)}\n**Status:** {status}", color=cor)
        embed.add_field(name=f"{game.player.display_name} ({game.player_hand.points} pontos)", value=str(game.player_hand), inline=False)
        if game.is_finished: embed.add_field(name=f"Casa ({game.dealer_hand.points} pontos)", value=str(game.dealer_hand), inline=False)
        else: embed.add_field(name=f"Casa ({game.dealer_hand.cards[0].value}+ pontos)", value=f"{str(game.dealer_hand.cards[0])} [`?`]", inline=False)
        return embed

    def create_embed_pvp(self, game: BlackjackPvPGame, status_override: str = None) -> discord.Embed:
        desc = f"**Pote Total:** {self.format_brl(game.pot)}\n\n"
        if status_override: desc += f"**Resultado:** {status_override}"
        elif game.is_finished: desc += f"**Resultado:** {game.status}"
        else: desc += f"É a vez de **{game.players[game.turn_of].mention}** jogar."
        embed = discord.Embed(title="⚔️ Blackjack 1 vs 1 ⚔️", description=desc, color=discord.Color.blurple())
        for p_id, p_obj in game.players.items():
            mao, pontos = game.hands[p_id], game.hands[p_id].points
            if game.is_finished or p_id == game.turn_of or p_id in game.players_who_stood:
                val, nome = str(mao), f"{p_obj.display_name} ({pontos} pontos)"
            else:
                val, nome = f"{str(mao.cards[0])} [`?`]", f"{p_obj.display_name} ({mao.cards[0].value}+ pontos)"
            embed.add_field(name=nome, value=val, inline=False)
        return embed

    # --- Comandos do Cog ---
    @commands.command(name="blackjack", aliases=["bj"], help="Inicia um jogo de Vinte e Um contra a casa.")
    async def blackjack(self, ctx: commands.Context, aposta_str: str):
        if self.game_manager.get_game(ctx.author.id):
            return await ctx.send("Você já está em uma partida!", delete_after=10)
        if not self.data_manager:
            return await ctx.send("O sistema de economia não está disponível no momento.")
        user_data = await self.data_manager.get_user_data(ctx.author.id)
        saldo_carteira = user_data.get("carteira", 0)
        try:
            aposta = int(aposta_str) if aposta_str.lower() not in ['all', 'tudo'] else int(saldo_carteira)
        except ValueError: return await ctx.send("❌ Aposta inválida. Use um número ou 'all'.")
        if aposta <= 0: return await ctx.send("A aposta deve ser positiva.")
        if saldo_carteira < aposta: return await ctx.send(f"Você não tem dinheiro suficiente! Saldo: {self.format_brl(saldo_carteira)}")
        
        await self.data_manager.update_balance(ctx.author.id, -aposta, 'carteira')
        game = self.game_manager.start_pve_game(ctx.author, aposta)
        view = BlackjackView_PvE(game, self)
        embed = self.create_embed_pve(game)
        msg = await ctx.send(embed=embed, view=view)
        view.message = msg
        if game.player_hand.points == 21:
            game.stand()
            await self.finalize_game_pve(await self.bot.get_context(msg), view)

    @commands.command(name="bjdesafio", help="Desafia outro membro para um jogo de Blackjack 1v1.")
    async def bjdesafio(self, ctx: commands.Context, oponente: discord.Member, aposta_str: str):
        desafiante = ctx.author
        if oponente.bot or oponente == desafiante: return await ctx.send("Desafio inválido.")
        if self.game_manager.get_game(desafiante.id) or self.game_manager.get_game(oponente.id): return await ctx.send("Um dos jogadores já está numa partida.")
        if not self.data_manager: return await ctx.send("O sistema de economia não está disponível no momento.")

        dados_desafiante = await self.data_manager.get_user_data(desafiante.id)
        saldo_desafiante = dados_desafiante.get("carteira", 0)
        try:
            aposta = int(aposta_str) if aposta_str.lower() not in ['all', 'tudo'] else int(saldo_desafiante)
        except ValueError: return await ctx.send("❌ Aposta inválida. Use um número ou 'all'.")
        if aposta <= 0: return await ctx.send("A aposta deve ser positiva.")
        if saldo_desafiante < aposta: return await ctx.send(f"Você não tem {self.format_brl(aposta)} para apostar!")

        view_desafio = ChallengeView(oponente.id)
        embed_desafio = discord.Embed(title="⚔️ Desafio de Blackjack! ⚔️", description=f"{desafiante.mention} desafiou {oponente.mention} para uma partida valendo **{self.format_brl(aposta)}**!", color=discord.Color.orange())
        embed_desafio.set_footer(text=f"{oponente.display_name}, você tem 3 minutos para responder.")
        msg_desafio = await ctx.send(content=oponente.mention, embed=embed_desafio, view=view_desafio)
        await view_desafio.wait()

        if view_desafio.accepted is None:
            embed_desafio.description = "O desafio expirou."; embed_desafio.color = discord.Color.dark_grey()
            return await msg_desafio.edit(content=None, embed=embed_desafio, view=None)
        elif not view_desafio.accepted:
            embed_desafio.description = f"✖️ {oponente.mention} **RECUSOU** o desafio."; embed_desafio.color = discord.Color.red()
            return await msg_desafio.edit(content=None, embed=embed_desafio, view=None)

        dados_oponente = await self.data_manager.get_user_data(oponente.id)
        if dados_oponente.get("carteira", 0) < aposta:
            embed_desafio.description = f"{oponente.mention} não tem dinheiro suficiente para aceitar a aposta."; embed_desafio.color = discord.Color.red()
            return await msg_desafio.edit(content=None, embed=embed_desafio, view=None)

        await self.data_manager.update_balance(desafiante.id, -aposta)
        await self.data_manager.update_balance(oponente.id, -aposta)

        game = self.game_manager.start_pvp_game(desafiante, oponente, aposta, msg_desafio.id)
        view_pvp = PVPBlackjackView(game, self)
        view_pvp.message = msg_desafio
        
        embed_jogo = self.create_embed_pvp(game)
        await msg_desafio.edit(content=f"Desafio aceito! É a vez de {desafiante.mention}!", embed=embed_jogo, view=view_pvp)

async def setup(bot: commands.Bot):
    await bot.add_cog(Cassino(bot))