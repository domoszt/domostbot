import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio
import locale
import traceback

# Tenta configurar o locale para pt_BR, mas não quebra o bot se não for suportado
try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except locale.Error:
    print("Aviso: Locale 'pt_BR.UTF-8' não suportado. A usar a formatação de moeda manual.")

# Carrega as variáveis de ambiente do ficheiro .env
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Define as permissões (Intents)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Cria a instância do bot
bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# Cria a "fechadura" de segurança global para os ficheiros de economia
bot.economy_lock = asyncio.Lock()

@bot.event
async def on_ready():
    print(f'Login efetuado com sucesso como {bot.user}!')
    print(f'ID do Bot: {bot.user.id}')
    print('Bot está online e pronto.')
    print('-----------------------------------------')

# --- APANHADOR DE ERROS MESTRE ---
@bot.event
async def on_command_error(ctx, error):
    # Desembrulha o erro original
    causa_original = getattr(error, 'original', error)

    if isinstance(causa_original, commands.CommandOnCooldown):
        minutos, segundos = divmod(causa_original.retry_after, 60)
        tempo_restante = f"{int(minutos)}m {int(segundos)}s"
        embed = discord.Embed(title="✋ Calma aí!", description=f"Você precisa de esperar mais **{tempo_restante}**.", color=discord.Color.orange())
        await ctx.send(embed=embed, delete_after=10)
    
    elif isinstance(causa_original, commands.MissingPermissions):
        await ctx.send(f"❌ {ctx.author.mention}, você não tem permissão para usar este comando!", delete_after=10)
    
    elif isinstance(causa_original, commands.NotOwner):
        await ctx.send(f"❌ Este é um comando especial e só pode ser usado pelo meu criador!", delete_after=10)
    
    elif isinstance(causa_original, commands.CommandNotFound):
        pass # Ignora erros de comando não encontrado
    
    else:
        # Para todos os outros erros, mostra o erro no terminal e avisa o utilizador.
        print(f"Ocorreu um erro inesperado no comando '{ctx.command}':")
        traceback.print_exception(type(causa_original), causa_original, causa_original.__traceback__)
        await ctx.send(f"😵 Ocorreu um erro inesperado ao executar o comando `{ctx.command}`. O meu criador foi notificado (no terminal)!")

async def carregar_cogs():
    """Encontra e carrega todos os cogs na pasta ./cogs"""
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                print(f'Cog "{filename[:-3]}" carregado com sucesso.')
            except Exception as e:
                print(f'Erro ao carregar o Cog "{filename[:-3]}":')
                traceback.print_exc()

async def main():
    async with bot:
        await carregar_cogs()
        await bot.start(TOKEN)

# Ponto de entrada do script
if __name__ == "__main__":
    asyncio.run(main())