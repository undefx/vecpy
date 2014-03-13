#===========================================================
# Setup
#===========================================================
#Abstract Syntax Trees
import ast
#Inspect live objects
import inspect
#Language-independent kernel
import kernel

#===========================================================
# Parser class
#===========================================================
class Parser:
  def __init__(self, name, source):
    self.kernel = kernel.Kernel(name)
    self.source = source
    self.docstring = None

  def add_argument(self, name):
    return self.kernel.add_variable(kernel.Variable(name, True, None))

  def add_variable(self, name):
    var = self.kernel.get_variable(name)
    if var is None:
      var = self.kernel.add_variable(kernel.Variable(name, False, None))
    return var

  def add_literal(self, value):
    var = self.kernel.get_literal(value)
    if var is None:
      var = self.kernel.add_variable(kernel.Variable(None, False, value))
    return var

  def _dump(x, label=''):
    print('\n', '*' * 10, label, '*' * 10, '\n', ast.dump(x, annotate_fields=True, include_attributes=True), '\n')

  def binop(self, node):
    var = self.add_variable(None)
    left = self.expression(node.left)
    right = self.expression(node.right)
    if isinstance(node.op, ast.Add):
      op = kernel.Operator.add
    elif isinstance(node.op, ast.Sub):
      op = kernel.Operator.subtract
    elif isinstance(node.op, ast.Mult):
      op = kernel.Operator.multiply
    elif isinstance(node.op, ast.Div):
      op = kernel.Operator.divide
    elif isinstance(node.op, ast.Pow):
      op = kernel.Operator.pow
    else:
      raise Exception('Unexpected BinOp (%s)'%(node.op.__class__))
    operation = kernel.BinaryOperation(left, op, right)
    assignment = kernel.Assignment(var, operation)
    statement = kernel.Statement(assignment)
    self.kernel.add(statement)
    return var

  #def unaryop(self, node):
  #  operand = self.expression(node.operand)
  #  if isinstance(node.op, ast.UAdd):
  #    return operand
  #  if isinstance(node.op, ast.USub):
  #    if 'value' in operand:
  #      if -operand['value'] in self.literals:
  #        return self.literals[-operand['value']]
  #      else:
  #        return self.add_literal(-operand['value'])
  #    else:
  #      raise Exception('todo: negate an expression')
  #  else:
  #    raise Exception('Unexpected UnaryOp (%s)'%(node.op.__class__))

  def expression(self, expr):
    var = None
    if isinstance(expr, ast.Num):
      var = self.add_literal(expr.n)
    elif isinstance(expr, ast.Name):
      var = self.kernel.get_variable(expr.id)
      if var is None:
        raise Exception('Undefined Variable (%s)'%(expr.id))
      if var.is_arg:
        var.input = True
    elif isinstance(expr, ast.BinOp):
      var = self.binop(expr)
    #elif isinstance(expr, ast.UnaryOp):
    #  var = self.unaryop(expr)
    else:
      raise Exception('Unexpected Expression (%s)'%(expr.__class__))
    return var

  def assign_single(self, src, dst):
    comment = kernel.Comment(self.source.split('\n')[dst.lineno - 1].strip())
    self.kernel.add(comment)
    expr = self.expression(src)
    var = self.add_variable(dst.id)
    assignment = kernel.Assignment(var, expr)
    statement = kernel.Statement(assignment)
    self.kernel.add(statement)
    if var.is_arg:
      var.output = True

  def assign(self, stmt):
    value = stmt.value
    for i in range(len(stmt.targets)):
      target = stmt.targets[i]
      if isinstance(target, ast.Name):
        self.assign_single(value, target)
      elif isinstance(target, ast.Tuple):
        for (t, v) in zip(target.elts, stmt.value.elts):
          self.assign_single(v, t)
      else:
        raise Exception('Unexpected Assignment (%s)'%(target.__class__))

  def return_single(self, val):
    if not isinstance(val, ast.Name):
      raise Exception('Bad return type (%s)'%(val.__class__))
    var = self.kernel.get_variable(val.id)
    if var is None:
      raise Exception('Bad return type (%s)'%('undefined variable'))
    if not var.is_arg:
      raise Exception('Bad return type (%s)'%('not an argument'))

  def return_(self, ret):
    if ret.value is None:
      raise Exception('Bad return type (%s)'%('must return something'))
    elif isinstance(ret.value, ast.Tuple):
      for elem in ret.value.elts:
        self.return_single(elem)
    else:
      self.return_single(ret.value)

  def docstring_(self, stmt):
    if self.docstring is not None:
      raise Exception('Docstring already defined')
    if not isinstance(stmt.value, ast.Str):
      raise Exception('Bad docstring type (%s)'%(stmt.value.__class__))
    self.docstring = stmt.value.s
    self.kernel.set_docstring(self.docstring)

  def statement(self, stmt):
    if isinstance(stmt, ast.Assign):
      self.assign(stmt)
    elif isinstance(stmt, ast.Return):
      self.return_(stmt)
    elif isinstance(stmt, ast.Expr):
      self.docstring_(stmt)
    else:
      Parser._dump(stmt, 'unsupported statement')
      raise Exception('unsupported statement')

  #===========================================================
  # Public interface
  #===========================================================
  def parse(kernel):
    return Parser.parseFromSource(inspect.getsource(kernel), kernel.__name__)

  def parseFromFile(file_name, kernel_name):
    #Source file
    with open(file_name, 'r') as file:
      source_code = file.read()
    return Parser.parseFromSource(source_code, kernel_name)

  def parseFromSource(source_code, kernel_name):
    #Parse the source to build the AST
    root = ast.parse(source_code)

    #Sanity check - the root node should be a module
    if not isinstance(root, ast.Module):
      raise Exception('Expected Module (%s)'%(root.__class__))
    #else:
    #  print("Parsed successfully!")

    #Compile things in the module one at a time
    for node in ast.iter_child_nodes(root):

      #Currently only functions are supported
      if not isinstance(node, ast.FunctionDef):
        print('Node not supported:', node)
        continue

      #Find the kernel
      if node.name != kernel_name:
        print('Skipping function:', node.name)
        continue

      #Make sure there are no decorators
      #todo: clever use of decorators...
      #todo: check node.returns
      if len(node.decorator_list) > 0:
        raise Exception('Decorators not supported')

      #Get the function name
      print("Found '%s' on line %d!"%(kernel_name, node.lineno))

      #Make a parser for this kernel
      parser = Parser(kernel_name, source_code)

      #Get the function's arguments
      for arg in node.args.args:
        parser.add_argument(arg.arg)

      #The body!
      for stmt in node.body:
        parser.statement(stmt)

      #todo: Finished?
      print("Done!")
      return parser.kernel

    return None