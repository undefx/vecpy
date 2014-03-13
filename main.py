#Imports
from parser import *
from compiler import *
from compiler_constants import *
import array

#The kernel
def myKernel(a, x, b, y):
  plus = a + x
  minus = a - x
  b = (plus * minus) + 1
  y = (plus / minus) - (a ** 2.5)
  return (b, y)

#Entry point
k = Parser.parse(myKernel)
Compiler.compile(k, Architecture.avx)
print(myKernel(1, 2, 0, 0))