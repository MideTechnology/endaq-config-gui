import codecs
import os.path
import setuptools

def read(rel_path):
    here = os.path.abspath(os.path.dirname(__file__))
    with codecs.open(os.path.join(here, rel_path), 'r') as fp:
        return fp.read()


def get_version(rel_path):
    for line in read(rel_path).splitlines():
        if line.startswith('__version__'):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1]
    else:
        raise RuntimeError(f"Unable to find version string in {rel_path}.")



INSTALL_REQUIRES = [
    "endaq-device>=1.1.1",
    "wxPython>=4.2.0",
]

setuptools.setup(
        name='endaqconfig',
        version=get_version('endaqconfig/__init__.py'),
        author='Mide Technology',
        author_email='help@mide.com',
        description='Standalone GUI for configuring enDAQ data recorders',
        long_description=read('README.md'),
        long_description_content_type='text/markdown',
        url='https://github.com/MideTechnology/endaq-config-gui',
        license='MIT',
        classifiers=['Development Status :: 5 - Production/Stable',
                     'License :: OSI Approved :: MIT License',
                     'Natural Language :: English',
                     'Programming Language :: Python :: 3.9',
                     'Programming Language :: Python :: 3.10',
                     'Programming Language :: Python :: 3.11'],
        keywords='endaq slamstick config utility gui',
        packages=setuptools.find_packages(),
        package_dir={'': '.'},
        entry_points={'console_scripts': [
            'endaqconfig=endaqconfig.__main__:run',
        ]},
        install_requires=INSTALL_REQUIRES,
)
