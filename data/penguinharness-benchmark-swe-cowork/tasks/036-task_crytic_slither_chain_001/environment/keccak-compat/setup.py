from setuptools import setup
setup(name='pysha3', version='1.0.2+pycryptodome', py_modules=['sha3'],
      description='Local legacy pysha3 compatibility API backed by native PyCryptodome Keccak and Python SHA3',
      install_requires=['pycryptodome==3.23.0'], python_requires='>=3.8')
