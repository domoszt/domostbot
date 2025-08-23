import ast
import operator as op
import locale
from typing import Union

# Dicionário que mapeia nós da AST para funções de operador seguras
_OPERATORS = {
    ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul,
    ast.Div: op.truediv, ast.Pow: op.pow, ast.USub: op.neg
}

class SafeCalculator:
    """
    Uma calculadora que avalia expressões matemáticas de forma segura,
    analisando a Árvore de Sintaxe Abstrata (AST) da expressão.
    """
    def _eval_node(self, node: ast.AST):
        if isinstance(node, ast.Constant):
            return node.n
        elif isinstance(node, ast.BinOp):
            if type(node.op) not in _OPERATORS:
                raise TypeError(f"Operador binário não permitido: {type(node.op).__name__}")
            return _OPERATORS[type(node.op)](self._eval_node(node.left), self._eval_node(node.right))
        elif isinstance(node, ast.UnaryOp):
            if type(node.op) not in _OPERATORS:
                raise TypeError(f"Operador unário não permitido: {type(node.op).__name__}")
            return _OPERATORS[type(node.op)](self._eval_node(node.operand))
        else:
            raise TypeError(f"Operação não permitida: {type(node).__name__}")

    def calculate(self, expression: str) -> float:
        expression = expression.replace('^', '**')
        tree = ast.parse(expression, mode='eval').body
        return self._eval_node(tree)

def format_brl(valor: Union[int, float]) -> str:
    """Formata um número para o padrão de moeda brasileiro. Usa um fallback robusto."""
    try:
        # Tenta usar o locale do sistema para a formatação ideal
        locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
        return locale.currency(float(valor), grouping=True, symbol="R$")
    except (ValueError, TypeError, ImportError, locale.Error):
        # Fallback manual caso o locale não esteja disponível no sistema
        try:
            a = f'{float(valor):,.2f}'
            b = a.replace(',', 'v').replace('.', ',').replace('v', '.')
            return f"R$ {b}"
        except (ValueError, TypeError):
            return "R$ 0,00"