#Supported architectures
class Architecture:
  #Plain C++ code
  generic = {'level': 100, 'name': 'Generic', 'size': 1, 'flag': ''        }
  #C++ with Intel SIMD intrinsics 
  #sse     = {'level': 200, 'name': 'SSE'    , 'size': 4, 'flag': '-msse'   }
  #sse2    = {'level': 201, 'name': 'SSE2'   , 'size': 4, 'flag': '-msse2'  }
  #sse3    = {'level': 202, 'name': 'SSE3'   , 'size': 4, 'flag': '-msse3'  }
  #ssse3   = {'level': 203, 'name': 'SSSE3'  , 'size': 4, 'flag': '-mssse3' }
  #sse4_1  = {'level': 204, 'name': 'SSE4.1' , 'size': 4, 'flag': '-msse4.1'}
  sse4_2  = {'level': 205, 'name': 'SSE4.2' , 'size': 4, 'flag': '-msse4.2'}
  sse4    = sse4_2
  #avx     = {'level': 206, 'name': 'AVX'    , 'size': 8, 'flag': '-mavx'   }
  avx2    = {'level': 207, 'name': 'AVX2'   , 'size': 8, 'flag': '-mavx2'  }
  #C++ with NVIDIA CUDA
  #cuda    = {'level': 300, 'name': 'CUDA'   , 'size': 0, 'flag': ''        }

  #Utility functions
  def is_generic(arch):
    return (arch['level'] // 100) == 1
  def is_intel(arch):
    return (arch['level'] // 100) == 2
  #def is_nvidia(arch):
  #  return (arch['level'] // 100) == 3

#Supported data types
class DataType:
  float  = 'float'
  uint32 = 'unsigned int'

  #Utility functions
  def is_floating(type):
    return type in (DataType.float,)
  def is_integral(type):
    return type in (DataType.uint32,)

#Available language bindings
class Binding:
  all    = '*all*'
  cpp    = 'cpp'
  python = 'python'
  java   = 'java'

#Compile time options
class Options:
  def __init__(self, arch, type, bindings=(Binding.all,), threads=None, java_package='vecpy'):
    if arch is None or type is None or bindings is None or len(bindings) == 0:
      raise Exception('Invalid options')
    #Target architecture
    self.arch = arch
    #Kernel data type
    self.type = type
    #Language API bindings
    self.bindings = bindings
    #Number of threads to spawn
    self.threads = threads
    #Java package name
    self.java_package = java_package
  def show(self):
    print('=' * 40)
    print('VecPy options')
    print('-' * 40)
    print('Architecture:      ' + self.arch['name'])
    print('Data Type:         ' + self.type)
    print('Language Bindings: ' + ','.join(self.bindings))
    print('Threads:           ' + str(self.threads))
    if Binding.all in self.bindings or Binding.java in self.bindings:
      print('Java Package:      ' + str(self.java_package))
    print('=' * 40)

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
