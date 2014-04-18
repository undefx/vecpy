from kernel import *
from compiler_constants import *

class Compiler_Intel:

  def compile_kernel(k, options):
    scratch = ('tempA', 'tempB')
    src = Formatter()
    src.section('Target Architecture: %s (%s)'%(options.arch['name'], options.type))
    size = options.arch['size']
    if options.type == DataType.float:
      trans = Compiler_Intel.SSE4_Float(src, scratch, size)
      literal_format = '%.7ff'
    elif options.type == DataType.uint32:
      trans = Compiler_Intel.SSE4_UInt32(src, scratch, size)
      literal_format = '0x%08x'
    else:
      raise Exception('Type not supported (%s)'%(options.type))
    vecType = trans.type
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
      trans.set('const %s %s'%(vecType, var.name), literal_format%(var.value))
    src += ''
    #Temporary (stack) variables
    src += '//Stack variables'
    src += '%s %s;'%(vecType, ', '.join([var.name for var in k.get_variables()]))
    src += ''
    #Scratch
    src += '//Scratch'
    for var in scratch:
      src += '%s %s[%d];'%(options.type, var, size)
    src += ''
    #Begin input loop
    src += '//Loop over input'
    src += 'for(unsigned int index = 0; index < args->N; index += %d) {'%(size)
    src += ''
    #Function body
    src.indent()
    #Inputs
    src += '//Inputs'
    for arg in k.get_arguments(input=True):
      trans.load(arg.name, '&args->%s[index]'%(arg.name))
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
            if op in trans.operations:
              trans.operations[op](var, left, right)
            else:
              raise Exception('Unknown binary operator/function (%s)'%(op))
          elif isinstance(stmt.expr, UnaryOperation):
            op = stmt.expr.op
            var = stmt.var.name
            input = stmt.expr.var.name
            if op in trans.operations:
              trans.operations[op](var, input)
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
      trans.store('&args->%s[index]'%(arg.name), arg.name)
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

  class Translator:
    def __init__(self, src, scratch, size):
      self.src = src
      self.scratch = scratch
      self.size = size
      self.operations = {
        #Python operators
        '+': self.add,
        '-': self.sub,
        '*': self.mul,
        '/': self.div,
        '%': self.mod,
        '**': self.pow,
        #Python intrinsics
        'abs': self.abs,
        'max': self.max,
        'min': self.min,
        #Math functions (binary)
        'atan2': self.atan2,
        'copysign': self.copysign,
        'fmod': self.fmod,
        'hypot': self.hypot,
        #'ldexp': self.ldexp,
        'pow': self.pow,
        #Math functions (unary)
        'acos': self.acos,
        'acosh': self.acosh,
        'asin': self.asin,
        'asinh': self.asinh,
        'atan': self.atan,
        'atanh': self.atanh,
        'ceil': self.ceil,
        'cos': self.cos,
        'cosh': self.cosh,
        'erf': self.erf,
        'erfc': self.erfc,
        'exp': self.exp,
        'expm1': self.expm1,
        'fabs': self.fabs,
        #'factorial': self.factorial,
        'floor': self.floor,
        #'frexp': self.frexp,
        'gamma': self.gamma,
        #'isfinite': self.isfinite,
        #'isinf': self.isinf,
        #'isnan': self.isnan,
        'lgamma': self.lgamma,
        'log': self.log,
        'log10': self.log10,
        'log1p': self.log1p,
        'log2': self.log2,
        #'modf': self.modf,
        'sin': self.sin,
        'sinh': self.sinh,
        'sqrt': self.sqrt,
        'tan': self.tan,
        'tanh': self.tanh,
        'trunc': self.trunc,
      }
    #Common operations
    def vector_0_1(self, func, args):
      self.src += '%s(%s);'%(func, args[0])
    def vector_1_1(self, func, args):
      self.src += '%s = %s(%s);'%(args[0], func, args[1])
    def vector_0_2(self, func, args):
      self.src += '%s(%s, %s);'%(func, args[0], args[1])
    def vector_1_2(self, func, args):
      self.src += '%s = %s(%s, %s);'%(args[0], func, args[1], args[2])
    def scalar_1_1(self, func, args):
      output, input = args
      s = self.scratch
      self.store(s[0], input)
      for i in range(self.size):
        self.src += '%s[%d] = %s(%s[%d]);'%(s[0], i, func, s[0], i)
      self.load(output, s[0])
    def scalar_1_2(self, func, args):
      output, left, right = args
      s = self.scratch
      self.store(s[0], left)
      self.store(s[1], right)
      for i in range(self.size):
        self.src += '%s[%d] = %s(%s[%d], %s[%d]);'%(s[0], i, func, s[0], i, s[1], i)
      self.load(output, s[0])
    def error(self):
      raise Exception('Not implemented')
    #Abstract stubs
    #Misc
    def set(self, *args):
      self.error()
    def load(self, *args):
      self.error()
    def store(self, *args):
      self.error()
    #Operators
    def add(self, *args):
      self.error()
    def sub(self, *args):
      self.error()
    def mul(self, *args):
      self.error()
    def div(self, *args):
      self.error()
    def mod(self, *args):
      self.error()
    def pow(self, *args):
      self.error()
    #Python intrinsics
    def abs(self, *args):
      self.error()
    def max(self, *args):
      self.error()
    def min(self, *args):
      self.error()
    #Math functions (binary)
    def atan2(self, *args):
      self.error()
    def copysign(self, *args):
      self.error()
    def fmod(self, *args):
      self.error()
    def hypot(self, *args):
      self.error()
    def ldexp(self, *args):
      self.error()
    #Math functions (unary)
    def acos(self, *args):
      self.error()
    def acosh(self, *args):
      self.error()
    def asin(self, *args):
      self.error()
    def asinh(self, *args):
      self.error()
    def atan(self, *args):
      self.error()
    def atanh(self, *args):
      self.error()
    def ceil(self, *args):
      self.error()
    def cos(self, *args):
      self.error()
    def cosh(self, *args):
      self.error()
    def erf(self, *args):
      self.error()
    def erfc(self, *args):
      self.error()
    def exp(self, *args):
      self.error()
    def expm1(self, *args):
      self.error()
    def fabs(self, *args):
      self.error()
    def factorial(self, *args):
      self.error()
    def floor(self, *args):
      self.error()
    def frexp(self, *args):
      self.error()
    def gamma(self, *args):
      self.error()
    def isfinite(self, *args):
      self.error()
    def isinf(self, *args):
      self.error()
    def isnan(self, *args):
      self.error()
    def lgamma(self, *args):
      self.error()
    def log(self, *args):
      self.error()
    def log10(self, *args):
      self.error()
    def log1p(self, *args):
      self.error()
    def log2(self, *args):
      self.error()
    def modf(self, *args):
      self.error()
    def sin(self, *args):
      self.error()
    def sinh(self, *args):
      self.error()
    def sqrt(self, *args):
      self.error()
    def tan(self, *args):
      self.error()
    def tanh(self, *args):
      self.error()
    def trunc(self, *args):
      self.error()

  class SSE4_Float(Translator):
    def __init__(self, src, scratch, size):
      Compiler_Intel.Translator.__init__(self, src, scratch, size)
      self.type = '__m128'
    #Misc
    def set(self, *args):
      self.vector_1_1('_mm_set1_ps', args)
    def load(self, *args):
      self.vector_1_1('_mm_load_ps', args)
    def store(self, *args):
      self.vector_0_2('_mm_store_ps', args)
    #Operators
    def add(self, *args):
      self.vector_1_2('_mm_add_ps', args)
    def sub(self, *args):
      self.vector_1_2('_mm_sub_ps', args)
    def mul(self, *args):
      self.vector_1_2('_mm_mul_ps', args)
    def div(self, *args):
      self.vector_1_2('_mm_div_ps', args)
    def mod(self, *args):
      self.scalar_1_2('fmod', args)
    def pow(self, *args):
      self.scalar_1_2('pow', args)
    #Python intrinsics
    def abs(self, *args):
      self.scalar_1_1('fabs', args)
    def max(self, *args):
      self.vector_1_2('_mm_max_ps', args)
    def min(self, *args):
      self.vector_1_2('_mm_min_ps', args)
    #Math functions (binary)
    def atan2(self, *args):
      self.scalar_1_2('atan2', args)
    def copysign(self, *args):
      self.scalar_1_2('copysign', args)
    def fmod(self, *args):
      self.scalar_1_2('fmod', args)
    def hypot(self, *args):
      self.scalar_1_2('hypot', args)
    #def ldexp(self, *args):
    #  self.error()
    #Math functions (unary)
    def acos(self, *args):
      self.scalar_1_1('acos', args)
    def acosh(self, *args):
      self.scalar_1_1('acosh', args)
    def asin(self, *args):
      self.scalar_1_1('asin', args)
    def asinh(self, *args):
      self.scalar_1_1('asinh', args)
    def atan(self, *args):
      self.scalar_1_1('atan', args)
    def atanh(self, *args):
      self.scalar_1_1('atanh', args)
    def ceil(self, *args):
      self.scalar_1_1('ceil', args)
    def cos(self, *args):
      self.scalar_1_1('cos', args)
    def cosh(self, *args):
      self.scalar_1_1('cosh', args)
    def erf(self, *args):
      self.scalar_1_1('erf', args)
    def erfc(self, *args):
      self.scalar_1_1('erfc', args)
    def exp(self, *args):
      self.scalar_1_1('exp', args)
    def expm1(self, *args):
      self.scalar_1_1('expm1', args)
    def fabs(self, *args):
      self.scalar_1_1('fabs', args)
    #def factorial(self, *args):
    #  self.scalar_1_1('factorial', args)
    def floor(self, *args):
      self.scalar_1_1('floor', args)
    #def frexp(self, *args):
    #  self.scalar_1_1('frexp', args)
    def gamma(self, *args):
      self.scalar_1_1('tgamma', args)
    #def isfinite(self, *args):
    #  self.scalar_1_1('isfinite', args)
    #def isinf(self, *args):
    #  self.scalar_1_1('isinf', args)
    #def isnan(self, *args):
    #  self.scalar_1_1('isnan', args)
    def lgamma(self, *args):
      self.scalar_1_1('lgamma', args)
    def log(self, *args):
      self.scalar_1_1('log', args)
    def log10(self, *args):
      self.scalar_1_1('log10', args)
    def log1p(self, *args):
      self.scalar_1_1('log1p', args)
    def log2(self, *args):
      self.scalar_1_1('log2', args)
    #def modf(self, *args):
    #  self.scalar_1_1('modf', args)
    def sin(self, *args):
      self.scalar_1_1('sin', args)
    def sinh(self, *args):
      self.scalar_1_1('sinh', args)
    def sqrt(self, *args):
      self.vector_1_1('_mm_sqrt_ps', args)
    def tan(self, *args):
      self.scalar_1_1('tan', args)
    def tanh(self, *args):
      self.scalar_1_1('tanh', args)
    def trunc(self, *args):
      self.scalar_1_1('trunc', args)

  class SSE4_UInt32(Translator):
    def __init__(self, src, scratch, size):
      Compiler_Intel.Translator.__init__(self, src, scratch, size)
      self.type = '__m128i'
    #Misc
    def set(self, *args):
      self.vector_1_1('_mm_set1_epi32', args)
    def load(self, *args):
      args = (args[0], '(const %s*)(%s)'%(self.type, args[1]))
      self.vector_1_1('_mm_load_si128', args)
    def store(self, *args):
      args = ('(%s*)(%s)'%(self.type, args[0]), args[1])
      self.vector_0_2('_mm_store_si128', args)
    #Operators
    def add(self, *args):
      self.vector_1_2('_mm_add_epi32', args)
    def sub(self, *args):
      self.vector_1_2('_mm_sub_epi32', args)
    def mul(self, *args):
      self.vector_1_2('_mm_mullo_epi32', args)
    #def div(self, *args):
    #  self.vector_1_2('_mm_div_ps', args)
    #def mod(self, *args):
    #  self.vector_1_2('?', args)
    #def pow(self, *args):
    #  self.scalar_1_2('pow', args)
    ##Python intrinsics
    #def abs(self, *args):
    #  self.error()
    #def max(self, *args):
    #  self.error()
    #def min(self, *args):
    #  self.error()
    ##Math functions (binary)
    #def atan2(self, *args):
    #  self.scalar_1_2('atan2', args)
    #def copysign(self, *args):
    #  self.scalar_1_2('copysign', args)
    #def fmod(self, *args):
    #  self.scalar_1_2('fmod', args)
    #def hypot(self, *args):
    #  self.scalar_1_2('hypot', args)
    #def ldexp(self, *args):
    #  self.error()
    ##Math functions (unary)
    #def acos(self, *args):
    #  self.scalar_1_1('acos', args)
    #def acosh(self, *args):
    #  self.scalar_1_1('acosh', args)
    #def asin(self, *args):
    #  self.scalar_1_1('asin', args)
    #def asinh(self, *args):
    #  self.scalar_1_1('asinh', args)
    #def atan(self, *args):
    #  self.scalar_1_1('atan', args)
    #def atanh(self, *args):
    #  self.scalar_1_1('atanh', args)
    #def ceil(self, *args):
    #  self.scalar_1_1('ceil', args)
    #def cos(self, *args):
    #  self.scalar_1_1('cos', args)
    #def cosh(self, *args):
    #  self.scalar_1_1('cosh', args)
    ##'erf',
    ##'erfc',
    #def exp(self, *args):
    #  self.scalar_1_1('exp', args)
    ##'expm1',
    #def fabs(self, *args):
    #  self.scalar_1_1('fabs', args)
    ##'factorial',
    #def floor(self, *args):
    #  self.scalar_1_1('floor', args)
    ##'frexp',
    ##'gamma',
    ##'isfinite',
    ##'isinf',
    ##'isnan',
    ##'lgamma',
    ##'log',
    ##'log10',
    ##'log1p',
    ##'log2',
    ##'modf',
    #def sin(self, *args):
    #  self.scalar_1_1('sin', args)
    #def sinh(self, *args):
    #  self.scalar_1_1('sinh', args)
    #def sqrt(self, *args):
    #  self.vector_1_1('_mm_sqrt_ps', args)
    #def tan(self, *args):
    #  self.scalar_1_1('tan', args)
    #def tanh(self, *args):
    #  self.scalar_1_1('tanh', args)
    ##'trunc',
