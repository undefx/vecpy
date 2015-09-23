from vecpy.kernel import *
from vecpy.compiler_constants import *

class Compiler_Intel:

  def compile_kernel(k, options):
    src = Formatter()
    src.section('Target Architecture: %s (%s)'%(options.arch['name'], options.type))
    #Set some basic parameters
    size = options.arch['size']
    #Select an appropriate translator for the target architecture and data type
    if options.arch == Architecture.sse4:
      if DataType.is_floating(options.type):
        trans = Compiler_Intel.SSE4_Float(src, size)
      else:
        trans = Compiler_Intel.SSE4_UInt32(src, size)
    elif options.arch == Architecture.avx2:
      if DataType.is_floating(options.type):
        trans = Compiler_Intel.AVX2_Float(src, size)
      else:
        trans = Compiler_Intel.AVX2_UInt32(src, size)
    else:
      raise Exception('Architecture not supported (%s)'%(options.arch['name']))
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
    #Target-dependent setup
    src += '//Setup'
    trans.setup()
    src += ''
    #Uniforms
    src += '//Uniforms'
    for arg in k.get_arguments(uniform=True):
      trans.set('const %s %s'%(vecType, arg.name), 'args->%s'%(arg.name))
    src += ''
    #Literals
    src += '//Literals'
    for var in k.get_literals():
      if DataType.is_floating(options.type):
        value = str(var.value)
      else:
        value = '0x%08x'%(var.value)
      trans.set('const %s %s'%(vecType, var.name), value)
    src += ''
    #Temporary (stack) variables
    src += '//Stack variables'
    src += '%s %s;'%(vecType, ', '.join(var.name for var in k.get_variables(uniform=False, array=False)))
    vars = ['*%s'%(var.name) for var in k.get_variables(uniform=False, array=True)]
    if len(vars) > 0:
      src += '%s %s;'%(options.type, ', '.join(vars))
    src += ''
    #Begin input loop
    src += '//Loop over input'
    src += 'for(uint64_t index = 0; index < args->N; index += %d) {'%(size)
    src += ''
    #Function body
    src.indent()
    #Inputs
    src += '//Inputs'
    for arg in k.get_arguments(input=True, uniform=False):
      if arg.stride > 1:
        index = 'index * %d'%(arg.stride)
        src += '%s = &args->%s[%s];'%(arg.name, arg.name, index)
      else:
        trans.load(arg.name, '&args->%s[index]'%(arg.name))
    src += ''
    #Core kernel logic
    src += '//Begin kernel logic'
    src += '{'
    src += ''
    Compiler_Intel.compile_block(k.block, src, trans)
    src += ''
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

  def compile_block(block, src, trans):
    src.indent()
    for stmt in block.code:
      if isinstance(stmt, Comment):
        src += '//>>> %s'%(stmt.comment)
      elif isinstance(stmt, Assignment):
        if isinstance(stmt.expr, Variable):
          if stmt.vector_only:
            mask = stmt.mask.name
            output = stmt.var.name
            input = stmt.expr.name
            trans.mask(input, output, mask)
          else:
            src += '%s = %s;'%(stmt.var.name, stmt.expr.name)
        elif isinstance(stmt.expr, BinaryOperation):
          op = stmt.expr.op
          var = stmt.var.name
          left = stmt.expr.left.name
          right = stmt.expr.right.name
          if op in trans.operations:
            #Check for bit-shift optimization
            if op in (Operator.shift_left, Operator.shift_right) and stmt.expr.right.value is not None:
              #Optimized shift
              right = '%d'%(stmt.expr.right.value)
              trans.operations[op](var, left, right, True)
            else:
              #Normal binary operation
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
        elif isinstance(stmt.expr, ComparisonOperation):
          op = stmt.expr.op
          var = stmt.var.name
          left = stmt.expr.left.name
          right = stmt.expr.right.name
          if op in trans.operations:
            trans.operations[op](var, left, right)
          else:
            raise Exception('Unknown comparison operator (%s)'%(op))
        elif isinstance(stmt.expr, ArrayAccess):
          var = stmt.var.name
          array = stmt.expr.array.name
          index = stmt.expr.index.name
          stride = stmt.expr.array.stride
          if stmt.expr.is_read:
            trans.array_read(var, array, index, stride)
          else:
            trans.array_write(var, array, index, stride)
        else:
          raise Exception('Bad assignment')
      elif isinstance(stmt, IfElse):
        src += '{'
        Compiler_Intel.compile_block(stmt.if_block, src, trans)
        if len(stmt.else_block.code) != 0:
          src += '}'
          src += '//(else)'
          src += '{'
          Compiler_Intel.compile_block(stmt.else_block, src, trans)
        src += '}'
      elif isinstance(stmt, WhileLoop):
        test = '%s(%s)'%(trans.test, stmt.block.mask.name)
        src += 'while(%s) {'%(test)
        Compiler_Intel.compile_block(stmt.block, src, trans)
        src += '}'
      else:
        raise Exception('Can\'t handle that (%s)'%(stmt.__class__))
    src.unindent()

  ################################################################################
  # Translates kernel operations into vectorized C++ code
  ################################################################################
  class Translator:
    def __init__(self, src, size):
      self.src = src
      self.size = size
      self.operations = {
        #Python arithmetic operators
        Operator.add: self.add,
        Operator.subtract: self.sub,
        Operator.multiply: self.mul,
        Operator.divide: self.div,
        Operator.divide_int: self.floordiv,
        Operator.mod: self.mod,
        Operator.pow: self.pow,
        #Python comparison operators
        Operator.eq: self.eq,
        Operator.ne: self.ne,
        Operator.ge: self.ge,
        Operator.gt: self.gt,
        Operator.le: self.le,
        Operator.lt: self.lt,
        #Python bit operators
        Operator.bit_and: self.bit_and,
        Operator.bit_andnot: self.bit_andnot,
        Operator.bit_or: self.bit_or,
        Operator.bit_xor: self.bit_xor,
        Operator.bit_not: self.bit_not,
        Operator.shift_left: self.shift_left,
        Operator.shift_right: self.shift_right,
        #Python boolean operators
        Operator.bool_and: self.bool_and,
        Operator.bool_or: self.bool_or,
        Operator.bool_not: self.bool_not,
        #Python intrinsics
        'abs': self.abs,
        'max': self.max,
        'min': self.min,
        'round': self.round,
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
    def vector_1_3(self, func, args):
      self.src += '%s = %s(%s, %s, %s);'%(args[0], func, args[1], args[2], args[3])
    def scalar_1_1(self, func, args):
      output, input = args
      for i in range(self.size):
        self.src += '%s[%d] = %s(%s[%d]);'%(output, i, func, input, i)
    def scalar_1_2(self, func, args):
      output, left, right = args
      for i in range(self.size):
        self.src += '%s[%d] = %s(%s[%d], %s[%d]);'%(output, i, func, left, i, right, i)
    def mask_1_2(self, input, output, mask, or_, and_, andnot_):
      if mask == 'MASK_TRUE':
        self.src += '%s = %s;'%(output, input)
      else:
        self.src += '%s = %s(%s(%s, %s), %s(%s, %s));'%(output, or_, and_, mask, input, andnot_, mask, output)
    def error(self):
      raise Exception('Not implemented')
    #Abstract stubs
    #Misc
    def setup(self):
      self.error()
    def set(self, *args):
      self.error()
    def load(self, *args):
      self.error()
    def store(self, *args):
      self.error()
    def mask(self, *args):
      self.error()
    #Python arithmetic operators
    def add(self, *args):
      self.error()
    def sub(self, *args):
      self.error()
    def mul(self, *args):
      self.error()
    def div(self, *args):
      self.error()
    def floordiv(self, *args):
      self.error()
    def mod(self, *args):
      self.error()
    def pow(self, *args):
      self.error()
    #Python comparison operators
    def eq(self, *args):
      self.error()
    def ne(self, *args):
      self.error()
    def ge(self, *args):
      self.error()
    def gt(self, *args):
      self.error()
    def le(self, *args):
      self.error()
    def lt(self, *args):
      self.error()
    #Python bit operators
    def bit_and(self, *args):
      self.error()
    def bit_andnot(self, *args):
      self.error()
    def bit_or(self, *args):
      self.error()
    def bit_xor(self, *args):
      self.error()
    def bit_not(self, *args):
      self.error()
    def shift_left(self, *args):
      self.error()
    def shift_right(self, *args):
      self.error()
    #Python boolean operators
    def bool_and(self, *args):
      self.error()
    def bool_or(self, *args):
      self.error()
    def bool_not(self, *args):
      self.error()
    #Python intrinsics
    def abs(self, *args):
      self.error()
    def max(self, *args):
      self.error()
    def min(self, *args):
      self.error()
    def round(self, *args):
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

  ################################################################################
  # Translates kernel operations into vectorized C++ code (SSE4.2, 32-bit float)
  ################################################################################
  class SSE4_Float(Translator):
    def __init__(self, src, size):
      Compiler_Intel.Translator.__init__(self, src, size)
      self.type = '__m128'
      self.test = '_mm_movemask_ps'
    #Misc
    def setup(self):
      self.src += 'const %s MASK_FALSE = _mm_setzero_ps();'%(self.type)
      self.src += 'const %s MASK_TRUE = _mm_cmpeq_ps(MASK_FALSE, MASK_FALSE);'%(self.type)
      #for i in range(self.size):
      #  slots = []
      #  for j in range(self.size):
      #    slots.append('%ff'%(1 if i == j else 0))
      #  slots.reverse()
      #  lane = '_mm_cmpneq_ps(MASK_FALSE, _mm_set_ps(%s))'%(', '.join(slots))
      #  self.src += 'const %s MASK_LANE_%d = %s;'%(self.type, i, lane)
    def set(self, *args):
      self.vector_1_1('_mm_set1_ps', args)
    def load(self, *args):
      self.vector_1_1('_mm_load_ps', args)
    def store(self, *args):
      self.vector_0_2('_mm_store_ps', args)
    def mask(self, *args):
      (input, output, mask) = args
      self.mask_1_2(input, output, mask, '_mm_or_ps', '_mm_and_ps', '_mm_andnot_ps')
    #Python arithmetic operators
    def add(self, *args):
      self.vector_1_2('_mm_add_ps', args)
    def sub(self, *args):
      self.vector_1_2('_mm_sub_ps', args)
    def mul(self, *args):
      self.vector_1_2('_mm_mul_ps', args)
    def div(self, *args):
      self.vector_1_2('_mm_div_ps', args)
    def floordiv(self, *args):
      self.div(*args)
      self.floor(args[0], args[0])
    def mod(self, *args):
      self.scalar_1_2('fmod', args)
    def pow(self, *args):
      self.scalar_1_2('pow', args)
    #Python comparison operators
    def eq(self, *args):
      self.vector_1_2('_mm_cmpeq_ps', args)
    def ne(self, *args):
      self.vector_1_2('_mm_cmpneq_ps', args)
    def ge(self, *args):
      self.vector_1_2('_mm_cmpge_ps', args)
    def gt(self, *args):
      self.vector_1_2('_mm_cmpgt_ps', args)
    def le(self, *args):
      self.vector_1_2('_mm_cmple_ps', args)
    def lt(self, *args):
      self.vector_1_2('_mm_cmplt_ps', args)
    #Python bit operators
    def bit_and(self, *args):
      self.vector_1_2('_mm_and_ps', args)
    def bit_andnot(self, *args):
      self.vector_1_2('_mm_andnot_ps', args)
    def bit_or(self, *args):
      self.vector_1_2('_mm_or_ps', args)
    def bit_xor(self, *args):
      self.vector_1_2('_mm_xor_ps', args)
    def bit_not(self, *args):
      args += ('MASK_TRUE',)
      self.bit_xor(*args)
    #Python boolean operators
    def bool_and(self, *args):
      self.bit_and(*args)
    def bool_or(self, *args):
      self.bit_or(*args)
    def bool_not(self, *args):
      self.bit_not(*args)
    #Python intrinsics
    def abs(self, *args):
      self.scalar_1_1('fabs', args)
    def max(self, *args):
      self.vector_1_2('_mm_max_ps', args)
    def min(self, *args):
      self.vector_1_2('_mm_min_ps', args)
    def round(self, *args):
      args += ('(_MM_FROUND_TO_NEAREST_INT | _MM_FROUND_NO_EXC)',)
      self.vector_1_2('_mm_round_ps', args)
    #Math functions (binary)
    def atan2(self, *args):
      self.scalar_1_2('atan2', args)
    def copysign(self, *args):
      self.scalar_1_2('copysign', args)
    def fmod(self, *args):
      self.scalar_1_2('fmod', args)
    def hypot(self, *args):
      self.scalar_1_2('hypot', args)
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
      args += ('(_MM_FROUND_TO_POS_INF | _MM_FROUND_NO_EXC)',)
      self.vector_1_2('_mm_round_ps', args)
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
    def floor(self, *args):
      args += ('(_MM_FROUND_TO_NEG_INF | _MM_FROUND_NO_EXC)',)
      self.vector_1_2('_mm_round_ps', args)
    def gamma(self, *args):
      self.scalar_1_1('tgamma', args)
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
      args += ('(_MM_FROUND_TO_ZERO | _MM_FROUND_NO_EXC)',)
      self.vector_1_2('_mm_round_ps', args)

  ################################################################################
  # Translates kernel operations into vectorized C++ code (SSE4.2, 32-bit uint)
  ################################################################################
  class SSE4_UInt32(Translator):
    def __init__(self, src, size):
      Compiler_Intel.Translator.__init__(self, src, size)
      self.type = '__m128i'
      self.test = '_mm_movemask_epi8'
    #Misc
    def setup(self):
      self.src += 'const %s MASK_FALSE = _mm_setzero_si128();'%(self.type)
      self.src += 'const %s MASK_TRUE = _mm_cmpeq_epi32(MASK_FALSE, MASK_FALSE);'%(self.type)
      self.src += 'const %s SIGN_BITS = _mm_set1_epi32(0x80000000);'%(self.type)
      for i in range(self.size):
        slots = []
        for j in range(self.size):
          slots.append('%d'%(1 if i == j else 0))
        slots.reverse()
        lane = '_mm_xor_si128(MASK_TRUE, _mm_cmpeq_epi32(MASK_FALSE, _mm_set_epi32(%s)))'%(', '.join(slots))
        self.src += 'const %s MASK_LANE_%d = %s;'%(self.type, i, lane)
    def set(self, *args):
      self.vector_1_1('_mm_set1_epi32', args)
    def load(self, *args):
      args = (args[0], '(const %s*)(%s)'%(self.type, args[1]))
      self.vector_1_1('_mm_load_si128', args)
    def store(self, *args):
      args = ('(%s*)(%s)'%(self.type, args[0]), args[1])
      self.vector_0_2('_mm_store_si128', args)
    def mask(self, *args):
      (input, output, mask) = args
      self.mask_1_2(input, output, mask, '_mm_or_si128', '_mm_and_si128', '_mm_andnot_si128')
    #Python arithmetic operators
    def add(self, *args):
      self.vector_1_2('_mm_add_epi32', args)
    def sub(self, *args):
      self.vector_1_2('_mm_sub_epi32', args)
    def mul(self, *args):
      self.vector_1_2('_mm_mullo_epi32', args)
    #Python comparison operators
    def eq(self, *args):
      self.vector_1_2('_mm_cmpeq_epi32', args)
    def ne(self, *args):
      #Not equal
      self.bit_not(args[0], '_mm_cmpeq_epi32(%s, %s)'%(args[1], args[2]))
    def ge(self, *args):
      #Not less than
      args = (args[0], '_mm_xor_si128(SIGN_BITS, %s)'%(args[1]), '_mm_xor_si128(SIGN_BITS, %s)'%(args[2]))
      self.bit_not(args[0], '_mm_cmplt_epi32(%s, %s)'%(args[1], args[2]))
    def gt(self, *args):
      args = (args[0], '_mm_xor_si128(SIGN_BITS, %s)'%(args[1]), '_mm_xor_si128(SIGN_BITS, %s)'%(args[2]))
      self.vector_1_2('_mm_cmpgt_epi32', args)
    def le(self, *args):
      #Not greater than
      args = (args[0], '_mm_xor_si128(SIGN_BITS, %s)'%(args[1]), '_mm_xor_si128(SIGN_BITS, %s)'%(args[2]))
      self.bit_not(args[0], '_mm_cmpgt_epi32(%s, %s)'%(args[1], args[2]))
    def lt(self, *args):
      args = (args[0], '_mm_xor_si128(SIGN_BITS, %s)'%(args[1]), '_mm_xor_si128(SIGN_BITS, %s)'%(args[2]))
      self.vector_1_2('_mm_cmplt_epi32', args)
    #Python bit operators
    def bit_and(self, *args):
      self.vector_1_2('_mm_and_si128', args)
    def bit_andnot(self, *args):
      self.vector_1_2('_mm_andnot_si128', args)
    def bit_or(self, *args):
      self.vector_1_2('_mm_or_si128', args)
    def bit_xor(self, *args):
      self.vector_1_2('_mm_xor_si128', args)
    def bit_not(self, *args):
      args += ('MASK_TRUE',)
      self.bit_xor(*args)
    def shift_left(self, *args):
      if len(args) == 4 and args[3]:
        #Shifting all lanes by the same constant
        self.vector_1_2('_mm_slli_epi32', args[0:3])
      else:
        #Shift each lane separately
        (output, left, right) = args
        for i in range(self.size):
          mask = 'MASK_LANE_%d'%(i)
          input = '_mm_slli_epi32(%s, _mm_extract_epi32(%s, %d))'%(left, right, i)
          self.src += '%s = _mm_or_si128(_mm_and_si128(%s, %s), _mm_andnot_si128(%s, %s));'%(output, mask, input, mask, output)
    def shift_right(self, *args):
      if len(args) == 4 and args[3]:
        #Shifting all lanes by the same constant
        self.vector_1_2('_mm_srli_epi32', args[0:3])
      else:
        #Shift each lane separately
        (output, left, right) = args
        for i in range(self.size):
          mask = 'MASK_LANE_%d'%(i)
          input = '_mm_srli_epi32(%s, _mm_extract_epi32(%s, %d))'%(left, right, i)
          self.src += '%s = _mm_or_si128(_mm_and_si128(%s, %s), _mm_andnot_si128(%s, %s));'%(output, mask, input, mask, output)
    #Python boolean operators
    def bool_and(self, *args):
      self.bit_and(*args)
    def bool_or(self, *args):
      self.bit_or(*args)
    def bool_not(self, *args):
      self.bit_not(*args)
    #Python intrinsics
    def max(self, *args):
      args = (args[0], '_mm_xor_si128(SIGN_BITS, %s)'%(args[1]), '_mm_xor_si128(SIGN_BITS, %s)'%(args[2]))
      self.src += '%s = _mm_xor_si128(SIGN_BITS, _mm_max_epi32(%s, %s));'%(args[0], args[1], args[2])
    def min(self, *args):
      args = (args[0], '_mm_xor_si128(SIGN_BITS, %s)'%(args[1]), '_mm_xor_si128(SIGN_BITS, %s)'%(args[2]))
      self.src += '%s = _mm_xor_si128(SIGN_BITS, _mm_min_epi32(%s, %s));'%(args[0], args[1], args[2])
    #Experimental - array access
    def array_read(self, *args):
      (output, array, index, stride) = args
      for i in range(self.size):
        mask = 'MASK_LANE_%d'%(i)
        input = '_mm_set1_epi32(%s[%d + _mm_extract_epi32(%s, %d)])'%(array, stride * i, index, i)
        self.src += '%s = _mm_or_si128(_mm_and_si128(%s, %s), _mm_andnot_si128(%s, %s));'%(output, mask, input, mask, output)
    def array_write(self, *args):
      (input, array, index, stride) = args
      for i in range(self.size):
        self.src += '%s[%d + _mm_extract_epi32(%s, %d)] = _mm_extract_epi32(%s, %d);'%(array, stride * i, index, i, input, i)

  ################################################################################
  # Translates kernel operations into vectorized C++ code (AVX2, 32-bit float)
  ################################################################################
  class AVX2_Float(Translator):
    def __init__(self, src, size):
      Compiler_Intel.Translator.__init__(self, src, size)
      self.type = '__m256'
      self.test = '_mm256_movemask_ps'
    #Misc
    def setup(self):
      self.src += 'const %s MASK_FALSE = _mm256_setzero_ps();'%(self.type)
      self.src += 'const %s MASK_TRUE = _mm256_cmp_ps(MASK_FALSE, MASK_FALSE, _CMP_EQ_UQ);'%(self.type)
    def set(self, *args):
      self.vector_1_1('_mm256_set1_ps', args)
    def load(self, *args):
      self.vector_1_1('_mm256_load_ps', args)
    def store(self, *args):
      self.vector_0_2('_mm256_store_ps', args)
    def mask(self, *args):
      (input, output, mask) = args
      self.mask_1_2(input, output, mask, '_mm256_or_ps', '_mm256_and_ps', '_mm256_andnot_ps')
    #Python arithmetic operators
    def add(self, *args):
      self.vector_1_2('_mm256_add_ps', args)
    def sub(self, *args):
      self.vector_1_2('_mm256_sub_ps', args)
    def mul(self, *args):
      self.vector_1_2('_mm256_mul_ps', args)
    def div(self, *args):
      self.vector_1_2('_mm256_div_ps', args)
    def floordiv(self, *args):
      self.div(*args)
      self.floor(args[0], args[0])
    def mod(self, *args):
      self.scalar_1_2('fmod', args)
    def pow(self, *args):
      self.scalar_1_2('pow', args)
    #Python comparison operators
    def eq(self, *args):
      args += ('_CMP_EQ_UQ',)
      self.vector_1_3('_mm256_cmp_ps', args)
    def ne(self, *args):
      args += ('_CMP_NEQ_UQ',)
      self.vector_1_3('_mm256_cmp_ps', args)
    def ge(self, *args):
      args += ('_CMP_GE_OQ',)
      self.vector_1_3('_mm256_cmp_ps', args)
    def gt(self, *args):
      args += ('_CMP_GT_OQ',)
      self.vector_1_3('_mm256_cmp_ps', args)
    def le(self, *args):
      args += ('_CMP_LE_OQ',)
      self.vector_1_3('_mm256_cmp_ps', args)
    def lt(self, *args):
      args += ('_CMP_LT_OQ',)
      self.vector_1_3('_mm256_cmp_ps', args)
    #Python bit operators
    def bit_and(self, *args):
      self.vector_1_2('_mm256_and_ps', args)
    def bit_andnot(self, *args):
      self.vector_1_2('_mm256_andnot_ps', args)
    def bit_or(self, *args):
      self.vector_1_2('_mm256_or_ps', args)
    def bit_xor(self, *args):
      self.vector_1_2('_mm256_xor_ps', args)
    def bit_not(self, *args):
      args += ('MASK_TRUE',)
      self.bit_xor(*args)
    #Python boolean operators
    def bool_and(self, *args):
      self.bit_and(*args)
    def bool_or(self, *args):
      self.bit_or(*args)
    def bool_not(self, *args):
      self.bit_not(*args)
    #Python intrinsics
    def abs(self, *args):
      self.scalar_1_1('fabs', args)
    def max(self, *args):
      self.vector_1_2('_mm256_max_ps', args)
    def min(self, *args):
      self.vector_1_2('_mm256_min_ps', args)
    def round(self, *args):
      args += ('(_MM_FROUND_TO_NEAREST_INT | _MM_FROUND_NO_EXC)',)
      self.vector_1_2('_mm256_round_ps', args)
    #Math functions (binary)
    def atan2(self, *args):
      self.scalar_1_2('atan2', args)
    def copysign(self, *args):
      self.scalar_1_2('copysign', args)
    def fmod(self, *args):
      self.scalar_1_2('fmod', args)
    def hypot(self, *args):
      self.scalar_1_2('hypot', args)
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
      args += ('(_MM_FROUND_TO_POS_INF | _MM_FROUND_NO_EXC)',)
      self.vector_1_2('_mm256_round_ps', args)
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
    def floor(self, *args):
      args += ('(_MM_FROUND_TO_NEG_INF | _MM_FROUND_NO_EXC)',)
      self.vector_1_2('_mm256_round_ps', args)
    def gamma(self, *args):
      self.scalar_1_1('tgamma', args)
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
    def sin(self, *args):
      self.scalar_1_1('sin', args)
    def sinh(self, *args):
      self.scalar_1_1('sinh', args)
    def sqrt(self, *args):
      self.vector_1_1('_mm256_sqrt_ps', args)
    def tan(self, *args):
      self.scalar_1_1('tan', args)
    def tanh(self, *args):
      self.scalar_1_1('tanh', args)
    def trunc(self, *args):
      args += ('(_MM_FROUND_TO_ZERO | _MM_FROUND_NO_EXC)',)
      self.vector_1_2('_mm256_round_ps', args)

  ################################################################################
  # Translates kernel operations into vectorized C++ code (AVX2, 32-bit uint)
  ################################################################################
  class AVX2_UInt32(Translator):
    def __init__(self, src, size):
      Compiler_Intel.Translator.__init__(self, src, size)
      self.type = '__m256i'
      self.test = '_mm256_movemask_epi8'
    #Misc
    def setup(self):
      self.src += 'const %s MASK_FALSE = _mm256_setzero_si256();'%(self.type)
      self.src += 'const %s MASK_TRUE = _mm256_cmpeq_epi32(MASK_FALSE, MASK_FALSE);'%(self.type)
      self.src += 'const %s SIGN_BITS = _mm256_set1_epi32(0x80000000);'%(self.type)
      for i in range(self.size):
        slots = []
        for j in range(self.size):
          slots.append('%d'%(1 if i == j else 0))
        slots.reverse()
        lane = '_mm256_xor_si256(MASK_TRUE, _mm256_cmpeq_epi32(MASK_FALSE, _mm256_set_epi32(%s)))'%(', '.join(slots))
        self.src += 'const %s MASK_LANE_%d = %s;'%(self.type, i, lane)
    def set(self, *args):
      self.vector_1_1('_mm256_set1_epi32', args)
    def load(self, *args):
      args = (args[0], '(const %s*)(%s)'%(self.type, args[1]))
      self.vector_1_1('_mm256_load_si256', args)
    def store(self, *args):
      args = ('(%s*)(%s)'%(self.type, args[0]), args[1])
      self.vector_0_2('_mm256_store_si256', args)
    def mask(self, *args):
      (input, output, mask) = args
      self.mask_1_2(input, output, mask, '_mm256_or_si256', '_mm256_and_si256', '_mm256_andnot_si256')
    #Python arithmetic operators
    def add(self, *args):
      self.vector_1_2('_mm256_add_epi32', args)
    def sub(self, *args):
      self.vector_1_2('_mm256_sub_epi32', args)
    def mul(self, *args):
      self.vector_1_2('_mm256_mullo_epi32', args)
    #Python comparison operators
    def eq(self, *args):
      self.vector_1_2('_mm256_cmpeq_epi32', args)
    def ne(self, *args):
      #Not equal
      self.bit_not(args[0], '_mm256_cmpeq_epi32(%s, %s)'%(args[1], args[2]))
    def ge(self, *args):
      #Greater than or equal to
      left, right = '_mm256_xor_si256(SIGN_BITS, %s)'%(args[1]), '_mm256_xor_si256(SIGN_BITS, %s)'%(args[2])
      args = (args[0], '_mm256_cmpgt_epi32(%s, %s)'%(left, right), '_mm256_cmpeq_epi32(%s, %s)'%(args[1], args[2]))
      self.bit_or(args)
    def gt(self, *args):
      args = (args[0], '_mm256_xor_si256(SIGN_BITS, %s)'%(args[1]), '_mm256_xor_si256(SIGN_BITS, %s)'%(args[2]))
      self.vector_1_2('_mm256_cmpgt_epi32', args)
    def le(self, *args):
      #Not greater than
      args = (args[0], '_mm256_xor_si256(SIGN_BITS, %s)'%(args[1]), '_mm256_xor_si256(SIGN_BITS, %s)'%(args[2]))
      self.bit_not(args[0], '_mm256_cmpgt_epi32(%s, %s)'%(args[1], args[2]))
    def lt(self, *args):
      #Greater than with operands switched
      args = (args[0], '_mm256_xor_si256(SIGN_BITS, %s)'%(args[2]), '_mm256_xor_si256(SIGN_BITS, %s)'%(args[1]))
      self.vector_1_2('_mm256_cmpgt_epi32', args)
    #Python bit operators
    def bit_and(self, *args):
      self.vector_1_2('_mm256_and_si256', args)
    def bit_andnot(self, *args):
      self.vector_1_2('_mm256_andnot_si256', args)
    def bit_or(self, *args):
      self.vector_1_2('_mm256_or_si256', args)
    def bit_xor(self, *args):
      self.vector_1_2('_mm256_xor_si256', args)
    def bit_not(self, *args):
      args += ('MASK_TRUE',)
      self.bit_xor(*args)
    def shift_left(self, *args):
      if len(args) == 4 and args[3]:
        #Shifting all lanes by the same constant
        self.vector_1_2('_mm256_slli_epi32', args[0:3])
      else:
        #Shift each lane separately
        self.vector_1_2('_mm256_sllv_epi32', args[0:3])
    def shift_right(self, *args):
      if len(args) == 4 and args[3]:
        #Shifting all lanes by the same constant
        self.vector_1_2('_mm256_srli_epi32', args[0:3])
      else:
        #Shift each lane separately
        self.vector_1_2('_mm256_srlv_epi32', args[0:3])
    #Python boolean operators
    def bool_and(self, *args):
      self.bit_and(*args)
    def bool_or(self, *args):
      self.bit_or(*args)
    def bool_not(self, *args):
      self.bit_not(*args)
    #Python intrinsics
    def max(self, *args):
      args = (args[0], '_mm256_xor_si256(SIGN_BITS, %s)'%(args[1]), '_mm256_xor_si256(SIGN_BITS, %s)'%(args[2]))
      self.src += '%s = _mm256_xor_si256(SIGN_BITS, _mm256_max_epi32(%s, %s));'%(args[0], args[1], args[2])
    def min(self, *args):
      args = (args[0], '_mm256_xor_si256(SIGN_BITS, %s)'%(args[1]), '_mm256_xor_si256(SIGN_BITS, %s)'%(args[2]))
      self.src += '%s = _mm256_xor_si256(SIGN_BITS, _mm256_min_epi32(%s, %s));'%(args[0], args[1], args[2])
    #Experimental - array access
    def array_read(self, *args):
      (output, array, index, stride) = args
      for i in range(self.size):
        mask = 'MASK_LANE_%d'%(i)
        input = '_mm256_set1_epi32(%s[%d + _mm256_extract_epi32(%s, %d)])'%(array, stride * i, index, i)
        self.src += '%s = _mm256_or_si256(_mm256_and_si256(%s, %s), _mm256_andnot_si256(%s, %s));'%(output, mask, input, mask, output)
    def array_write(self, *args):
      (input, array, index, stride) = args
      for i in range(self.size):
        self.src += '%s[%d + _mm256_extract_epi32(%s, %d)] = _mm256_extract_epi32(%s, %d);'%(array, stride * i, index, i, input, i)
