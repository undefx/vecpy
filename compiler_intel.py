from kernel import *
from compiler_constants import *

class Compiler_Intel:

  def compile_kernel(k, arch):
    cType = k.get_type()
    vecType = '__m128'
    size = 4
    scratch = ('tempA', 'tempB')
    src = Formatter()
    src.section('Target Architecture: %s'%(arch['name']))
    #Includes
    src += '//Includes'
    src += '#include <x86intrin.h>'
    src += ''
    #Function header
    src += '//Kernel function: %s'%(k.name)
    src += 'static void %s_vector(KernelArgs* args) {'%(k.name)
    src += ''
    src.indent()
    #Literals
    src += '//Literals'
    for var in k.get_literals():
      src += 'const %s %s = _mm_set1_ps(%f);'%(vecType, var.name, var.value)
    src += ''
    #Temporary (stack) variables
    src += '//Stack variables'
    src += '%s %s;'%(vecType, ', '.join([var.name for var in k.get_variables()]))
    src += ''
    #Scratch
    src += '//Scratch'
    for var in scratch:
      src += '%s %s[%d];'%(cType, var, size)
    src += ''
    #Helper functions
    def binary_function(src, var, func, left, right):
      src += '_mm_store_ps(%s, %s);'%(scratch[0], left)
      src += '_mm_store_ps(%s, %s);'%(scratch[1], right)
      for i in range(size):
        src += '%s[%d] = %s(%s[%d], %s[%d]);'%(scratch[0], i, func, scratch[0], i, scratch[1], i)
      src += '%s = _mm_load_ps(%s);'%(var, scratch[0])
    def unary_function(src, var, func, input):
      src += '_mm_store_ps(%s, %s);'%(scratch[0], input)
      for i in range(size):
        src += '%s[%d] = %s(%s[%d]);'%(scratch[0], i, func, scratch[0], i)
      src += '%s = _mm_load_ps(%s);'%(var, scratch[0])
    #Begin input loop
    src += '//Loop over input'
    src += 'for(int index = 0; index < args->N; index += %d) {'%(size)
    src += ''
    #Function body
    src.indent()
    #Inputs
    src += '//Inputs'
    for arg in k.get_arguments(input=True):
      src += '%s = _mm_load_ps(&args->%s[index]);'%(arg.name, arg.name)
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
              if op == '+':
                func = '_mm_add_ps'
              elif op == '-':
                func = '_mm_sub_ps'
              elif op == '*':
                func = '_mm_mul_ps'
              elif op == '/':
                func = '_mm_div_ps'
              src += '%s = %s(%s, %s);'%(var, func, left, right)
            elif op == '**':
              binary_function(src, var, 'pow', left, right)
            elif op in Math.binary_functions:
              binary_function(src, var, op, left, right)
            else:
              raise Exception('Unknown binary operator/function (%s)'%(op))
          elif isinstance(stmt.expr, UnaryOperation):
            op = stmt.expr.op
            var = stmt.var.name
            input = stmt.expr.var.name
            if op in ('',):
              #todo - built-in unary operations
              pass
            elif op in Math.unary_functions:
              unary_function(src, var, op, input)
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
      src += '_mm_store_ps(&args->%s[index], %s);'%(arg.name, arg.name)
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
