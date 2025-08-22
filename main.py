# -*- coding: utf-8 -*-

"""
Ponto de entrada principal para o Domost Bot.

Este script é responsável por:
1. Configurar o logging para monitoramento.
2. Carregar variáveis de ambiente (como o token do bot).
3. Definir as intenções (Intents) e inicializar o cliente do bot.
4. Carregar todas as extensões (cogs) da pasta /cogs.
5. Implementar um manipulador de erros global.
6. Iniciar a conexão do bot com a API do Discord.
"""

# --- 1. Imports ---
import asyncio
import logging
import os
import traceback
from typing import NoReturn

import discord
from discord.ext import commands
from dotenv import load_dotenv

# --- 2. Configuração do Logging ---
# Configura o logger para exibir logs no console e em um arquivo.
# Isso é mais robusto que usar 'print()'.
log_formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s')
log_handler = logging.FileHandler(filename='domostbot.log', encoding='utf-8', mode='w')
log_handler.setFormatter(log_formatter)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)

logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)
logger.addHandler(log_handler)
logger.addHandler(stream_handler)


# --- 3. Configuração Inicial do Bot ---

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

if not DISCORD_TOKEN:
    logger.critical("ERRO CRÍTICO: O 'DISCORD_TOKEN' não foi encontrado no ambiente.")
    # Usar exit() aqui é aceitável, pois o bot não pode funcionar sem o token.
    exit("Token não configurado. O bot não pode iniciar.")

# Define as permissões (Intents) necessárias para o bot.
# É uma boa prática solicitar apenas as intents que você realmente precisa.
intents = discord.Intents.default()
intents.message_content = True  # Necessário para ler o conteúdo das mensagens.
intents.members = True          # Necessário para eventos de membros (entrada/saída).


# --- 4. Inicialização do Bot ---

class DomostBot(commands.Bot):
    """Subclasse de commands.Bot para adicionar atributos personalizados."""
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents, help_command=None)
        # O Lock previne condições de corrida ao acessar/modificar
        # recursos compartilhados, como arquivos de economia.
        self.economy_lock = asyncio.Lock()

    async def setup_hook(self) -> None:
        """
        Hook que é chamado após o login, mas antes de se conectar ao WebSocket.
        Ideal para carregar extensões.
        """
        logger.info("Carregando extensões (cogs)...")
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                cog_name = f'cogs.{filename[:-3]}'
                try:
                    await self.load_extension(cog_name)
                    logger.info(f'Cog "{cog_name}" carregado com sucesso.')
                except Exception as e:
                    # Usar exc_info=True anexa o traceback completo ao log.
                    logger.error(f'Erro ao carregar o Cog "{cog_name}".', exc_info=True)
    
    async def on_ready(self) -> None:
        """Evento disparado quando o bot está online e pronto."""
        logger.info(f'Login efetuado com sucesso como {self.user} (ID: {self.user.id})')
        logger.info('Bot está online e pronto.')
        logger.info('-----------------------------------------')


bot = DomostBot()


# --- 5. Manipulador de Erros Global ---

@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError) -> None:
    """
    Manipulador de erros global para todos os comandos.
    Captura, trata e loga os erros, fornecendo feedback ao usuário.
    """
    # Desembrulha o erro original de exceções como commands.CommandInvokeError
    causa_original = getattr(error, 'original', error)

    if isinstance(causa_original, commands.CommandOnCooldown):
        minutos, segundos = divmod(causa_original.retry_after, 60)
        tempo_restante = f"{int(minutos)}m {int(segundos)}s"
        embed = discord.Embed(
            title="✋ Calma aí!",
            description=f"Você precisa esperar mais **{tempo_restante}**.",
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed, delete_after=10)
    
    elif isinstance(causa_original, commands.MissingPermissions):
        await ctx.send(f"❌ {ctx.author.mention}, você não tem permissão para usar este comando!", delete_after=10)
    
    elif isinstance(causa_original, commands.NotOwner):
        await ctx.send("❌ Este é um comando especial e só pode ser usado pelo meu criador!", delete_after=10)
    
    elif isinstance(causa_original, commands.CommandNotFound):
        # Ignora silenciosamente comandos que não existem para evitar poluição no chat.
        return
    
    else:
        # Para todos os outros erros, loga o traceback completo e avisa o usuário.
        logger.error(f"Erro inesperado no comando '{ctx.command}' invocado por '{ctx.author}':", exc_info=causa_original)
        await ctx.send(f"😵 Ocorreu um erro inesperado. A equipe de desenvolvimento já foi notificada!")


# --- 6. Ponto de Entrada Principal ---

async def main() -> None:
    """Função principal para iniciar o bot."""
    async with bot:
        await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot desligado pelo usuário (Ctrl+C).")
    except Exception as e:
        logger.critical("Erro fatal ao iniciar o bot:", exc_info=True)