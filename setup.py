import setuptools

with open('README.md', 'r') as fh:
    long_description = fh.read()

INSTALL_REQUIRES = [
    "endaq-device @ git+https://github.com/MideTechnology/endaq-device.git@develop",
    "wxPython==4.2.0",
]

setuptools.setup(
        name='endaqconfig',
        version='1.0.0b1',
        author='Mide Technology',
        author_email='help@mide.com',
        description='Standalone GUI for configuring enDAQ data recorders',
        long_description=long_description,
        long_description_content_type='text/markdown',
        url='https://github.com/MideTechnology/endaq-config-gui',
        license='MIT',
        classifiers=['Development Status :: 5 - Production/Stable',
                     'License :: OSI Approved :: MIT License',
                     'Natural Language :: English',
                     'Programming Language :: Python :: 3.7',
                     'Programming Language :: Python :: 3.8',
                     'Programming Language :: Python :: 3.9',
                     'Programming Language :: Python :: 3.10'],
        keywords='endaq slamstick config utility gui',
        packages=setuptools.find_packages(),
        package_dir={'': '.'},
        # package_data={
        #     '': ['schemata/*']
        # },
        entry_points={'console_scripts': [
            'endaqconfig=endaqconfig.__main__:run',
        ]},
        # test_suite='tests',
        install_requires=INSTALL_REQUIRES,
        # extras_require={
        #     'test': INSTALL_REQUIRES + TEST_REQUIRES,
        #     },
)
