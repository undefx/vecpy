from kernel import *
from compiler_constants import *
from compiler_generic import Compiler_Generic
from compiler_intel import Compiler_Intel

class Compiler:
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

  def compile_core(k, include_files):
    indent = get_indent()
    src = ''
    #Includes
    src += '//Includes\n'
    src += '#include <pthread.h>\n'
    src += '#include <stdio.h>\n'
    src += '#include "%s"\n'%(Compiler.get_kernel_file(k))
    src += '\n'
    #Utility functions
    src += '//Utility functions\n';
    src += 'static void* threadStart(void* v) {'
    src += ' %s((KernelArgs*)v); return NULL; '%(k.name)
    src += '}\n'
    src += 'static bool isAligned(void* data) {'
    src += ' return reinterpret_cast<unsigned long>(data) %% %dUL == 0UL; '%(16)
    src += '}\n'
    src += 'static bool checkArgs(KernelArgs* args) {\n'
    src += '%sif(args->N %% 4 != 0) {'%(indent)
    src += ' printf("Input size not a multiple of %d (%%d)\\n", args->N); return false; '%(4)
    src += '}\n'
    for arg in k.get_arguments():
      src += '%sif(!isAligned(args->%s)) {'%(indent, arg.name)
      src += ' printf("Array not aligned (%s)\\n"); return false; '%(arg.name)
      src += '}\n'
    src += '%sreturn true;\n'%(indent)
    src += '}\n'
    src += '\n'
    #Unified core for all programming interfaces
    src += '//Unified core function\n'
    src += 'static bool run(KernelArgs* args) {\n'
    src += '%sif(!checkArgs(args)) {'%(indent)
    src += ' printf("Arguments are invalid\\n"); return false; }\n'
    src += '%sprintf("Arguments are valid\\n");\n'%(indent)
    src += '%sint numThreads = 2;\n'%(indent)
    src += '%sunsigned int offset = 0;\n'%(indent)
    src += '%spthread_t* threads = new pthread_t[numThreads];\n'%(indent)
    src += '%sKernelArgs* threadArgs = new KernelArgs[numThreads];\n'%(indent)
    src += '%sfor(int t = 0; t < numThreads; t++) {\n'%(indent)
    src += '%s%sunsigned int num = 4;\n'%(indent, indent)
    for arg in k.get_arguments():
      src += '%s%sthreadArgs[t].%s = &args->%s[offset];\n'%(indent, indent, arg.name, arg.name)
    src += '%s%sthreadArgs[t].N = num;\n'%(indent, indent)
    src += '%s%soffset += num;\n'%(indent, indent)
    src += '%s%spthread_create(&threads[t], NULL, threadStart, (void*)&threadArgs[t]);\n'%(indent, indent)
    src += '%s}\n'%(indent)
    src += '%sfor(int t = 0; t < numThreads; t++) {'%(indent)
    src += ' pthread_join(threads[t], NULL); '
    src += '}\n'
    src += '%sdelete [] threads;\n'%(indent)
    src += '%sdelete [] threadArgs;\n'%(indent)
    src += '%sreturn true;\n'%(indent)
    src += '}\n'
    src += '\n'
    #Additional includes for each programming language
    src += '//Additional includes for each programming language\n'
    for file in include_files:
      src += '#include "%s"\n'%(file)
    src += '\n';
    #Print code to stdout
    #print('/*%s*/\n%s/*%s*/\n'%('*' * 80, src, '*' * 80))
    #Save code to file
    file_name = Compiler.get_core_file(k)
    with open(file_name, 'w') as file:
      file.write(src)
    #print('Saved to file: %s'%(file_name))

  def compile_cpp(k):
    indent = get_indent()
    src = ''
    src += '//c++ entry point\n'
    #Build the argument string
    arg_str = ''
    for arg in k.get_arguments():
      arg_str += '%s* %s, '%(k.get_type(), arg.name)
    #Wrapper for the core function
    src += '//Wrapper for the core function\n'
    src += 'extern "C" bool %s(%sint N) {\n'%(k.name, arg_str)
    src += '%sKernelArgs args;\n'%(indent)
    for arg in k.get_arguments():
      src += '%sargs.%s = %s;\n'%(indent, arg.name, arg.name)
    src += '%sargs.N = N;\n'%(indent)
    src += '%sreturn run(&args);\n'%(indent)
    src += '}\n'
    src += '\n';
    #Print code to stdout
    #print('/*%s*/\n%s/*%s*/\n'%('*' * 80, src, '*' * 80))
    #Save code to file
    file_name = Compiler.get_cpp_file(k)
    with open(file_name, 'w') as file:
      file.write(src)
    #print('Saved to file: %s'%(file_name))

  def compile_python(k):
    indent = get_indent()
    src = ''
    type = k.get_type()
    module_name = 'VecPy_' + k.name
    args = k.get_arguments()
    src += '//Python entry point\n'
    #Includes
    src += '//Includes\n'
    src += '#include <Python.h>\n'
    src += '\n';
    #Wrapper for the core function
    src += '//Wrapper for the core function\n'
    src += 'static PyObject* %s_run(PyObject* self, PyObject* pyArgs) {\n'%(k.name)
    src += '%s//Handles to Python objects and buffers\n'%(indent)
    obj_str = ', '.join('*obj_%s'%(arg.name) for arg in args)
    buf_str = ', '.join('buf_%s'%(arg.name) for arg in args)
    src += '%sPyObject %s;\n'%(indent, obj_str)
    src += '%sPy_buffer %s;\n'%(indent, buf_str)
    src += '%s//Get Python objects\n'%(indent)
    obj_str = ', '.join('&obj_%s'%(arg.name) for arg in args)
    src += '%sif(!PyArg_ParseTuple(pyArgs, "%s", %s)) {'%(indent, 'O' * len(args), obj_str)
    src += ' printf("Error retrieving Python objects\\n"); return NULL; '
    src += '}\n'
    src += '%s//Get Python buffers from Python objects\n'%(indent)
    for arg in args:
      src += '%sif(PyObject_GetBuffer(obj_%s, &buf_%s, %s) != 0) {'%(indent, arg.name, arg.name, 'PyBUF_WRITABLE' if arg.output else '0')
      src += ' printf("Error retrieving Python buffers\\n"); return NULL; '
      src += '}\n'
    src += '%s//Number of elements to process\n'%(indent)
    src += '%sint N = buf_%s.len / sizeof(%s);\n'%(indent, args[0].name, type)
    src += '%s//Check length for all buffers\n'%(indent)
    for arg in args:
      src += '%sif(buf_%s.len / sizeof(%s) != N) {'%(indent, arg.name, type)
      src += ' printf("Python buffer sizes don\'t match\\n"); return NULL; '
      src += '}\n'
    src += '%s//Extract input arrays from buffers\n'%(indent)
    src += '%sKernelArgs args;\n'%(indent)
    for arg in args:
      src += '%sargs.%s = (%s*)buf_%s.buf;\n'%(indent, arg.name, type, arg.name)
    src += '%sargs.N = N;\n'%(indent)
    src += '%s//Run the kernel\n'%(indent)
    src += '%sbool result = run(&args);\n'%(indent)
    src += '%s//Release buffers\n'%(indent)
    for arg in args:
      src += '%sPyBuffer_Release(&buf_%s);\n'%(indent, arg.name)
    src += '%s//Return the result\n'%(indent)
    src += '%sif(result) { Py_RETURN_TRUE; } else { printf("Kernel reported failure\\n"); Py_RETURN_FALSE; }\n'%(indent)
    src += '}\n'
    src += '\n'
    #Module manifest
    src += '//Module manifest\n'
    src += 'static PyMethodDef module_methods[] = {\n'
    src += '%s{\n'%(indent)
    src += '%s%s//Export name, visible within Python\n'%(indent, indent)
    src += '%s%s"%s",\n'%(indent, indent, k.name)
    src += '%s%s//Pointer to local implementation\n'%(indent, indent)
    src += '%s%s%s_run,\n'%(indent, indent, k.name)
    src += '%s%s//Accept normal (not keyword) arguments\n'%(indent, indent)
    src += '%s%sMETH_VARARGS,\n'%(indent, indent)
    src += '%s%s//Function documentation\n'%(indent, indent)
    src += '%s%s"%s"\n'%(indent, indent, '\\n'.join(k.docstring.splitlines()))
    src += '%s},{NULL, NULL, 0, NULL} //End of manifest entries\n'%(indent)
    src += '};\n'
    src += '\n'
    #Module definition
    src += '//Module definition\n'
    src += 'static struct PyModuleDef module = {\n'
    src += '%sPyModuleDef_HEAD_INIT,\n'%(indent)
    src += '%s//Module name\n'%(indent)
    src += '%s"%s",\n'%(indent, module_name)
    src += '%s//Module documentation\n'%(indent)
    src += '%s"VecPy module for %s.",\n'%(indent, k.name)
    src += '%s//Other module info\n'%(indent)
    src += '%s-1, module_methods, NULL, NULL, NULL, NULL\n'%(indent)
    src += '};\n'
    src += '\n'
    #Module initializer
    src += '//Module initializer\n'
    src += 'PyMODINIT_FUNC PyInit_%s() { return PyModule_Create(&module); }\n'%(module_name)
    src += '\n'
    #Print code to stdout
    #print('/*%s*/\n%s/*%s*/\n'%('*' * 80, src, '*' * 80))
    #Save code to file
    file_name = Compiler.get_python_file(k)
    with open(file_name, 'w') as file:
      file.write(src)
    #print('Saved to file: %s'%(file_name))

  def compile_java(k):
    indent = get_indent()
    src = ''
    type = k.get_type()
    args = k.get_arguments()
    src += '//Java entry point\n'
    #Includes
    src += '//Includes\n'
    src += '#include <jni.h>\n'
    src += '\n';
    #Wrapper for the core function
    src += '//Wrapper for the core function\n'
    arg_str = ', '.join('jobject buf_%s'%(arg.name) for arg in args)
    src += 'extern "C" JNIEXPORT jboolean JNICALL Java_%s_%s(JNIEnv* env, jclass cls, %s) {\n'%('VecPy', k.name, arg_str)
    buffer_type = 'FloatBuffer'
    src += '%s//Make sure the buffers are directly allocated\n'%(indent)
    src += '%sjclass %s = env->FindClass("java/nio/%s");\n'%(indent, buffer_type, buffer_type)
    src += '%sjmethodID isDirect = env->GetMethodID(%s, "isDirect", "()Z");\n'%(indent, buffer_type)
    for arg in args:
      src += '%sif(!env->CallBooleanMethod(buf_%s, isDirect)) {'%(indent, arg.name)
      src += ' printf("Buffer not direct (%s)\\n"); return false; '%(arg.name)
      src += '}\n'
    src += '%s//Number of elements to process\n'%(indent)
    src += '%sjlong N = env->GetDirectBufferCapacity(buf_%s);\n'%(indent, args[0].name)
    src += '%sif(N == -1) { printf("JVM doesn\'t support direct buffers\\n"); return false; }\n'%(indent)
    src += '%s//Check length for all buffers\n'%(indent)
    for arg in args:
      src += '%sif(env->GetDirectBufferCapacity(buf_%s) != N) { '%(indent, arg.name)
      src += 'printf("Java buffer sizes don\'t match\\n"); return false; '
      src += '}\n'
    src += '%s//Extract input arrays from buffers\n'%(indent)
    src += '%sKernelArgs args;\n'%(indent)
    for arg in args:
      src += '%sargs.%s = (%s*)env->GetDirectBufferAddress(buf_%s);\n'%(indent, arg.name, type, arg.name)
    src += '%sargs.N = N;\n'%(indent)
    for arg in args:
      src += '%sif(args.%s == NULL) { printf("Error retrieving Java buffers\\n"); return false; }\n'%(indent, arg.name)
    src += '%s//Run the kernel\n'%(indent)
    src += '%sreturn run(&args);\n'%(indent)
    src += '}\n'
    src += '\n'
    #Print code to stdout
    #print('/*%s*/\n%s/*%s*/\n'%('*' * 80, src, '*' * 80))
    #Save code to file
    file_name = Compiler.get_java_file(k)
    with open(file_name, 'w') as file:
      file.write(src)
    #print('Saved to file: %s'%(file_name))

  def compile_kernel(k, arch):
    #Generate an architecture-specific kernel
    if Architecture.is_generic(arch):
      src = Compiler_Generic.compile_kernel(k, arch)
    elif Architecture.is_intel(arch):
      src = Compiler_Intel.compile_kernel(k, arch)
    else:
      raise Exception('Target architecture not implemented (%s)'%(arch['name']))
    #Print code to stdout
    print('/*%s*/\n%s/*%s*/\n'%('*' * 80, src, '*' * 80))
    #Save code to file
    file_name = Compiler.get_kernel_file(k)
    with open(file_name, 'w') as file:
      file.write(src)
    print('Saved to file: %s'%(file_name))

  def compile(k, arch, bindings=(Binding.all,)):
    #Sanity checks
    if arch is None:
      raise Exception('No architecture unspecified')
    if bindings is None or len(bindings) == 0:
      raise Exception('No language bindings specified')
    #Generate the kernel
    Compiler.compile_kernel(k, arch)
    #Generate API for each language
    include_files = []
    if Binding.all in bindings or Binding.cpp in bindings:
      Compiler.compile_cpp(k)
      include_files.append(Compiler.get_cpp_file(k))
    if Binding.all in bindings or Binding.python in bindings:
      Compiler.compile_python(k)
      include_files.append(Compiler.get_python_file(k))
    if Binding.all in bindings or Binding.java in bindings:
      Compiler.compile_java(k)
      include_files.append(Compiler.get_java_file(k))
    #Generate the core
    Compiler.compile_core(k, include_files)
    #todo: build