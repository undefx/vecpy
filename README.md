VecPy
=====

A Python module compiler that leverages SIMD instructions on modern processors.


Proof of Concept
=====
Define a kernel and tell VecPy to compile it.

    #Imports
    from parser import Parser
    from compiler import Compiler
    from compiler_constants import Architecture
    
    #The kernel
    def myKernel(a, x, b, y):
      """A generic kernel function."""
      plus = a + x
      minus = a - x
      b = (plus * minus) + 1
      y = (plus / minus) - (a ** 3.5)
      return (b, y)
    
    #Sanity check
    print('Expected result: ', myKernel(1, 2, 0, 0))
    
    #VecPy will turn the kernel into a native module
    Compiler.compile(Parser.parse(myKernel), Architecture.avx2)

Import the native module which contains the kernel logic and execute it.

    #Imports
    import array
    import VecPy_myKernel
    
    #Show VecPy generated documentation
    print(VecPy_myKernel.__doc__)
    print(VecPy_myKernel.myKernel.__doc__)
    
    #Generate a lot of data
    n = 16
    a = array.array('f', [1 for i in range(n)])
    x = array.array('f', [2 for i in range(n)])
    b = array.array('f', [0 for i in range(n)])
    y = array.array('f', [0 for i in range(n)])
    
    #Call the native kernel and show the results
    print(VecPy_myKernel.myKernel(a, x, b, y))
    print(a, x, b, y, sep='\n')
