import logging
from typing import List

import discord
from discord.ext import commands

# Importa a calculadora do novo módulo de utilidades com o nome corrigido
from cogs._utilidades import SafeCalculator

log = logging.getLogger(__name__)

class Geral(commands.Cog):
    """Cog para comandos gerais e de utilidade."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.calculator = SafeCalculator()

    # --- Classe da View aninhada para encapsulamento ---
    class HelpPaginationView(discord.ui.View):
        def __init__(self, autor_comando: discord.User, embeds: List[discord.Embed]):
            super().__init__(timeout=120.0)
            self.autor_comando = autor_comando
            self.embeds = embeds
            self.current_page = 0
            self._update_buttons()

        async def interaction_check(self, interaction: discord.Interaction) -> bool:
            if interaction.user.id != self.autor_comando.id:
                await interaction.response.send_message("Use o comando `!ajuda` para ver sua própria lista.", ephemeral=True)
                return False
            return True
        
        def _update_buttons(self):
            self.prev_button.disabled = len(self.embeds) <= 1
            self.next_button.disabled = len(self.embeds) <= 1

        async def update_message(self, interaction: discord.Interaction):
            self.embeds[self.current_page].set_footer(text=f"Página {self.current_page + 1} de {len(self.embeds)}")
            await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

        @discord.ui.button(label="Anterior", style=discord.ButtonStyle.secondary, emoji="⬅️")
        async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.current_page = (self.current_page - 1) % len(self.embeds)
            await self.update_message(interaction)

        @discord.ui.button(label="Próximo", style=discord.ButtonStyle.primary, emoji="➡️")
        async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.current_page = (self.current_page + 1) % len(self.embeds)
            await self.update_message(interaction)

    # --- Comandos do Cog ---

    @commands.command(name="ping", help="Verifica a latência do bot.")
    async def ping(self, ctx: commands.Context):
        latency_ms = self.bot.latency * 1000
        await ctx.send(f'Pong! 🏓 Minha latência é de {latency_ms:.2f}ms.')

    def _build_help_pages(self) -> List[discord.Embed]:
        embeds = []
        # Omitir o cog 'Geral' do cálculo para não mostrar a si mesmo
        cogs_a_exibir = [cog_name for cog_name in sorted(self.bot.cogs) if cog_name != "Geral"]

        for cog_name in cogs_a_exibir:
            cog = self.bot.get_cog(cog_name)
            
            public_commands = [cmd for cmd in cog.get_commands() if not cmd.hidden]
            if not public_commands:
                continue

            command_list_str = []
            for command in public_commands:
                aliases = f" (aliases: {', '.join(command.aliases)})" if command.aliases else ""
                command_list_str.append(f"**`!{command.name}`**{aliases}\n* {command.help or 'Sem descrição.'}*")
            
            embed = discord.Embed(
                title=f"📜 Categoria: {cog_name}",
                description="\n\n".join(command_list_str),
                color=discord.Color.blurple()
            )
            embeds.append(embed)
        return embeds

    @commands.command(name="ajuda", aliases=["comandos", "help"], help="Mostra esta mensagem de ajuda.")
    async def ajuda(self, ctx: commands.Context):
        embeds = self._build_help_pages()

        if not embeds:
            return await ctx.send("Não foram encontrados comandos para exibir.")
            
        view = self.HelpPaginationView(ctx.author, embeds)
        
        embeds[0].set_footer(text=f"Página 1 de {len(embeds)}")
        await ctx.send(embed=embeds[0], view=view)
        
    @commands.command(name="calcular", aliases=["calc"], help="Calcula uma expressão matemática.")
    async def calcular(self, ctx: commands.Context, *, expressao: str):
        try:
            resultado = self.calculator.calculate(expressao)
            
            if isinstance(resultado, float) and resultado.is_integer():
                resultado_fmt = str(int(resultado))
            elif isinstance(resultado, float):
                resultado_fmt = f"{resultado:.4f}"
            else:
                resultado_fmt = str(resultado)

            embed = discord.Embed(title="🧮 Calculadora", color=discord.Color.dark_gray())
            embed.add_field(name="Expressão", value=f"```fix\n{expressao}```", inline=False)
            embed.add_field(name="Resultado", value=f"```fix\n{resultado_fmt}```", inline=False)
            await ctx.send(embed=embed)
            
        except (TypeError, SyntaxError, ZeroDivisionError) as e:
            await ctx.send(f"❌ **Erro na expressão:** Expressão matemática inválida ou não suportada.\n`Detalhe: {e}`")
        except Exception as e:
            log.error(f"Erro inesperado na calculadora: {e}", exc_info=True)
            await ctx.send(f"Ocorreu um erro inesperado ao processar o cálculo.")

async def setup(bot: commands.Bot):
    await bot.add_cog(Geral(bot))