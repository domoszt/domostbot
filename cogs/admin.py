import discord
from discord.ext import commands
import locale

class Admin(commands.Cog):
    """Cog para comandos de administração e moderação."""

    def __init__(self, bot):
        self.bot = bot

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

    @commands.command(name="addgrana", help="Adiciona dinheiro a um membro. (Admin)")
    @commands.has_permissions(manage_guild=True)
    async def addgrana(self, ctx, membro: discord.Member, quantia: int):
        economia_cog = self.bot.get_cog('Economia')
        if not economia_cog:
            return await ctx.send("Erro: Módulo de economia não carregado.")
        
        if quantia <= 0:
            await ctx.send("A quantia deve ser um número positivo.")
            return

        # Usa a fechadura de segurança global para modificar os dados
        async with self.bot.economy_lock:
            await economia_cog.abrir_conta(membro)
            dados = await economia_cog.carregar_dados()
            id_membro = str(membro.id)
            dados[id_membro]["carteira"] = dados[id_membro].get("carteira", 0) + quantia
            await economia_cog.salvar_dados(dados)

        await ctx.send(f"✅ Adicionado **{self.format_brl(quantia)}** à carteira de {membro.mention}.")

    @commands.command(name="limpar", aliases=["clear"], help="Limpa mensagens do canal. (Admin)")
    @commands.has_permissions(manage_messages=True)
    async def limpar(self, ctx, limite: int):
        if limite <= 0:
            await ctx.send("O número de mensagens a apagar deve ser positivo.")
            return
        
        # O +1 é para apagar também a mensagem do comando !limpar
        apagadas = await ctx.channel.purge(limit=limite + 1)
        await ctx.send(f"🗑️ `{len(apagadas) - 1}` mensagens foram apagadas por {ctx.author.mention}.", delete_after=5)

    @commands.command(name="reload", help="Recarrega um Cog. (Apenas Dono)")
    @commands.is_owner()
    async def reload(self, ctx, cog_name: str):
        try:
            await self.bot.reload_extension(f"cogs.{cog_name.lower()}")
            await ctx.send(f"✅ O Cog `{cog_name}` foi recarregado com sucesso!")
        except commands.ExtensionNotFound:
            await ctx.send(f"⚠️ O Cog `{cog_name}` não foi encontrado.")
        except Exception as e:
            await ctx.send(f"❌ Ocorreu um erro ao recarregar o Cog `{cog_name}`:\n```py\n{e}\n```")

async def setup(bot):
    await bot.add_cog(Admin(bot))