#Supported architectures
class Architecture:
  #Plain c++ code
  generic = {'level': 100, 'name': 'Generic', 'flag': ''        }
  #c++ with Intel SIMD intrinsics
  sse     = {'level': 200, 'name': 'SSE'    , 'flag': '-msse'   }
  sse2    = {'level': 201, 'name': 'SSE2'   , 'flag': '-msse2'  }
  sse3    = {'level': 202, 'name': 'SSE3'   , 'flag': '-msse3'  }
  ssse3   = {'level': 203, 'name': 'SSSE3'  , 'flag': '-mssse3' }
  sse4_1  = {'level': 204, 'name': 'SSE4.1' , 'flag': '-msse4.1'}
  sse4_2  = {'level': 205, 'name': 'SSE4.2' , 'flag': '-msse4.2'}
  avx     = {'level': 206, 'name': 'AVX'    , 'flag': '-mavx'   }
  avx2    = {'level': 207, 'name': 'AVX2'   , 'flag': '-mavx2'  }
  #c++ with NVIDIA CUDA
  cuda    = {'level': 300, 'name': 'CUDA'   , 'flag': ''        }

  #Utility functions
  def is_generic(arch):
    return arch['level'] // 100 == 1
  def is_intel(arch):
    return arch['level'] // 100 == 2
  def is_nvidia(arch):
    return arch['level'] // 100 == 3

#Available language bindings
class Binding:
  all    = 0
  cpp    = 1
  python = 2
  java   = 3

#Indent amount
def get_indent(level):
  return ' ' * (4 * level)

#Source code formatter
class Formatter:
  def __init__(self):
    self.level = 0
    self.code = ''
  def section(self, title):
    width = 78
    left = (width - len(title)) // 2
    right = width - len(title) - left
    self.append('/' + ('*' * width) + '*')
    self.append('*' + (' ' * left) + title + (' ' * right) + '*')
    self.append('*' + ('*' * width) + '/')
  def __iadd__(self, other):
    self.append(other)
    return self
  def append(self, code, end='\n'):
    self.code += get_indent(self.level) + code + end
  def indent(self):
    self.level += 1
  def unindent(self):
    self.level -= 1
    if self.level < 0:
      raise Exception('Negative indent')
  def get_code(self):
    if self.level != 0:
      raise Exception('Still indented')
    return self.code
