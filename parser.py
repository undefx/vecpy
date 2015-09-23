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
#Math constants
import math
#Language-independent kernel
from vecpy.kernel import *

#===========================================================
# Parser class
#===========================================================
#Converts Python source code into an abstract kernel
class Parser:

  #Parser constructor
  def __init__(self, name, source):
    #Initializes the kernel
    self.kernel = Kernel(name)
    #The source code to be parsed
    self.source = source
    #The docstring of the kernel function
    self.docstring = None

  #Adds an argument to the kernel
  def add_argument(self, name, is_uniform, stride):
    return self.kernel.add_variable(Variable(name=name, is_arg=True, is_uniform=is_uniform, stride=stride))

  #Adds a variable to the kernel if it hasn't already been defined
  def add_variable(self, name, is_mask=False):
    var = self.kernel.get_variable(name)
    if var is None:
      is_temp = name is None
      var = self.kernel.add_variable(Variable(name=name, is_temp=is_temp, is_mask=is_mask))
    return var

  #Adds a literal to the kernel if it hasn't already been defined
  def add_literal(self, value, suffix=None):
    var = self.kernel.get_literal(value)
    if var is None:
      var = self.kernel.add_variable(Variable(value=value))
      if suffix is not None:
        var.name += '_' + suffix
    return var

  #Adds this (Python source) line as a (C++ source) comment
  def add_comment(self, block, src):
    comment = Comment(self.source.split('\n')[src.lineno - 1].strip())
    block.add(comment)

  #todo: debugging
  def _dump(x, label=''):
    print('\n', '*' * 10, label, '*' * 10, '\n', ast.dump(x, annotate_fields=True, include_attributes=True), '\n')

  #Parses a binary operation (AST BinOp)
  def binop(self, block, node, var=None):
    if var == None:
      var = self.add_variable(None)
    left = self.expression(block, node.left)
    right = self.expression(block, node.right)
    if isinstance(node.op, ast.Add):
      op = Operator.add
    elif isinstance(node.op, ast.Sub):
      op = Operator.subtract
    elif isinstance(node.op, ast.Mult):
      op = Operator.multiply
    elif isinstance(node.op, ast.Div):
      op = Operator.divide
    elif isinstance(node.op, ast.FloorDiv):
      op = Operator.divide_int
    elif isinstance(node.op, ast.Mod):
      op = Operator.mod
    elif isinstance(node.op, ast.Pow):
      op = Operator.pow
    elif isinstance(node.op, ast.BitAnd):
      op = Operator.bit_and
    elif isinstance(node.op, ast.BitOr):
      op = Operator.bit_or
    elif isinstance(node.op, ast.BitXor):
      op = Operator.bit_xor
    elif isinstance(node.op, ast.LShift):
      op = Operator.shift_left
    elif isinstance(node.op, ast.RShift):
      op = Operator.shift_right
    else:
      raise Exception('Unexpected BinOp (%s)'%(node.op.__class__))
    operation = BinaryOperation(left, op, right)
    assignment = Assignment(var, operation)
    block.add(assignment)
    return var

  #Parses a unary uperation (AST UnaryOp)
  def unaryop(self, block, node):
    operand = self.expression(block, node.operand)
    if isinstance(node.op, ast.UAdd):
      #No-Op
      var = operand
    elif isinstance(node.op, ast.USub):
      if operand.value is not None:
        #It's a literal, return the negation
        var = self.add_literal(-operand.value)
      else:
        #It's an expression, subtract from zero (faster than multiplying by -1)
        var = self.add_variable(None)
        zero = self.add_literal(0, 'ZERO')
        operation = BinaryOperation(zero, Operator.subtract, operand)
        assignment = Assignment(var, operation)
        block.add(assignment)
    elif isinstance(node.op, ast.Invert):
      #Make sure it's numeric
      if operand.is_mask:
        raise Exception('Unary invert requires a numeric operand')
      #Bit-flip
      var = self.add_variable(None)
      operation = UnaryOperation(Operator.bit_not, operand)
      assignment = Assignment(var, operation)
      block.add(assignment)
    elif isinstance(node.op, ast.Not):
      #Make sure it's boolean
      if not operand.is_mask:
        raise Exception('Unary not requires a boolean operand')
      #Invert the mask
      var = self.add_variable(None, is_mask=True)
      operation = UnaryOperation(Operator.bool_not, operand)
      assignment = Assignment(var, operation)
      block.add(assignment)
    else:
      raise Exception('Unexpected UnaryOp (%s)'%(node.op.__class__))
    return var

  #Parses a comparison operator (AST CmpOp)
  def cmpop(self, op):
    if isinstance(op, ast.Eq):
      return Operator.eq
    elif isinstance(op, ast.NotEq):
      return Operator.ne
    elif isinstance(op, ast.Lt):
      return Operator.lt
    elif isinstance(op, ast.LtE):
      return Operator.le
    elif isinstance(op, ast.Gt):
      return Operator.gt
    elif isinstance(op, ast.GtE):
      return Operator.ge
    else:
      raise Exception('Unexpected CmpOp (%s)'%(op.__class__))

  #Parses a function call (AST Call)
  def call(self, block, expr, var):
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
      args.append(self.expression(block, arg))
    #Find the module that contains the function
    if mod == '__main__':
      #Calls to intrinsic functions
      cls = Intrinsic
    elif mod == 'math':
      #Calls to math functions
      cls = Math
    else:
      #Other calls aren't supported
      raise Exception('Call not supported (module %s)'%(mod))
    #Build the call
    if func in cls.binary_functions and len(args) == 2:
      operation = BinaryOperation(args[0], func, args[1])
    elif func in cls.unary_functions and len(args) == 1:
      operation = UnaryOperation(func, args[0])
    #Emulated functions
    elif mod == 'math' and func == 'degrees' and len(args) == 1:
      r2d = self.add_literal(180.0 / math.pi, 'R2D')
      operation = BinaryOperation(args[0], '*', r2d)
    elif mod == 'math' and func == 'radians' and len(args) == 1:
      d2r = self.add_literal(math.pi / 180.0, 'D2R')
      operation = BinaryOperation(args[0], '*', d2r)
    elif mod == 'math' and func == 'log' and len(args) == 2:
      var1 = self.add_variable(None)
      op1 = UnaryOperation(func, args[0])
      asst1 = Assignment(var1, op1)
      block.add(asst1)
      var2 = self.add_variable(None)
      op2 = UnaryOperation(func, args[1])
      asst2 = Assignment(var2, op2)
      block.add(asst2)
      operation = BinaryOperation(var1, '/', var2)
    #Unknown function
    else:
      raise Exception('Call not supported or invalid arguments (%s.%s)'%(mod, func))
    #Make the assignment and return the result
    assignment = Assignment(var, operation)
    block.add(assignment)
    return var

  #Parses a named attribute (AST Attribute)
  def attribute(self, block, attr):
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

  #Parses a comparison (AST Compare)
  def compare(self, block, cmp, var=None):
    if len(cmp.comparators) != 1:
      raise Exception('Comparison requires exactly 1 right-side element')
    if len(cmp.ops) != 1:
      raise Exception('Comparison requires exactly 1 operator')
    #Parse the left and right expressions
    left = self.expression(block, cmp.left)
    right = self.expression(block, cmp.comparators[0])
    #Parse the operator
    op = self.cmpop(cmp.ops[0])
    #Create a temporary variable to store the result of the comparison
    if var is None:
      var = self.add_variable(None, is_mask=True)
    comparison = ComparisonOperation(left, op, right)
    assignment = Assignment(var, comparison)
    block.add(assignment)
    return var

  #Parses a boolean operation (AST BoolOp)
  def boolop(self, block, node, var=None):
    if len(node.values) != 2:
      raise Exception('BoolOp requires exactly 2 operands')
    if var == None:
      var = self.add_variable(None, is_mask=True)
    left = self.expression(block, node.values[0])
    right = self.expression(block, node.values[1])
    if isinstance(node.op, ast.And):
      op = Operator.bool_and
    elif isinstance(node.op, ast.Or):
      op = Operator.bool_or
    else:
      raise Exception('Unexpected BoolOp (%s)'%(node.op.__class__))
    operation = BinaryOperation(left, op, right)
    assignment = Assignment(var, operation)
    block.add(assignment)
    return var

  #Parses an array element (AST Subscript)
  def subscript(self, block, node):
    #Check types
    if not isinstance(node.value, ast.Name):
      raise Exception('Only variables can be subscripted')
    if not isinstance(node.slice, ast.Index):
      raise Exception('Slicing not supported')
    #Get the array and index
    array = self.expression(block, node.value)
    index = self.expression(block, node.slice.value)
    #Make sure the variable is an array
    if array.stride < 2:
      raise Exception('Variable can\'t be subscripted (%s)'%(array.name))
    #Check the access mode
    if isinstance(node.ctx, ast.Load):
      is_read=True
    elif isinstance(node.ctx, ast.Store):
      is_read=False
    else:
      raise Exception('Invalid array operation')
    #Access the array specified index
    var = self.add_variable(None)
    operation = ArrayAccess(array, index, is_read)
    assignment = Assignment(var, operation)
    return (var, assignment)

  #Parses an expression (AST Expr)
  def expression(self, block, expr, var=None):
    if isinstance(expr, ast.Num):
      var = self.add_literal(expr.n)
    elif isinstance(expr, ast.Name):
      var = self.kernel.get_variable(expr.id)
      if var is None:
        raise Exception('Undefined Variable (%s)'%(expr.id))
      if var.is_arg:
        var.is_input = True
    elif isinstance(expr, ast.BinOp):
      var = self.binop(block, expr, var)
    elif isinstance(expr, ast.UnaryOp):
      var = self.unaryop(block, expr)
    elif isinstance(expr, ast.Call):
      var = self.call(block, expr, var)
    elif isinstance(expr, ast.Attribute):
      var = self.attribute(block, expr)
    elif isinstance(expr, ast.Compare):
      var = self.compare(block, expr)
    elif isinstance(expr, ast.BoolOp):
      var = self.boolop(block, expr)
    elif isinstance(expr, ast.Subscript):
      (var, assignment) = self.subscript(block, expr)
      block.add(assignment)
    else:
      Parser._dump(expr, 'Unexpected Expression')
      raise Exception('Unexpected Expression (%s)'%(expr.__class__))
    return var

  #Generates a new block mask
  def get_mask(self, block, mask, op, var=None):
    if block.mask is None:
      return mask
    else:
      if var is None:
        var = self.add_variable(None, is_mask=True)
      operation = BinaryOperation(mask, op, block.mask)
      assignment = Assignment(var, operation, vector_only=True)
      block.add(assignment)
      return var

  #Parses a while loop (AST While)
  def while_(self, block, src):
    #Mark the start and stop indices for the while condition so it can be checked later
    start_index = len(block.code)
    #Parse the condition
    cond = self.expression(block, src.test)
    #Generate the mask
    mask = self.get_mask(block, cond, Operator.bit_and)
    stop_index = len(block.code)
    loop = WhileLoop(mask)
    #Recursively parse the body
    for stmt in src.body:
      self.statement(loop.block, stmt)
    #Duplicate the condition checking code
    self.add_comment(loop.block, src)
    loop.block.code += block.code[start_index:stop_index]
    #Nest the loop in the current block
    block.add(loop)

  #Parses an if(-else) statement (AST If)
  def if_(self, block, src):
    #Parse the condition
    cond = self.expression(block, src.test)
    #Generate the masks
    if_mask = self.get_mask(block, cond, Operator.bit_and)
    if len(src.orelse) != 0:
      else_mask = self.get_mask(block, cond, Operator.bit_andnot)
    else:
      else_mask = None
    ifelse = IfElse(if_mask, else_mask)
    #Recursively parse the body (and the else body if there is one)
    for stmt in src.body:
      self.statement(ifelse.if_block, stmt)
    for stmt in src.orelse:
      self.statement(ifelse.else_block, stmt)
    #Nest the block(s) in the current block
    block.add(ifelse)

  #Parses a single assignment
  def assign_single(self, block, src, dst, multi=False, src_variable=None):
    #Parse the expression and get the intermediate variable
    if src_variable is None:
      #Generates an intermediate storage variable
      expr = self.expression(block, src, None)
    else:
      #Reuses an existing variable
      expr = src_variable
    #Make or get the destination variable
    asst = None
    if isinstance(dst, ast.Name):
      var = self.add_variable(dst.id, is_mask=(expr.is_mask))
    elif isinstance(dst, ast.Subscript):
      (var, asst) = self.subscript(block, dst)
    else:
      raise Exception('Unexpected assignment destination (%s)'%(dst.__class__))
    #Sanity checks
    if var.is_uniform:
      raise Exception('Can\'t modify a uniform variable')
    if (var.stride == 1) ^ (expr.stride == 1):
      raise Exception('Can\'t assign scalar to array (or vice versa)')
    #Set the output flag if the variable is a scalar kernel argument
    if var.is_arg and var.stride == 1:
      var.is_output = True
    #Don't generate a self assignment
    if var != expr:
      #Create a temporary variable if this is a multi-assignment
      if multi and not expr.is_temp:
        temp = self.add_variable(None)
        temp.stride = expr.stride
        assignment = Assignment(temp, expr)
        block.add(assignment)
        expr = temp
      #The final assignment will be added to the kernel later
      result = [Assignment(var, expr, vector_only=True, mask=block.mask)]
      if asst is not None:
        result.append(asst)
      return result
    else:
      return None

  #Parses (possibly multiple) assignments (AST Assign)
  def assign(self, block, stmt):
    #Evaluate the assignment(s)
    value = stmt.value
    value_variable = None
    for i in range(len(stmt.targets)):
      target = stmt.targets[i]
      if isinstance(target, ast.Tuple):
        #Save intermediate results
        results = []
        #Evaluate individual assignments
        for (t, v) in zip(target.elts, stmt.value.elts):
          results.append(self.assign_single(block, v, t, multi=True))
        #Execute final assignments after intermediate calculations
        for result in results:
          block.add(result)
      else:
        result = self.assign_single(block, value, target, src_variable=value_variable)
        if result is not None:
          block.add(result)
          value_variable = result[-1].expr

  #Parses an augmenting assignment (AST AugAssign)
  def augassign(self, block, stmt):
    #Evaluate the assignment(s)
    src = ast.BinOp(stmt.target, stmt.op, stmt.value)
    dst = stmt.target
    result = self.assign_single(block, src, dst)
    if result is not None:
      block.add(result)

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
  def return_(self, block, ret):
    if block != self.kernel.block:
      raise Exception('Can\'t return from nested code block')
    if ret.value is None:
      raise Exception('Bad return type (%s)'%('must return something'))
    elif isinstance(ret.value, ast.Tuple):
      for elem in ret.value.elts:
        self.return_single(elem)
    else:
      self.return_single(ret.value)

  #Parses the docstring of a function
  def docstring_(self, block, stmt):
    if block != self.kernel.block:
      raise Exception('Can\'t define docstring in nested code block')
    if self.docstring is not None:
      raise Exception('Docstring already defined')
    if not isinstance(stmt.value, ast.Str):
      raise Exception('Bad docstring type (%s)'%(stmt.value.__class__))
    self.docstring = '\\n'.join(line.strip() for line in stmt.value.s.strip().split('\n'))
    self.kernel.set_docstring(self.docstring)

  #Parses statements (AST Stmt)
  def statement(self, block, stmt):
    #Add a comment
    self.add_comment(block, stmt)
    #Parse the statement
    try:
      if isinstance(stmt, ast.Assign):
        self.assign(block, stmt)
      elif isinstance(stmt, ast.Return):
        self.return_(block, stmt)
      elif isinstance(stmt, ast.Expr):
        self.docstring_(block, stmt)
      elif isinstance(stmt, ast.If):
        self.if_(block, stmt)
      elif isinstance(stmt, ast.While):
        self.while_(block, stmt)
      elif isinstance(stmt, ast.AugAssign):
        self.augassign(block, stmt)
      else:
        Parser._dump(stmt, 'Unexpected Statement')
        raise Exception('Unexpected Statement (%s)'%(stmt.__class__))
    except:
      line = stmt.lineno
      src = self.source.split('\n')[line - 1].strip()
      print('Line %d: %s'%(line, src))
      raise

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
    #Strip leading whitespace (e.g. a static method inside some class)
    source_lines = source_code.split('\n')
    leading_spaces = len(source_lines[0]) - len(source_lines[0].lstrip())
    if leading_spaces > 0:
      source_code = '\n'.join([line[leading_spaces:] for line in source_lines])

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
      if len(node.decorator_list) > 0:
        raise Exception('Decorators not supported')

      ##Get the function name
      #print("Found '%s' on line %d!"%(kernel_name, node.lineno))

      #Make a parser for this kernel
      parser = Parser(kernel_name, source_code)

      #Get the function's arguments
      for arg in node.args.args:
        name = arg.arg
        is_uniform = False
        stride = 1
        if arg.annotation is not None:
          ann = arg.annotation
          if isinstance(ann, ast.Str):
            label = ann.s
            if label == 'uniform':
              is_uniform = True
            else:
              raise Exception('Unsupported annotation (%s)'%(str))
          elif isinstance(ann, ast.Num):
            stride = ann.n
            if stride <= 0:
              raise Exception('Stride must be positive')
          else:
            raise Exception('Unsupported annotation (%s)'%(ann.__class__))
        parser.add_argument(name, is_uniform, stride)

      #The body!
      for stmt in node.body:
        parser.statement(parser.kernel.block, stmt)

      #Make sure there is at least one valid kernel argument
      if len(parser.kernel.get_arguments(uniform=False, array=False)) == 0:
        raise Exception('Kernel must take at least one non-uniform, non-array argument')

      #The source code has been parsed, return the abstract kernel
      return parser.kernel

    #The kernel wasn't found
    raise Exception('Kernel function not found (%s)'%(kernel_name))
