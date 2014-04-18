VecPy
=====

VecPy builds native libraries from arbitrary kernel functions written in Python. Native libraries leverage multi-threading and SIMD instructions on modern x86 processors to execute the kernel as efficiently as possible. Multiple language bindings allow the vectorized kernel to be called from Python, C++, and Java - all from a single, shared library.


Hello, world!
=====
One of the primary design goals of VecPy is *simplicity*. In just a few lines of code, VecPy translates and compiles a Python function into an efficient, data-parallel native library. The generated library can then be loaded as a Python module, allowing the optimized function to be used as a drop-in replacement for the original Python function. The following program illustrates how simple it can be to use VecPy to significantly improve Python program performance.
```python
#Import VecPy and other modules
from parser import Parser
from compiler import Compiler
from compiler_constants import *
from array import array
from random import uniform

#Define the kernel
def shapes(radius, edge, vol_sphere, vol_icos):
  """Calculates sphere and an icosahedron volumes."""
  vol_sphere = (4/3 * math.pi) * (radius ** 3)
  vol_icos = (5/12) * (3 + math.sqrt(5)) * (edge ** 3)
  return (vol_sphere, vol_icos)

#Generate some data
n = 1000
def rand():
  return array('f', [uniform(0, 1) for i in range(n)])
radii, edges, spheres, icosahedrons = rand(), rand(), rand(), rand()

#Call VecPy to generate the a native module
krnl = Parser.parse(shapes)
opts = Options(Architecture.sse4, DataType.float)
Compiler.compile(krnl, opts)

#Import the newly-minted module and execute the data-parallel kernel
import VecPy_shapes
VecPy_shapes.shapes(radii, edges, spheres, icosahedrons)

#Use the results!
print(spheres, icosahedrons)
```

Features and Functionality
=====
Other design goals of VecPy include *utility*, *flexibility*, and *efficiency*.

VecPy aims to implement a sufficiently large feature set to be useful for meaningful, real-world applications. The following Python operators, functions, and constants are currently supported:

  - **Operators**
    - Binary: +, -, \*, /, %, \*\*
    - Unary: +, -
  - **Functions**
    - global: abs, max, min, pow
    - math: acos, acosh, asin, asinh, atan, atan2, atanh, ceil, copysign, cos, cosh, erf, erfc, exp, expm1, fabs, floor, fmod, gamma, hypot, lgamma, log, log10, log1p, log2, pow, sin, sinh, sqrt, tan, tanh, trunc
  - **Constants**
    - math: e, pi


VecPy provides many options to allow for extensive customization. The following data types and language bindings are currently supported:

  - **Data Types**
    - 32-bit floats
    - 32-bit integers (experimental)
  - **Language Bindings**
    - C++
    - Python
    - Java

VecPy relies on multi-threading and SIMD execution to achieve the fastest possible performance. The following x86 architectures and operating systems are currently supported:

  - **Architectures**
    - Generic (no SIMD)
    - SSE4.2
  - **Operating Systems**
    - Linux

Requirements
=====
  - Python 3.x (to run VecPy)
  - Linux (to compile the native module)
  - Optional: Python 3.x headers if compiling as a Python module
  - Optional: JDK if compiling for use with Java via JNI
