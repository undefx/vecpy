"""
The Compiler uses the Parser and the Kernel to translate a pure Python function
into a native library. This library can be invoked though several language bindings,
in particular as a native Python module.
"""


import subprocess
from kernel import *
from compiler_constants import *
from compiler_generic import Compiler_Generic
from compiler_intel import Compiler_Intel

class Compiler:

  #Utility functions: output file names
  def get_python_file(k):
    return 'vecpy_%s_python.h'%(k.name)

  def get_java_file(k):
    return 'vecpy_%s_java.h'%(k.name)

  def get_cpp_file(k):
    return 'vecpy_%s_cpp.h'%(k.name)

  def get_kernel_file(k):
    return 'vecpy_%s_kernel.h'%(k.name)

  def get_core_file(k):
    return 'vecpy_%s_core.cpp'%(k.name)

  #Generates the core file
  def compile_core(k, include_files, num_cores):
    src = Formatter()
    src.section('VecPy generated core')
    #Includes
    src += '//Includes'
    src += '#include <pthread.h>'
    src += '#include <stdio.h>'
    src += '#include "%s"'%(Compiler.get_kernel_file(k))
    src += ''
    #Utility functions
    src += '//Utility functions'
    src += 'static void* threadStart(void* v) {'
    src.indent()
    src += '%s_generic((KernelArgs*)v);'%(k.name)
    src += 'return NULL;'
    src.unindent()
    src += '}'
    src += 'static bool isAligned(void* data) {'
    src.indent()
    src += 'return reinterpret_cast<unsigned long>(data) %% %dUL == 0UL;'%(16)
    src.unindent()
    src += '}'
    src += 'static bool checkArgs(KernelArgs* args) {'
    src.indent()
    src += 'if(args->N %% %d != 0) {'%(4)
    src.indent()
    src += 'printf("Input size not a multiple of %d (%%d)\\n", args->N);'%(4)
    src += 'return false;'
    src.unindent()
    src += '}'
    for arg in k.get_arguments():
      src += 'if(!isAligned(args->%s)) {'%(arg.name)
      src.indent()
      src += 'printf("Array not aligned (%s)\\n");'%(arg.name)
      src += 'return false;'
      src.unindent()
      src += '}'
    src += 'return true;'
    src.unindent()
    src += '}'
    src += ''
    #Unified core for all programming interfaces
    src += '//Unified core function'
    src += 'static bool run(KernelArgs* args) {'
    src.indent()
    src += 'if(!checkArgs(args)) {'
    src.indent()
    src += 'printf("Arguments are invalid\\n");'
    src += 'return false;'
    src.unindent()
    src += '}'
    src += 'const unsigned int numThreads = %d;'%(num_cores)
    src += 'unsigned int num = args->N / numThreads;'
    src += 'unsigned int offset = 0;'
    src += '//Execute on multiple threads'
    src += 'if(num > 0) {'
    src.indent()
    src += 'pthread_t* threads = new pthread_t[numThreads];'
    src += 'KernelArgs* threadArgs = new KernelArgs[numThreads];'
    src += 'for(int t = 0; t < numThreads; t++) {'
    src.indent()
    for arg in k.get_arguments():
      src += 'threadArgs[t].%s = &args->%s[offset];'%(arg.name, arg.name)
    src += 'threadArgs[t].N = num;'
    src += 'offset += num;'
    src += 'pthread_create(&threads[t], NULL, threadStart, (void*)&threadArgs[t]);'
    src.unindent()
    src += '}'
    src += 'for(int t = 0; t < numThreads; t++) {'
    src.indent()
    src += ' pthread_join(threads[t], NULL); '
    src.unindent()
    src += '}'
    src += 'delete [] threads;'
    src += 'delete [] threadArgs;'
    src.unindent()
    src += '}'
    src += '//Handle any remaining elements'
    src += 'if(offset < args->N) {'
    src.indent()
    src += 'KernelArgs lastArgs;'
    for arg in k.get_arguments():
      src += 'lastArgs.%s = &args->%s[offset];'%(arg.name, arg.name)
    src += 'lastArgs.N = args->N - offset;'
    src += 'simple_generic(&lastArgs);'
    src.unindent()
    src += '}'
    src += 'return true;'
    src.unindent()
    src += '}'
    src += ''
    #Additional includes for each programming language
    src += '//Additional includes for each programming language'
    for file in include_files:
      src += '#include "%s"'%(file)
    src += ''
    #Save code to file
    file_name = Compiler.get_core_file(k)
    with open(file_name, 'w') as file:
      file.write(src.get_code())
    #print('Saved to file: %s'%(file_name))

  #Generates the C++ API
  def compile_cpp(k):
    src = Formatter()
    src.section('VecPy generated entry point: C++')
    #Build the argument string
    arg_str = ''
    for arg in k.get_arguments():
      arg_str += '%s* %s, '%(k.get_type(), arg.name)
    #Wrapper for the core function
    src += '//Wrapper for the core function'
    src += 'extern "C" bool %s(%sint N) {'%(k.name, arg_str)
    src.indent()
    src += 'KernelArgs args;'
    for arg in k.get_arguments():
      src += 'args.%s = %s;'%(arg.name, arg.name)
    src += 'args.N = N;'
    src += 'return run(&args);'
    src.unindent()
    src += '}'
    src += ''
    #Save code to file
    file_name = Compiler.get_cpp_file(k)
    with open(file_name, 'w') as file:
      file.write(src.get_code())
    #print('Saved to file: %s'%(file_name))

  #Generates the Python API
  def compile_python(k):
    type = k.get_type()
    module_name = 'VecPy_' + k.name
    args = k.get_arguments()
    src = Formatter()
    src.section('VecPy generated entry point: Python')
    #Includes
    src += '//Includes'
    src += '#include <Python.h>'
    src += ''
    #Wrapper for the core function
    src += '//Wrapper for the core function'
    src += 'static PyObject* %s_run(PyObject* self, PyObject* pyArgs) {'%(k.name)
    src.indent()
    src += '//Handles to Python objects and buffers'
    obj_str = ', '.join('*obj_%s'%(arg.name) for arg in args)
    buf_str = ', '.join('buf_%s'%(arg.name) for arg in args)
    src += 'PyObject %s;'%(obj_str)
    src += 'Py_buffer %s;'%(buf_str)
    src += '//Get Python objects'
    obj_str = ', '.join('&obj_%s'%(arg.name) for arg in args)
    src += 'if(!PyArg_ParseTuple(pyArgs, "%s", %s)) {'%('O' * len(args), obj_str)
    src.indent()
    src += 'printf("Error retrieving Python objects\\n");'
    src += 'return NULL;'
    src.unindent()
    src += '}'
    src += '//Get Python buffers from Python objects'
    for arg in args:
      src += 'if(PyObject_GetBuffer(obj_%s, &buf_%s, %s) != 0) {'%(arg.name, arg.name, 'PyBUF_WRITABLE' if arg.output else '0')
      src.indent()
      src += 'printf("Error retrieving Python buffer (%s)\\n");'%(arg.name)
      src += 'return NULL;'
      src.unindent()
      src += '}'
    src += '//Number of elements to process'
    src += 'int N = buf_%s.len / sizeof(%s);'%(args[0].name, type)
    src += '//Check length for all buffers'
    for arg in args:
      src += 'if(buf_%s.len / sizeof(%s) != N) {'%(arg.name, type)
      src.indent()
      src += 'printf("Python buffer sizes don\'t match (%s)\\n");'%(arg.name)
      src += 'return NULL;'
      src.unindent()
      src += '}'
    src += '//Extract input arrays from buffers'
    src += 'KernelArgs args;'
    for arg in args:
      src += 'args.%s = (%s*)buf_%s.buf;'%(arg.name, type, arg.name)
    src += 'args.N = N;'
    src += '//Run the kernel'
    src += 'bool result = run(&args);'
    src += '//Release buffers'
    for arg in args:
      src += 'PyBuffer_Release(&buf_%s);'%(arg.name)
    src += '//Return the result'
    src += 'if(result) { Py_RETURN_TRUE; } else { printf("Kernel reported failure\\n"); Py_RETURN_FALSE; }'
    src.unindent()
    src += '}'
    src += ''
    #Module manifest
    src += '//Module manifest'
    src += 'static PyMethodDef module_methods[] = {'
    src.indent()
    src += '{'
    src.indent()
    src += '//Export name, visible within Python'
    src += '"%s",'%(k.name)
    src += '//Pointer to local implementation'
    src += '%s_run,'%(k.name)
    src += '//Accept normal (not keyword) arguments'
    src += 'METH_VARARGS,'
    src += '//Function documentation'
    src += '"%s"'%('\n'.join(k.docstring.splitlines()))
    src.unindent()
    src += '},{NULL, NULL, 0, NULL} //End of manifest entries'
    src.unindent()
    src += '};'
    src += ''
    #Module definition
    src += '//Module definition'
    src += 'static struct PyModuleDef module = {'
    src.indent()
    src += 'PyModuleDef_HEAD_INIT,'
    src += '//Module name'
    src += '"%s",'%(module_name)
    src += '//Module documentation'
    src += '"VecPy module for %s.",'%(k.name)
    src += '//Other module info'
    src += '-1, module_methods, NULL, NULL, NULL, NULL'
    src.unindent()
    src += '};'
    src += ''
    #Module initializer
    src += '//Module initializer'
    src += 'PyMODINIT_FUNC PyInit_%s() { return PyModule_Create(&module); }'%(module_name)
    src += ''
    #Save code to file
    file_name = Compiler.get_python_file(k)
    with open(file_name, 'w') as file:
      file.write(src.get_code())
    #print('Saved to file: %s'%(file_name))

  #Generates the Java API
  def compile_java(k):
    type = k.get_type()
    args = k.get_arguments()
    src = Formatter()
    src.section('VecPy generated entry point: Java')
    #Includes
    src += '//Includes'
    src += '#include <jni.h>'
    src += ''
    #Wrapper for the core function
    src += '//Wrapper for the core function'
    arg_str = ', '.join('jobject buf_%s'%(arg.name) for arg in args)
    src += 'extern "C" JNIEXPORT jboolean JNICALL Java_%s_%s(JNIEnv* env, jclass cls, %s) {'%('VecPy', k.name, arg_str)
    src.indent()
    buffer_type = 'FloatBuffer'
    src += '//Make sure the buffers are directly allocated'
    src += 'jclass %s = env->FindClass("java/nio/%s");'%(buffer_type, buffer_type)
    src += 'jmethodID isDirect = env->GetMethodID(%s, "isDirect", "()Z");'%(buffer_type)
    for arg in args:
      src += 'if(!env->CallBooleanMethod(buf_%s, isDirect)) {'%(arg.name)
      src.indent()
      src += 'printf("Buffer not direct (%s)\\n");'%(arg.name)
      src += 'return false;'
      src.unindent()
      src += '}'
    src += '//Number of elements to process'
    src += 'jlong N = env->GetDirectBufferCapacity(buf_%s);'%(args[0].name)
    src += 'if(N == -1) {'
    src.indent()
    src += 'printf("JVM doesn\'t support direct buffers\\n");'
    src += 'return false;'
    src.unindent()
    src += '}'
    src += '//Check length for all buffers'
    for arg in args:
      src += 'if(env->GetDirectBufferCapacity(buf_%s) != N) { '%(arg.name)
      src.indent()
      src += 'printf("Java buffer sizes don\'t match (%s)\\n");'%(arg.name)
      src += 'return false;'
      src.unindent()
      src += '}'
    src += '//Extract input arrays from buffers'
    src += 'KernelArgs args;'
    for arg in args:
      src += 'args.%s = (%s*)env->GetDirectBufferAddress(buf_%s);'%(arg.name, type, arg.name)
    src += 'args.N = N;'
    for arg in args:
      src += 'if(args.%s == NULL) {'%(arg.name)
      src.indent()
      src += 'printf("Error retrieving Java buffer (%s)\\n");'%(arg.name)
      src += 'return false;'
      src.unindent()
      src += '}'
    src += '//Run the kernel'
    src += 'return run(&args);'
    src.unindent()
    src += '}'
    src += ''
    #Save code to file
    file_name = Compiler.get_java_file(k)
    with open(file_name, 'w') as file:
      file.write(src.get_code())
    #print('Saved to file: %s'%(file_name))

  #Generates the kernel
  def compile_kernel(k, arch):
    src = Formatter()
    src.section('VecPy generated kernel: %s'%(k.name))
    #The KernelArgs struct
    src += '//Kernel arguments'
    src += 'struct KernelArgs {'
    src.indent()
    for arg in k.get_arguments():
      src += '%s* %s;'%(k.get_type(), arg.name)
    src += 'int N;'
    src.unindent()
    src += '};'
    src += ''
    #Generate an architecture-specific kernel
    src += Compiler_Generic.compile_kernel(k, arch)
    if Architecture.is_intel(arch):
      src += Compiler_Intel.compile_kernel(k, arch)
    elif not Architecture.is_generic(arch):
      raise Exception('Target architecture not implemented (%s)'%(arch['name']))
    #Save code to file
    file_name = Compiler.get_kernel_file(k)
    with open(file_name, 'w') as file:
      file.write(src.get_code())
    #print('Saved to file: %s'%(file_name))

  #Compiles the module
  def build(k, build_flags):
    src = Formatter()
    #Generate the build script
    src += 'NAME=VecPy_%s.so'%(k.name)
    src += 'rm -f $NAME'
    src += 'g++ -O3 -fPIC -shared %s -o $NAME %s'%(' '.join(build_flags), Compiler.get_core_file(k))
    src += 'nm $NAME | grep " T "'
    #Save code to file
    file_name = 'build.sh'
    with open(file_name, 'w') as file:
      file.write(src.get_code())
    #print('Saved to file: %s'%(file_name))
    #Run the build script
    subprocess.call(['chmod', '+x', file_name])
    subprocess.check_call(['./' + file_name], shell=True)

  #Generates all files and compiles the module
  def compile(k, arch, bindings=(Binding.all,), num_cores=None):
    #Sanity checks
    if arch is None:
      raise Exception('No architecture specified')
    if bindings is None or len(bindings) == 0:
      raise Exception('No language bindings specified')
    #Auto-detect number of cores
    if num_cores is None or num_cores < 1:
      try:
        import multiprocessing
        num_cores = multiprocessing.cpu_count()
      except(ImportError, NotImplementedError):
        num_cores = 1
      print('Detected %s core(s)'%(num_cores))
    #Generate the kernel
    Compiler.compile_kernel(k, arch)
    #Generate API for each language
    include_files = []
    build_flags = [arch['flag']]
    if Binding.all in bindings or Binding.cpp in bindings:
      Compiler.compile_cpp(k)
      include_files.append(Compiler.get_cpp_file(k))
    if Binding.all in bindings or Binding.python in bindings:
      Compiler.compile_python(k)
      include_files.append(Compiler.get_python_file(k))
      build_flags.append('-lpython3.3m')
      build_flags.append('-I/usr/include/python3.3m/')
    if Binding.all in bindings or Binding.java in bindings:
      Compiler.compile_java(k)
      include_files.append(Compiler.get_java_file(k))
      build_flags.append('-I/usr/java/latest/include/')
      build_flags.append('-I/usr/java/latest/include/linux/')
    #Generate the core
    Compiler.compile_core(k, include_files, num_cores)
    #Compile the module
    Compiler.build(k, build_flags)