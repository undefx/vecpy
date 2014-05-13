import array
import math
import time
from vecpy.parser import Parser
from vecpy.compiler import Compiler

#Invokes the VecPy stack
def vectorize(func, options):
  Compiler.compile(Parser.parse(func), options)

#Returns an aligned array (necessary for SSE/AVX)
def get_array(type, length, align=32, value=0):
  #Check arguments
  if type not in ('f', 'I'):
    raise Exception('Invalid type')
  if length <= 0:
    raise Exception('Length must be positive')
  if align < 16 or 2 ** int(math.log2(align)) != align:
    raise Exception('Alignment must be a power of 2, at least 16')
  #4 bytes per element
  size = 4
  num_elements = align // size
  padding = num_elements - 1
  #Allocate the (probably unaligned) buffer
  buffer = array.array(type, [value for i in range(length + padding)])
  #Find the offset needed to reach the boundary
  base_address = buffer.buffer_info()[0]
  offset = ((align - (base_address % align)) % align) // size
  #Return the buffer starting at an aligned offset
  return memoryview(buffer)[offset:length + offset]

#Returns aligned arrays
def get_arrays(num, type, length, align=32, value=0):
  return [get_array(type, length, align, value) for i in range(num)]

#Calculates kernel runtime and speedup
def get_speedup(kernel1, kernel2):
  #Execute both kernels
  time1 = time.perf_counter()
  kernel1()
  time2 = time.perf_counter()
  kernel2()
  time3 = time.perf_counter()
  #Return runtime and speedup
  delta1 = time2 - time1
  delta2 = time3 - time2
  return (delta1, delta2, delta1 / delta2)
