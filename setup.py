#!/usr/bin/env python

from setuptools import setup, find_packages
import pathlib

readme_md = pathlib.Path('README.md').read_text(encoding='utf-8')

extras_require = {
    'develop': ['bumpversion', 'black', 'pyflakes'],
    'test': ['pytest', 'pytest-cov', 'coverage', 'pytest-mock'],
    'docs': ['sphinx', 'sphinx_rtd_theme'],
    'complete': sorted(set(sum(extras_require.values(), [])))
}

setup(
    name='tcadana',
    version='1.0.0',
    package_dir={"": "src"},
    packages=find_packages(where="src", exclude=["tests"]),
    include_package_data=True,
    description='Python tools for analyzing TCAD data',
    long_description=readme_md,
    long_description_content_type='text/markdown',
    url='https://github.com/neko-0/tcadana.git',
    author='ITk team at Carleton University',
    maintainer='Yuzhan Zhao',
    maintainer_email='yuzhan.physics@gmail.com',
    license='Apache License 2.0',
    keywords='Python tools for analyzing TCAD data',
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
    ],
    python_requires=">=3.8, <3.14",
    install_requires=[
        'numpy',
        'scipy',
        'h5py',
        'numba',
        'click',
        'tqdm',
        'lazy_loader',
        'matplotlib',
    ],
    extras_require=extras_require,
    dependency_links=[],
    entry_points={'console_scripts': ['tcadana=tcadana.cli:tcadana']},
)