"""
The Parser takes the Python source code of a function and
creates a Kernel object.
"""


#===========================================================
# Setup
#===========================================================
#Abstract Syntax Trees
import ast
#Inspect live objects
import inspect
#Language-independent kernel
import kernel
#Math constants
import math

#===========================================================
# Parser class
#===========================================================
#Converts Python source code into an abstract kernel
class Parser:

  #Parser constructor
  def __init__(self, name, source):
    #Initializes the kernel
    self.kernel = kernel.Kernel(name)
    #The source code to be parsed
    self.source = source
    #The docstring of the kernel function
    self.docstring = None

  #Adds an argument to the kernel
  def add_argument(self, name):
    return self.kernel.add_variable(kernel.Variable(name, True, False, None))

  #Adds a variable to the kernel if it hasn't already been defined
  def add_variable(self, name):
    var = self.kernel.get_variable(name)
    if var is None:
      var = self.kernel.add_variable(kernel.Variable(name, False, name is None, None))
    return var

  #Adds a literal to the kernel if it hasn't already been defined
  def add_literal(self, value, suffix=None):
    var = self.kernel.get_literal(value)
    if var is None:
      var = self.kernel.add_variable(kernel.Variable(None, False, False, value))
      if suffix is not None:
        var.name += '_' + suffix
    return var

  #todo: debugging
  def _dump(x, label=''):
    print('\n', '*' * 10, label, '*' * 10, '\n', ast.dump(x, annotate_fields=True, include_attributes=True), '\n')

  #Parses a binary operation (AST BinOp)
  def binop(self, node, var):
    if var == None:
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
    elif isinstance(node.op, ast.Mod):
      op = kernel.Operator.mod
    elif isinstance(node.op, ast.Pow):
      op = kernel.Operator.pow
    else:
      raise Exception('Unexpected BinOp (%s)'%(node.op.__class__))
    operation = kernel.BinaryOperation(left, op, right)
    assignment = kernel.Assignment(var, operation)
    statement = kernel.Statement(assignment)
    self.kernel.add(statement)
    return var

  #Parses a unary uperation (AST UnaryOp)
  def unaryop(self, node):
    operand = self.expression(node.operand)
    if isinstance(node.op, ast.UAdd):
      return operand
    if isinstance(node.op, ast.USub):
      if operand.value is not None:
        return self.add_literal(-operand.value)
      else:
        #Emulate negation by subtracting from zero (faster than multiplying by negative one)
        var = self.add_variable(None)
        zero = self.add_literal(0, 'ZERO')
        operation = kernel.BinaryOperation(zero, kernel.Operator.subtract, operand)
        assignment = kernel.Assignment(var, operation)
        statement = kernel.Statement(assignment)
        self.kernel.add(statement)
        return var
    else:
      raise Exception('Unexpected UnaryOp (%s)'%(node.op.__class__))

  #Parses a function call (AST Call)
  def call(self, expr, var):
    if var == None:
      var = self.add_variable(None)
    if isinstance(expr.func, ast.Attribute):
      mod = expr.func.value.id
      func = expr.func.attr
    elif isinstance(expr.func, ast.Name):
      mod = '__main__'
      func = expr.func.id
    else:
      raise Exception('Unexpected function call (%s)'%(expr.func.__class__))
    #Parse the argument list
    args = []
    for arg in expr.args:
      args.append(self.expression(arg))
    #Find the module that contains the function
    if mod == '__main__':
      #Calls to intrinsic functions
      cls = kernel.Intrinsic
    elif mod == 'math':
      #Calls to math functions
      cls = kernel.Math
    else:
      #Other calls aren't supported
      raise Exception('Call not supported (module %s)'%(mod))
    #Build the call
    if func in cls.binary_functions and len(args) == 2:
      operation = kernel.BinaryOperation(args[0], func, args[1])
    elif func in cls.unary_functions and len(args) == 1:
      operation = kernel.UnaryOperation(func, args[0])
    #Emulated functions
    elif mod == 'math' and func == 'degrees' and len(args) == 1:
      r2d = self.add_literal(180.0 / math.pi, 'R2D')
      operation = kernel.BinaryOperation(args[0], '*', r2d)
    elif mod == 'math' and func == 'radians' and len(args) == 1:
      d2r = self.add_literal(math.pi / 180.0, 'D2R')
      operation = kernel.BinaryOperation(args[0], '*', d2r)
    elif mod == 'math' and func == 'log' and len(args) == 2:
      var1 = self.add_variable(None)
      op1 = kernel.UnaryOperation(func, args[0])
      asst1 = kernel.Assignment(var1, op1)
      stmt1 = kernel.Statement(asst1)
      self.kernel.add(stmt1)
      var2 = self.add_variable(None)
      op2 = kernel.UnaryOperation(func, args[1])
      asst2 = kernel.Assignment(var2, op2)
      stmt2 = kernel.Statement(asst2)
      self.kernel.add(stmt2)
      operation = kernel.BinaryOperation(var1, '/', var2)
    #Unknown function
    else:
      raise Exception('Call not supported or invalid arguments (%s.%s)'%(mod, func))
    #Make the assignment and return the result
    assignment = kernel.Assignment(var, operation)
    statement = kernel.Statement(assignment)
    self.kernel.add(statement)
    return var

  #Parses a named attribute (AST Attribute)
  def attribute(self, attr):
    mod = attr.value.id
    name = attr.attr
    if mod == 'math':
      if name == 'pi':
        var = self.add_literal(math.pi, 'PI')
      elif name == 'e':
        var = self.add_literal(math.e, 'E')
      else:
        raise Exception('Contsant not supported (%s.%s)'%(mod, name))
    else:
      raise Exception('Constant not supported (module %s)'%(mod))
    return var

  #Parses an expression (AST Expr)
  def expression(self, expr, var=None):
    if isinstance(expr, ast.Num):
      var = self.add_literal(expr.n)
    elif isinstance(expr, ast.Name):
      var = self.kernel.get_variable(expr.id)
      if var is None:
        raise Exception('Undefined Variable (%s)'%(expr.id))
      if var.is_arg:
        var.input = True
    elif isinstance(expr, ast.BinOp):
      var = self.binop(expr, var)
    elif isinstance(expr, ast.UnaryOp):
      var = self.unaryop(expr)
    elif isinstance(expr, ast.Call):
      var = self.call(expr, var)
    elif isinstance(expr, ast.Attribute):
      var = self.attribute(expr)
    else:
      raise Exception('Unexpected Expression (%s)'%(expr.__class__))
    return var

  #Parses a single assignment
  def assign_single(self, src, dst, multi=False):
    #Make or get the destination variable
    var = self.add_variable(dst.id)
    #Set the output flag is the variable is a kernel argument
    if var.is_arg:
      var.output = True
    #Parse the expression and get the intermediate variable
    expr = self.expression(src, var if not multi else None)
    #Don't generate a self assignment
    if var != expr:
      #Create a temporary variable if this is a multi-assignment
      if multi and not expr.is_temp:
        temp = self.add_variable(None)
        assignment = kernel.Assignment(temp, expr)
        statement = kernel.Statement(assignment)
        self.kernel.add(statement)
        expr = temp
      #The final assignment will be added to the kernel later
      assignment = kernel.Assignment(var, expr)
      statement = kernel.Statement(assignment)
      return statement
    else:
      return None

  #Parses (possibly multiple) assignments (AST Assign)
  def assign(self, stmt):
    #Add this (python source) line as a (c++ kernel) comment
    comment = kernel.Comment(self.source.split('\n')[stmt.lineno - 1].strip())
    self.kernel.add(comment)
    #Evaluate the assignment(s)
    value = stmt.value
    for i in range(len(stmt.targets)):
      target = stmt.targets[i]
      if isinstance(target, ast.Name):
        result = self.assign_single(value, target)
        if result is not None:
          self.kernel.add(result)
      elif isinstance(target, ast.Tuple):
        #Save intermediate results
        results = []
        #Evaluate individual assignments
        for (t, v) in zip(target.elts, stmt.value.elts):
          results.append(self.assign_single(v, t, multi=True))
        #Execute final assignments after intermediate calculations
        for result in results:
          self.kernel.add(result)
      else:
        raise Exception('Unexpected Assignment (%s)'%(target.__class__))

  #Parses a single returned element
  def return_single(self, val):
    if not isinstance(val, ast.Name):
      raise Exception('Bad return type (%s)'%(val.__class__))
    var = self.kernel.get_variable(val.id)
    if var is None:
      raise Exception('Bad return type (%s)'%('undefined variable'))
    if not var.is_arg:
      raise Exception('Bad return type (%s)'%('not an argument'))

  #Parses (possibly multiple) returns (AST Return)
  def return_(self, ret):
    if ret.value is None:
      raise Exception('Bad return type (%s)'%('must return something'))
    elif isinstance(ret.value, ast.Tuple):
      for elem in ret.value.elts:
        self.return_single(elem)
    else:
      self.return_single(ret.value)

  #Parses the docstring of a function
  def docstring_(self, stmt):
    if self.docstring is not None:
      raise Exception('Docstring already defined')
    if not isinstance(stmt.value, ast.Str):
      raise Exception('Bad docstring type (%s)'%(stmt.value.__class__))
    self.docstring = stmt.value.s
    self.kernel.set_docstring(self.docstring)

  #Parses statements (AST Stmt)
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
  #Parses the kernel using the specified live function
  def parse(kernel):
    return Parser.parseFromSource(inspect.getsource(kernel), kernel.__name__)

  #Parses the kernel defined in a file
  def parseFromFile(file_name, kernel_name):
    #Source file
    with open(file_name, 'r') as file:
      source_code = file.read()
    return Parser.parseFromSource(source_code, kernel_name)

  #Parses the kernel defined in a string of source code
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

      #The source code has been parsed, return the abstract kernel
      return parser.kernel

    #The kernel wasn't found
    raise Exception('Kernel function not found (%s)'%(kernel_name))
