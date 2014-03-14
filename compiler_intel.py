from kernel import *
from compiler_constants import *

class Compiler_Intel:

  def compile_kernel(k, arch):
    indent = get_indent()
    src = ''
    cType = k.get_type()
    vecType = '__m128'
    size = 4
    scratch = ('tempA', 'tempB')
    src += '//Target Architecture: %s\n'%(arch['name'])
    #Includes
    src += '//Includes\n'
    src += '#include <math.h>\n'
    src += '#include <x86intrin.h>\n'
    src += '\n'
    #The KernelArgs struct
    src += '//Kernel arguments\n';
    src += 'struct KernelArgs {\n';
    for arg in k.get_arguments():
      src += '%s%s* %s;\n'%(indent, cType, arg.name);
    src += '%sint N;\n'%(indent);
    src += '};\n';
    src += '\n';
    #Function header
    src += '//Kernel function: %s\n'%(k.name)
    src += 'static void %s(KernelArgs* args) {\n'%(k.name)
    src += '\n';
    #Literals
    src += '%s//Literals\n'%(indent)
    for var in k.get_literals():
      src += '%sconst %s %s = _mm_set1_ps(%f);\n'%(indent, vecType, var.name, var.value)
    src += '\n';
    #Temporary (stack) variables
    src += '%s//Stack variables\n'%(indent)
    src += '%s%s %s;\n'%(indent, vecType, ', '.join([var.name for var in k.get_variables()]))
    src += '\n';
    #Scratch
    src += '%s//Scratch\n'%(indent)
    for var in scratch:
      src += '%s%s %s[%d];\n'%(indent, cType, var, size)
    src += '\n';
    #Helper functions
    def binary_function(var, func, left, right):
      src = ''
      src += '%s_mm_store_ps(%s, %s);\n'%(indent, scratch[0], left)
      src += '%s_mm_store_ps(%s, %s);\n'%(indent, scratch[1], right)
      for i in range(size):
        src += '%s%s[%d] = %s(%s[%d], %s[%d]);\n'%(indent, scratch[0], i, func, scratch[0], i, scratch[1], i)
      src += '%s%s = _mm_load_ps(%s);\n'%(indent, var, scratch[0])
      return src
    def unary_function(var, func, input):
      src = ''
      src += '%s_mm_store_ps(%s, %s);\n'%(indent, scratch[0], input)
      for i in range(size):
        src += '%s%s[%d] = %s(%s[%d]);\n'%(indent, scratch[0], i, func, scratch[0], i)
      src += '%s%s = _mm_load_ps(%s);\n'%(indent, var, scratch[0])
      return src
    #Begin input loop
    src += '%s//Loop over input\n'%(indent)
    src += '%sfor(int index = 0; index < args->N; index += %d) {\n'%(indent, size)
    src += '\n';
    #Function body
    indent += get_indent()
    #Inputs
    src += '%s//Inputs\n'%(indent)
    for arg in k.get_arguments(input=True):
      #src += '%s%s = args->%s[index];\n'%(indent, arg.name, arg.name)
      src += '%s%s = _mm_load_ps(&args->%s[index]);\n'%(indent, arg.name, arg.name)
    src += '\n';
    #Core kernel logic
    src += '%s//Begin kernel logic\n'%(indent)
    src += '%s{\n'%(indent)
    old_indent = indent
    indent += get_indent()
    for stmt in k.code:
      if isinstance(stmt, Comment):
        src += '\n%s// %s\n'%(indent, stmt.comment)
      elif isinstance(stmt, Statement):
        stmt = stmt.stmt
        if isinstance(stmt, Assignment):
          if isinstance(stmt.expr, Variable):
            src += '%s%s = %s;\n'%(indent, stmt.var.name, stmt.expr.name)
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
              src += '%s%s = %s(%s, %s);\n'%(indent, var, func, left, right)
            elif op == '**':
              func = 'pow'
              src += binary_function(var, func, left, right)
            elif op in Math.binary_functions:
              src += binary_function(var, op, left, right)
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
              src += unary_function(var, op, input)
            else:
              raise Exception('Unknown unary operator/function (%s)'%(op))
          else:
            raise Exception('bad assignment');
        else:
          raise Exception('statement not an assignment (%s)'%(stmt.__class__));
      else:
        raise Exception('can\'t handle that (%s)'%(stmt.__class__));
    src += '\n';
    indent = old_indent
    src += '%s}\n'%(indent)
    src += '%s//End kernel logic\n'%(indent)
    src += '\n';
    #Outputs
    src += '%s//Outputs\n'%(indent)
    for arg in k.get_arguments(output=True):
      src += '%s_mm_store_ps(&args->%s[index], %s);\n'%(indent, arg.name, arg.name)
    src += '\n';
    #End input loop
    indent = get_indent()
    src += '%s}\n'%(indent)
    #Function footer
    src += '}\n'
    src += '//End of kernel function\n'
    src += '\n';
    return src
