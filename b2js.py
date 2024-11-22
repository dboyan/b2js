from enum import Enum
from functools import reduce
import sys

from argparse import ArgumentParser
from brewparse import parse_program
from element import Element

class ExprType(Enum):
    RHS_ASSIGN = 1
    ARGS = 2
    RETURN = 3
    INNER = 4
    EAGER = 5

    @classmethod
    def is_toplevel(cls, type):
        return type != ExprType.INNER
    
    @classmethod
    def needs_cache(cls, type):
        return type in [cls.RHS_ASSIGN, cls.ARGS]

class B2JSBase:
    UNARY_OPS = ['neg', '!']
    BINARY_OPS = ['+', '-', '*', '/', '>', '>=', '<', '<=', '&&', '||', '==', '!=']

    def __init__(self):
        self.line_buf: list[str] = []
        self.indent = 0
        self.preamble = ""
        self.fout = None

    def set_output(self, f):
        self.fout = f

    def line_append(self, s: str):
        # if s not in [';', '(', ')', ','] and (self.line_buf and self.line_buf[-1] != '('):
        #     self.line_buf.append(' ')
        self.line_buf.append(s)

    def emit_line(self, block_open=False, block_close=False):
        if block_close:
            self.indent -= 1

        if self.line_buf:
            indent = 2 * self.indent * ' '
            if self.fout is None:
                print(indent, end='')
            else:
                self.fout.write(indent)

        line = ''.join(self.line_buf)
        if self.fout is None:
            print(line)
        else:
            self.fout.write(line)
            self.fout.write('\n')

        self.line_buf = []

        if block_open:
            self.indent += 1

    def transpile(self, prog: Element):
        if self.preamble:
            if self.fout is None:
                print(self.preamble)
            else:
                self.fout.write(self.preamble)
                self.fout.write('\n')

        for func in prog.get('functions'):
            self.transpile_func(func)
            self.emit_line()

        self.line_append('main();')
        self.emit_line()

    def transpile_func(self, func: Element):
        # First line
        self.line_append(f'function {func.get("name")}(')
        self.line_append(', '.join([x.get('name') for x in func.get('args')]))
        self.line_append(')')

        # Closing handled in transpile_stmts
        self.transpile_stmts(func.get('statements'))

    def transpile_stmts(self, stmts: list[Element]):
        self.line_append(' {')
        self.emit_line(block_open=True)

        for stmt in stmts:
            self.transpile_stmt(stmt)

        # Closing line
        self.line_append('}')
        self.emit_line(block_close=True)

    def transpile_stmt(self, stmt: Element):
        match stmt.elem_type:
            case 'vardef':
                self.transpile_vardef_stmt(stmt)
            case '=':
                self.transpile_assign_stmt(stmt)
            case 'fcall':
                self.transpile_funccall(stmt)
                self.line_append(';')
                self.emit_line()
            case 'return':
                self.transpile_return_stmt(stmt)
            case 'if':
                self.transpile_if_stmt(stmt)
            case 'for':
                self.transpile_for_stmt(stmt)
    
    def transpile_vardef_stmt(self, stmt: Element):
        self.line_append(f'var {stmt.get("name")}')
        self.vardef_posthook()
        self.line_append(';')
        self.emit_line()

    # In case some transpilation wants to initialize the variable
    def vardef_posthook(self):
        pass

    # endline=False is used by if statement
    def transpile_assign_stmt(self, stmt, endline=True):
        self.line_append(stmt.get('name'))
        self.assign_prehook()
        self.transpile_expression(stmt.get('expression'), ExprType.RHS_ASSIGN)
        self.assign_posthook()

        if endline:
            self.line_append(';')
            self.emit_line()

    def assign_prehook(self):
        self.line_append(' = ')

    def assign_posthook(self):
        pass

    def transpile_expression(self, expr: Element, type: ExprType):
        self.expression_prehook(expr, type)

        match expr.elem_type:
            case 'int':
                self.line_append(str(expr.get('val')))
            case 'string':
                self.line_append(f"\"{expr.get('val')}\"")
            case 'bool':
                self.line_append('true' if expr.get('val') else 'false')
            case 'nil':
                # This is not perfect, but I don't care a lot
                self.line_append('undefined')
            case 'fcall':
                self.transpile_funccall(expr)
            case 'var':
                self.transpile_varread(expr)
            case _:
                if expr.elem_type in self.UNARY_OPS:
                    self.line_append('-' if expr.elem_type == 'neg' else expr.elem_type)
                    self.transpile_expression(expr.get('op1'), ExprType.INNER)
                elif expr.elem_type in self.BINARY_OPS:
                    # XXX: We currently add parentheses at all possible places, ideally we
                    # can reduce some by checking the operators
                    if not ExprType.is_toplevel(type):
                        self.line_append('(')

                    self.transpile_expression(expr.get('op1'), ExprType.INNER)

                    # We don't want JS's exotic coercion to kick in
                    if expr.elem_type == '==':
                        self.line_append(" === ")
                    elif expr.elem_type == '!=':
                        self.line_append(" !== ")
                    else:
                        self.line_append(f" {expr.elem_type} ")

                    self.transpile_expression(expr.get('op2'), ExprType.INNER)

                    if not ExprType.is_toplevel(type):
                        self.line_append(')')
                else:
                    # THIS SHOULD NOT HAPPEN
                    print(f"Unsupported expression {expr}", file=sys.stderr)

        self.expression_posthook(expr, type)

    def expression_prehook(self, expr: Element, type: ExprType):
        pass

    def expression_posthook(self, expr: Element, type: ExprType):
        pass

    def transpile_varread(self, var: ExprType):
        self.line_append(var.get('name'))
        self.varread_posthook()

    def varread_posthook(self):
        pass

    def transpile_funccall(self, fcall):
        fname = fcall.get('name')
        is_print = fname == 'print'
        self.line_append(fname if not is_print else 'console.log')
        self.line_append('(')

        for i, arg in enumerate(fcall.get('args')):
            if i > 0:
                self.line_append(', ')
            self.transpile_expression(arg, ExprType.ARGS if not is_print else ExprType.EAGER)
        self.line_append(')')
        self.funccall_posthook(fname)

    # in case the function return value is a closure, so we need emit extra staff
    # the fname is provided to avoid messing up prints, etc.
    def funccall_posthook(self, fname):
        pass

    def transpile_return_stmt(self, stmt):
        self.line_append('return')
        expr = stmt.get('expression')
        if expr is not None:
            self.line_append(' ')
            self.transpile_expression(expr, ExprType.RETURN)
        self.line_append(';')
        self.emit_line()

    def transpile_if_stmt(self, stmt):
        self.line_append('if (')
        self.transpile_expression(stmt.get('condition'), ExprType.EAGER)
        self.line_append(')')
        self.transpile_stmts(stmt.get('statements'))

        else_stmts = stmt.get('else_statement')
        if else_stmts is not None:
            self.line_append('else')
            self.transpile_stmts(else_stmts)

    def transpile_for_stmt(self, stmt):
        self.line_append('for (')
        self.transpile_assign_stmt(stmt.get('init'), endline=False)
        self.line_append('; ')
        self.transpile_expression(stmt.get('condition'), ExprType.EAGER)
        self.line_append('; ')
        self.transpile_assign_stmt(stmt.get('update'), endline=False)
        self.line_append(')')
        self.transpile_stmts(stmt.get('statements'))

class B2JSV1(B2JSBase):
    def __init__(self):
        super().__init__()

    def expression_prehook(self, expr, type):
        if ExprType.is_toplevel(type) and type != ExprType.EAGER:
            self.line_append("() => ")

    def funccall_posthook(self, fname):
        if fname != 'print':
            self.line_append('()')

    def varread_posthook(self):
        self.line_append('()')

class B2JSV2(B2JSBase):
    def __init__(self):
        super().__init__()

        self.preamble = """function lazy_hlp(exp_closure) {
  var evaled = false, v;
  return () => {
    if (!evaled) {
      v = exp_closure();
      evaled = true;
    }
    return v;
  }
}
"""

    def expression_prehook(self, expr, type):
        if ExprType.is_toplevel(type):
            if ExprType.needs_cache(type):
                self.line_append("lazy_hlp(() => ")
            elif type != ExprType.EAGER:
                self.line_append("() => ")

    def expression_posthook(self, expr, type):
        if ExprType.needs_cache(type):
            self.line_append(")")

    def funccall_posthook(self, fname):
        if fname != 'print':
            self.line_append('()')

    def varread_posthook(self):
        self.line_append('()')

class B2JSV3(B2JSBase):
    def __init__(self):
        super().__init__()

        self.preamble = """function make_val(c) {
  var o = {
    "snap": () => make_val(c),
    "set": (closure) => {
      var evaled = false;
      var v;
      c = () => {
        if (!evaled) {
          v = closure();
          evaled = true;
        }
        return v;
      }
      return o;
    },
    "get": () => c()
  };
  return o;
}
"""

    def vars_in_expression(self, expr: Element) -> set[str]:
        match expr.elem_type:
            case 'fcall':
                return reduce(lambda a, e: a | self.vars_in_expression(e),
                              expr.get('args'), set())
            case 'var':
                return {expr.get('name')}
            case _:
                if expr.elem_type in self.UNARY_OPS:
                    return self.vars_in_expression(expr.get('op1'))
                elif expr.elem_type in self.BINARY_OPS:
                    return (self.vars_in_expression(expr.get('op1')) |
                            self.vars_in_expression(expr.get('op2')))

        return set()

    def expression_prehook(self, expr, type):
        if ExprType.is_toplevel(type):
            if type != ExprType.EAGER:
                if type == ExprType.RHS_ASSIGN:
                    var_list = list(self.vars_in_expression(expr))
                    if var_list:
                        expr.dict['varlist'] = var_list
                        self.line_append(f"(({', '.join(var_list)}) => ")
                elif ExprType.needs_cache(type):
                    self.line_append('make_val().set(')

                self.line_append("() => ")

    def expression_posthook(self, expr, type):
        if type == ExprType.RHS_ASSIGN:
            var_list = expr.get('varlist')
            if var_list is not None:
                self.line_append(f")({', '.join([x + '.snap()' for x in var_list])})")
        elif ExprType.needs_cache(type):
            self.line_append(')')

    def funccall_posthook(self, fname):
        if fname != 'print':
            self.line_append('()')

    def varread_posthook(self):
        self.line_append('.get()')

    def vardef_posthook(self):
        self.line_append(' = make_val()')

    def assign_prehook(self):
        self.line_append('.set(')
    
    def assign_posthook(self):
        self.line_append(')')

def main():
    parser = ArgumentParser(prog='b2js.py')
    parser.add_argument('-s', '--step', type=int, choices=[0, 1, 2, 3], default=3)
    parser.add_argument('-o', '--output', type=str)
    parser.add_argument('filename')

    args = parser.parse_args()

    with open(args.filename, 'r') as f:
        prog = f.read()

    prog_parsed = parse_program(prog)

    match args.step:
        case 0:
            b2js = B2JSBase()
        case 1:
            b2js = B2JSV1()
        case 2:
            b2js = B2JSV2()
        case _:
            b2js = B2JSV3()

    if args.output is not None:
        fout = open(args.output, 'w')
        b2js.set_output(fout)

    b2js.transpile(prog_parsed)

if __name__ == '__main__':
    main()