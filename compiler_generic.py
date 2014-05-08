from vecpy.kernel import *
from vecpy.compiler_constants import *

class Compiler_Generic:

  def compile_kernel(k, options):
    src = Formatter()
    src.section('Target Architecture: %s (%s)'%(options.arch['name'], options.type))
    #Includes
    src += '//Includes'
    src += '#include <math.h>'
    src += '#include <algorithm>'
    src += ''
    #Function header
    src += '//Kernel function: %s'%(k.name)
    src += 'static void %s_scalar(KernelArgs* args) {'%(k.name)
    src += ''
    src.indent()
    #Uniforms
    src += '//Uniforms'
    for arg in k.get_arguments(uniform=True):
      src += 'const %s %s = args->%s;'%(options.type, arg.name, arg.name)
    src += ''
    #Literals
    src += '//Literals'
    for var in k.get_literals():
      if DataType.is_floating(options.type):
        value = '%sf'%(str(var.value))
      else:
        value = '0x%08x'%(var.value)
      src += 'const %s %s = %s;'%(options.type, var.name, value)
    src += ''
    #Temporary (stack) variables
    src += '//Stack variables (numeric)'
    vars = ['%s%s'%('*' if var.stride > 1 else '', var.name) for var in k.get_variables(mask=False, uniform=False)]
    if len(vars) > 0:
      src += '%s %s;'%(options.type, ', '.join(vars))
    src += ''
    src += '//Stack variables (boolean)'
    bools = [var.name for var in k.get_variables() if var.is_mask]
    if len(bools) > 0:
      src += '%s %s;'%('bool', ', '.join(bools))
    src += ''
    #Begin input loop
    src += '//Loop over input'
    src += 'for(unsigned int index = 0; index < args->N; ++index) {'
    src += ''
    #Function body
    src.indent()
    #Inputs
    src += '//Inputs'
    for arg in k.get_arguments(input=True, uniform=False):
      addr = ''
      index = 'index'
      if arg.stride > 1:
        addr = '&'
        index = '%s * %d'%(index, arg.stride)
      src += '%s = %sargs->%s[%s];'%(arg.name, addr, arg.name, index)
    src += ''
    #Core kernel logic
    src += '//Begin kernel logic'
    src += '{'
    src += ''
    Compiler_Generic.compile_block(k.block, src, options)
    src += ''
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

  def compile_block(block, src, options):
    src.indent()
    for stmt in block.code:
      if isinstance(stmt, Comment):
        src += '//>>> %s'%(stmt.comment)
      elif isinstance(stmt, Assignment):
        if isinstance(stmt.expr, Variable):
          src += '%s = %s;'%(stmt.var.name, stmt.expr.name)
        elif stmt.vector_only:
          #Don't generate vector masks
          src += '%s = %s;'%(stmt.var.name, stmt.expr.left.name)
        elif isinstance(stmt.expr, BinaryOperation):
          op = stmt.expr.op
          var = stmt.var.name
          left = stmt.expr.left.name
          right = stmt.expr.right.name
          if op in ('+', '-', '*', '/', '&', '&~', '|', '^', '&&', '||', '<<', '>>'):
            if op == '&~':
              src += '%s = ~%s & %s;'%(var, left, right)
            else:
              src += '%s = %s %s %s;'%(var, left, op, right)
          elif op == '//':
            if DataType.is_floating(options.type):
              src += '%s = floor(%s / %s);'%(var, left, right)
            else:
              src += '%s = %s / %s;'%(var, left, op, right)
          elif op == '%':
            if DataType.is_floating(options.type):
              src += '%s = fmod(%s, %s);'%(var, left, right)
            else:
              src += '%s = %s %s %s;'%(var, left, op, right)
          elif op == '**':
            src += '%s = pow(%s, %s);'%(var, left, right)
          elif op in Intrinsic.binary_functions + Math.binary_functions:
            if op in ('max', 'min'):
              op = 'std::' + op
            src += '%s = %s(%s, %s);'%(var, op, left, right)
          else:
            raise Exception('Unknown operator (%s)'%(op))
        elif isinstance(stmt.expr, UnaryOperation):
          op = stmt.expr.op
          var = stmt.var.name
          input = stmt.expr.var.name
          if op in ('~', '!'):
            if op in ('~',) and not DataType.is_integral(options.type):
              raise Exception('Operator requires integer operand (%s)'%(op))
            if op in ('!',) and (not stmt.var.is_mask or not stmt.expr.var.is_mask):
              raise Exception('Operator requires boolean operand (%s)'%(op))
            src += '%s = %s%s;'%(var, op, input)
          elif op in Intrinsic.unary_functions + Math.unary_functions:
            #Special cases
            if op == 'gamma':
              #http://stackoverflow.com/a/18116639
              op = 'tgamma'
            elif op == 'abs' and options.type == DataType.float:
              #http://stackoverflow.com/a/13792680
              op = 'fabs'
            #Default case
            src += '%s = %s(%s);'%(var, op, input)
          else:
            raise Exception('Unknown unary operator/function (%s)'%(op))
        elif isinstance(stmt.expr, ComparisonOperation):
          op = stmt.expr.op
          var = stmt.var.name
          left = stmt.expr.left.name
          right = stmt.expr.right.name
          if op in ('==', '!=', '>', '>=', '<', '<='):
            src += '%s = %s %s %s;'%(var, left, op, right)
          else:
            raise Exception('Unknown operator (%s)'%(op))
        elif isinstance(stmt.expr, ArrayAccess):
          var = stmt.var.name
          array = stmt.expr.array.name
          index = stmt.expr.index.name
          if stmt.expr.is_read:
            src += '%s = %s[%s];'%(var, array, index)
          else:
            src += '%s[%s] = %s;'%(array, index, var)
        else:
          raise Exception('Bad assignment')
      elif isinstance(stmt, IfElse):
        src += 'if(%s) {'%(stmt.if_block.mask.name)
        Compiler_Generic.compile_block(stmt.if_block, src, options)
        if len(stmt.else_block.code) > 0:
          src += '} else {'
          Compiler_Generic.compile_block(stmt.else_block, src, options)
        src += '}'
      elif isinstance(stmt, WhileLoop):
        src += 'while(%s) {'%(stmt.block.mask.name)
        Compiler_Generic.compile_block(stmt.block, src, options)
        src += '}'
      else:
        raise Exception('Can\'t handle that (%s)'%(stmt.__class__))
    src.unindent()
