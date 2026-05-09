# setup.py
from setuptools import setup
from Cython.Build import cythonize

modules = [
    "Utils.py",
    "Database.py",
    "Channel.py",
    "Client.py",
    "Server.py"
]

setup(
    name='BigIRCd',
    ext_modules=cythonize(modules, compiler_directives={'language_level': "3"}),
)