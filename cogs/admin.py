import logging

import discord
from discord.ext import commands

# Importa as ferramentas do nosso módulo de utilidades
from cogs._utilidades import format_brl

log = logging.getLogger(__name__)

class Admin(commands.Cog):
    """Cog para comandos de administração e moderação."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.economia_data_manager = None

    @commands.Cog.listener()
    async def on_ready(self):
        """Obtém a referência para o DataManager do cog de Economia."""
        economia_cog = self.bot.get_cog('Economia')
        if economia_cog and hasattr(economia_cog, 'data_manager'):
            self.economia_data_manager = economia_cog.data_manager
            log.info("Cog 'Admin' conectado ao DataManager da Economia.")
        else:
            log.error("Cog 'Admin' não encontrou o DataManager da Economia. Comandos podem falhar.")

    @commands.command(name="addgrana", help="Adiciona dinheiro a um membro. (Admin)")
    @commands.has_permissions(manage_guild=True)
    async def addgrana(self, ctx: commands.Context, membro: discord.Member, quantia: int):
        if not self.economia_data_manager:
            return await ctx.send("❌ Erro: O sistema de economia não está pronto ou não foi carregado.")
        
        if quantia <= 0:
            return await ctx.send("A quantia deve ser um número positivo.")

        # A lógica agora é uma única chamada ao DataManager, que já é segura.
        # Não precisamos mais do lock ou de chamar "abrir_conta" aqui.
        await self.economia_data_manager.update_balance(membro.id, quantia, 'carteira')

        await ctx.send(f"✅ Adicionado **{format_brl(quantia)}** à carteira de {membro.mention}.")

    @commands.command(name="limpar", aliases=["clear"], help="Limpa mensagens do canal. (Admin)")
    @commands.has_permissions(manage_messages=True)
    async def limpar(self, ctx: commands.Context, limite: int):
        if limite <= 0:
            return await ctx.send("O número de mensagens a apagar deve ser positivo.")
        
        # O +1 é para apagar também a mensagem do comando !limpar
        apagadas = await ctx.channel.purge(limit=limite + 1)
        await ctx.send(f"🗑️ `{len(apagadas) - 1}` mensagens foram apagadas por {ctx.author.mention}.", delete_after=5)

    @commands.command(name="reload", help="Recarrega um Cog. (Apenas Dono)")
    @commands.is_owner()
    async def reload(self, ctx: commands.Context, cog_name: str):
        try:
            # O nome do cog a ser recarregado deve estar no formato 'cogs.nome'
            await self.bot.reload_extension(f"cogs.{cog_name.lower()}")
            await ctx.send(f"✅ O Cog `{cog_name}` foi recarregado com sucesso!")
        except commands.ExtensionNotFound:
            await ctx.send(f"⚠️ O Cog `{cog_name}` não foi encontrado.")
        except Exception as e:
            log.error(f"Erro ao recarregar o cog '{cog_name}':", exc_info=True)
            await ctx.send(f"❌ Ocorreu um erro ao recarregar o Cog `{cog_name}`:\n```py\n{e}\n```")

async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))