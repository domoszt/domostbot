import discord
from discord.ext import commands
import ast
import operator as op

# --- CLASSE DA VIEW COM OS BOTÕES DE PÁGINA ---

class HelpPaginationView(discord.ui.View):
    def __init__(self, autor_comando, embeds):
        super().__init__(timeout=120.0) # Os botões desaparecem após 2 minutos de inatividade
        self.autor_comando = autor_comando
        self.embeds = embeds
        self.current_page = 0
        
        # Desativa os botões se houver apenas uma página
        if len(self.embeds) <= 1:
            self.prev_button.disabled = True
            self.next_button.disabled = True

    # Verifica se a pessoa que clicou é a mesma que pediu o comando
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.autor_comando.id:
            await interaction.response.send_message("Use o comando `!ajuda` para ver a sua própria lista de comandos.", ephemeral=True)
            return False
        return True
    
    # Atualiza a mensagem com o embed da página atual
    async def update_message(self, interaction: discord.Interaction):
        self.embeds[self.current_page].set_footer(text=f"Página {self.current_page + 1} de {len(self.embeds)}")
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

    @discord.ui.button(label="Anterior", style=discord.ButtonStyle.secondary, emoji="⬅️")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page -= 1
        if self.current_page < 0:
            self.current_page = len(self.embeds) - 1 # Volta para a última página
        await self.update_message(interaction)

    @discord.ui.button(label="Próximo", style=discord.ButtonStyle.primary, emoji="➡️")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_page += 1
        if self.current_page >= len(self.embeds):
            self.current_page = 0 # Volta para a primeira página
        await self.update_message(interaction)

# --- Motor da Calculadora Segura ---
operadores_permitidos = {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul,
    ast.Div: op.truediv, ast.Pow: op.pow, ast.USub: op.neg
}

class SafeCalculator:
    # (A lógica da calculadora continua a mesma)
    def eval_expr(self, node):
        if isinstance(node, ast.Constant): return node.n
        elif isinstance(node, ast.BinOp):
            if type(node.op) not in operadores_permitidos: raise TypeError(f"Operador binário não permitido")
            return operadores_permitidos[type(node.op)](self.eval_expr(node.left), self.eval_expr(node.right))
        elif isinstance(node, ast.UnaryOp):
            if type(node.op) not in operadores_permitidos: raise TypeError(f"Operador unário não permitido")
            return operadores_permitidos[type(node.op)](self.eval_expr(node.operand))
        else: raise TypeError(f"Operação não permitida")

    def calculate(self, expression):
        expression = expression.replace('^', '**'); tree = ast.parse(expression, mode='eval').body
        return self.eval_expr(tree)

class Geral(commands.Cog):
    """Cog para comandos gerais e de utilidade."""

    def __init__(self, bot):
        self.bot = bot
        self.calculator = SafeCalculator()

    @commands.command(name="ping", help="Verifica a latência do bot.")
    async def ping(self, ctx):
        latencia = self.bot.latency * 1000
        await ctx.send(f'Pong! 🏓 Minha latência é de {latencia:.2f}ms.')

    # --- COMANDO DE AJUDA ATUALIZADO ---
    @commands.command(name="ajuda", aliases=["comandos", "help"], help="Mostra esta mensagem de ajuda.")
    async def ajuda(self, ctx):
        embeds = []
        # Itera sobre os Cogs por ordem alfabética
        for cog_name in sorted(self.bot.cogs):
            cog = self.bot.get_cog(cog_name)
            comandos_do_cog = cog.get_commands()
            
            lista_de_comandos = []
            for comando in comandos_do_cog:
                if not comando.hidden:
                    aliases_str = f" [{', '.join(comando.aliases)}]" if comando.aliases else ""
                    lista_de_comandos.append(f"`!{comando.name}{aliases_str}` - {comando.help}")
            
            if lista_de_comandos:
                # Cria um Embed para cada Cog (uma página)
                embed = discord.Embed(
                    title=f"📜 Comandos - Categoria: {cog_name}",
                    description="\n".join(lista_de_comandos),
                    color=discord.Color.dark_blue()
                )
                embeds.append(embed)
        
        # Se existirem páginas, envia a primeira com os botões
        if embeds:
            view = HelpPaginationView(ctx.author, embeds)
            embeds[0].set_footer(text=f"Página 1 de {len(embeds)}")
            await ctx.send(embed=embeds[0], view=view)
        else:
            await ctx.send("Não foram encontrados comandos para exibir.")
        
    @commands.command(name="calcular", aliases=["calc"], help="Calcula uma expressão matemática.")
    async def calcular(self, ctx, *, expressao: str):
        try:
            resultado = self.calculator.calculate(expressao)
            if isinstance(resultado, float) and resultado.is_integer(): resultado = int(resultado)
            elif isinstance(resultado, float): resultado = round(resultado, 4)
            embed = discord.Embed(title="🧮 Calculadora", color=discord.Color.dark_gray())
            embed.add_field(name="Expressão", value=f"```fix\n{expressao}```", inline=False)
            embed.add_field(name="Resultado", value=f"```fix\n{resultado}```", inline=False)
            await ctx.send(embed=embed)
        except (TypeError, SyntaxError, ZeroDivisionError) as e:
            await ctx.send(f"❌ **Erro na expressão:** Expressão matemática inválida ou não suportada.\n`Detalhe: {e}`")
        except Exception as e:
            await ctx.send(f"Ocorreu um erro inesperado: `{e}`")

async def setup(bot):
    await bot.add_cog(Geral(bot))