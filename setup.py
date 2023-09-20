import os
import sys
from setuptools import find_packages, setup
from distutils import sysconfig


with open('./README.md', 'r') as f:
    long_description = f.read()

site_packages_path = sysconfig.get_python_lib(prefix='./')

python_version = sys.version_info
python_version_str = "{}{}".format(python_version.major, python_version.minor)

setup(
    name='pbs-python',
    setup_requires=['setuptools_scm'],
    use_scm_version={
        'version_scheme': 'post-release',
    },
    description='Openpbs/Torque Python interface',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/exabyte-io/pbs-python',
    author='Exabyte Inc.',
    author_email='info@exabyte.io',
    license='LGPLv3',
    keywords=['pbs'],
    packages=find_packages(exclude=['tests*']),
    data_files=[
        (os.path.join(site_packages_path, 'pbs'), [
            'pbs/_pbs.so',
            'pbs/_pbs.cpython-{}-x86_64-linux-gnu.so'.format(python_version_str)
        ]),
    ],
    extras_require={
        "test": [
            "coverage[toml]>=5.3",
        ]
    },
    python_requires='>=2.7,!=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*,!=3.4.*,!=3.5.*,!=3.6.*,!=3.7.*',
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3.8',
        'Operating System :: POSIX :: Other',
        'License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)'
    ]
)
