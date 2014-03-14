class Variable:
  index = 0
  def __init__(self, name, is_arg, is_temp, value):
    if name is None:
      if value is None:
        prefix = 'var'
      else:
        prefix = 'lit'
      name = '%s%03d'%(prefix, Variable.index)
    self.name = name
    self.is_arg = is_arg
    self.is_temp = is_temp
    self.value = value
    self.index = Variable.index
    self.input = False
    self.output = False
    Variable.index += 1

class Operator:
  add = '+'
  subtract = '-'
  multiply = '*'
  divide = '/'
  pow = '**'

class Math:
  binary_functions = (
    'hypot',
    #'copysign',
    #'fmod',
    #'ldexp',
    #'log',
    'pow',
    'atan2',
  )
  unary_functions = (
    'ceil',
    'fabs',
    #'factorial',
    'floor',
    #'frexp',
    #'fsum',
    #'isfinite',
    #'isinf',
    #'isnan',
    #'modf',
    #'trunc',
    'exp',
    #'expm1',
    #'log1p',
    #'log2',
    #'log10',
    'sqrt',
    'acos',
    'asin',
    'atan',
    'cos',
    'sin',
    'tan',
    #'degrees',
    #'radians',
    'acosh',
    'asinh',
    'atanh',
    'cosh',
    'sinh',
    'tanh',
    #'erf',
    #'erfc',
    #'gamma',
    #'lgamma',
  )

class BinaryOperation:
  def __init__(self, left, op, right):
    self.left = left
    self.op = op
    self.right = right

class UnaryOperation:
  def __init__(self, op, var):
    self.op = op
    self.var = var

class Assignment:
  def __init__(self, var, expr):
    if var is None:
      raise Exception('var is None')
    self.var = var
    self.expr = expr

class Comment:
  def __init__(self, comment):
    self.comment = comment

class Statement:
  def __init__(self, stmt):
    self.stmt = stmt

class Block:
  def __init__(self):
    self.stmts = []
  def add_statement(self, stmt):
    self.stmts.append(stmt)

class Kernel:
  def __init__(self, name):
    self.name = name
    self.variables = {}
    self.arguments = {}
    self.literals = {}
    self.code = []
    self.docstring = 'An undocumented (but probably awesome) kernel function.'

  def get_variable(self, name):
    if name in self.variables:
      return self.variables[name]
    else:
      return None

  def get_literal(self, value):
    if value in self.literals:
      return self.literals[value]
    else:
      return None

  def add_variable(self, var):
    self.variables[var.name] = var
    if var.is_arg:
      self.arguments[var.name] = var
    if var.value is not None:
      self.literals[var.value] = var
    return var

  def add(self, stmt):
    if isinstance(stmt, Statement):
      pass
    elif isinstance(stmt, Comment):
      pass
    else:
      raise Exception('can\'t add that (%s)'%(stmt.__class__))
    self.code.append(stmt)

  def set_docstring(self, docstring):
    self.docstring = docstring
  
  def get_arguments(self, input=False, output=False):
    args = sorted(list(self.arguments.values()), key=lambda arg: arg.index)
    return [arg for arg in args if (not input or arg.input) and (not output or arg.output)]

  def get_literals(self):
    return sorted(list(self.literals.values()), key=lambda lit: lit.value)

  def get_variables(self):
    vars = sorted(list(self.variables.values()), key=lambda var: var.index)
    return [var for var in vars if var.value is None]

  def get_type(self):
    return 'float'