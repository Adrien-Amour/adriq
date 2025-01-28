from setuptools import setup, find_packages, Extension
from Cython.Build import cythonize
import numpy as np

extensions = [
    Extension(
        "adriq.tdc_functions",
        ["adriq/tdc_functions.pyx"],
        include_dirs=[np.get_include()],
        extra_compile_args=["-O3", "-Wall"]  # Add optimization and warning flags
    )
]

setup(
    name='adriq',
    version='1.1',
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'adriq': ['DLL_32bit/*.dll', 'DLL_64bit/*.dll', 'resources/*'],
    },
    install_requires=[
        # List any dependencies here
    ],
    ext_modules=cythonize(extensions),
    author='Adrien Amour',
    author_email='a.amour@sussex.ac.uk',
    description='A description of your package',
    url='https://github.com/adrien-amour/itcm',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)