from setuptools import setup, find_packages

setup(
    name='adriq',
    version='1.0',
    packages=find_packages(),  # This will include the 'adriq' package
    include_package_data=True,
    package_data={
        'adriq': ['DLL_32bit/*.dll', 'DLL_64bit/*.dll'],  # Include DLL files
    },
    install_requires=[
        # List any dependencies here
    ],
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