from kernel import *
from compiler_constants import *

class Compiler_Generic:

  def compile_kernel(k, arch):
    src = Formatter()
    src.section('Target Architecture: Generic')
    #Includes
    src += '//Includes'
    src += '#include <math.h>'
    src += ''
    #Function header
    src += '//Kernel function: %s'%(k.name)
    src += 'static void %s_generic(KernelArgs* args) {'%(k.name)
    src += ''
    src.indent()
    #Literals
    src += '//Literals'
    for var in k.get_literals():
      src += 'const %s %s = %f;'%(k.get_type(), var.name, var.value)
    src += ''
    #Temporary (stack) variables
    src += '//Stack variables'
    src += '%s %s;'%(k.get_type(), ', '.join([var.name for var in k.get_variables()]))
    src += ''
    #Begin input loop
    src += '//Loop over input'
    src += 'for(int index = 0; index < args->N; index++) {'
    src += ''
    #Function body
    src.indent()
    #Inputs
    src += '//Inputs'
    for arg in k.get_arguments(input=True):
      src += '%s = args->%s[index];'%(arg.name, arg.name)
    src += ''
    #Core kernel logic
    src += '//Begin kernel logic'
    src += '{'
    src.indent()
    for stmt in k.code:
      if isinstance(stmt, Comment):
        src += ''
        src += '//>>> %s'%(stmt.comment)
      elif isinstance(stmt, Statement):
        stmt = stmt.stmt
        if isinstance(stmt, Assignment):
          if isinstance(stmt.expr, Variable):
            src += '%s = %s;'%(stmt.var.name, stmt.expr.name)
          elif isinstance(stmt.expr, BinaryOperation):
            op = stmt.expr.op
            var = stmt.var.name
            left = stmt.expr.left.name
            right = stmt.expr.right.name
            if op in ('+', '-', '*', '/'):
              src += '%s = %s %s %s;'%(var, left, op, right)
            elif op == '**':
              src += '%s = pow(%s, %s);'%(var, left, right)
            elif op in Math.binary_functions:
              src += '%s = %s(%s, %s);'%(var, op, left, right)
            else:
              raise Exception('Unknown operator (%s)'%(op))
          elif isinstance(stmt.expr, UnaryOperation):
            op = stmt.expr.op
            var = stmt.var.name
            input = stmt.expr.var.name
            if op in ('',):
              #todo - built-in unary operations
              pass
            elif op in Math.unary_functions:
              src += '%s = %s(%s);'%(var, op, input)
            else:
              raise Exception('Unknown unary operator/function (%s)'%(op))
          else:
            raise Exception('bad assignment')
        else:
          raise Exception('statement not an assignment (%s)'%(stmt.__class__))
      else:
        raise Exception('can\'t handle that (%s)'%(stmt.__class__))
    src += ''
    src.unindent()
    src += '}'
    src += '//End kernel logic'
    src += ''
    #Outputs
    src += '//Outputs'
    for arg in k.get_arguments(output=True):
      src += 'args->%s[index] = %s;'%(arg.name, arg.name)
    src += ''
    #End input loop
    src.unindent()
    src += '}'
    #Function footer
    src.unindent()
    src += '}'
    src += '//End of kernel function'
    src += ''
    return src.get_code()
