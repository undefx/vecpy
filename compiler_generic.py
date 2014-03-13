from kernel import *
from compiler_constants import *

class Compiler_Generic:
  def compile_kernel(k, arch):
    indent = get_indent()
    src = ''
    #Includes
    src += '//Includes\n'
    src += '#include <math.h>\n'
    src += '\n'
    #The KernelArgs struct
    src += '//Kernel arguments\n';
    src += 'struct KernelArgs {\n';
    for arg in k.get_arguments():
      src += '%s%s* %s;\n'%(indent, k.get_type(), arg.name);
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
      src += '%sconst %s %s = %f;\n'%(indent, k.get_type(), var.name, var.value)
    src += '\n';
    #Temporary (stack) variables
    src += '%s//Stack variables\n'%(indent)
    src += '%s%s %s;\n'%(indent, k.get_type(), ', '.join([var.name for var in k.get_variables()]))
    src += '\n';
    #Begin input loop
    src += '%s//Loop over input\n'%(indent)
    src += '%sfor(int index = 0; index < args->N; index++) {\n'%(indent)
    src += '\n';
    #Function body
    indent += get_indent()
    #Inputs
    src += '%s//Inputs\n'%(indent)
    for arg in k.get_arguments(input=True):
      src += '%s%s = args->%s[index];\n'%(indent, arg.name, arg.name)
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
            if op in ('+', '-', '*', '/'):
              src += '%s%s = %s %s %s;\n'%(indent, stmt.var.name, stmt.expr.left.name, op, stmt.expr.right.name)
            elif op == '**':
              src += '%s%s = pow(%s, %s);\n'%(indent, stmt.var.name, stmt.expr.left.name, stmt.expr.right.name)
            else:
              raise Exception('Unknown operator (%s)'%(op))
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
      src += '%sargs->%s[index] = %s;\n'%(indent, arg.name, arg.name)
    src += '\n';
    #End input loop
    indent = get_indent()
    src += '%s}\n'%(indent)
    #Function footer
    src += '}\n'
    src += '//End of kernel function\n'
    src += '\n';
    return src
