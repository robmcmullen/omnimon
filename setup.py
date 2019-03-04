import os
import sys
import shutil
import glob
import subprocess
from setuptools import find_packages
from setuptools import setup
from distutils.extension import Extension

install_requires = [
    'numpy',
    'jsonpickle>=0.9.4',
    'bson<1.0.0',
    'configobj',
    'pyparsing',
    'pytz',
    'wxpython>=4.0.3',
    'fleep',
    ]

cmdclass = dict()

exec(compile(open('sawx/_version.py').read(), 'sawx/_version.py', 'exec'))
exec(compile(open('sawx/_metadata.py').read(), 'sawx/_metadata.py', 'exec'))

full_version = __version__
spaceless_version = full_version.replace(" ", "_")

# package_data is for pip and python installs, not for app bundles. Need
# to use data_files for that
package_data = {
    'sawx': ['icons/*.png',
                 'icons/*.ico',
                 'templates/*',
                 ],
    }

# Must explicitly add namespace packages
packages = find_packages()
packages.append("sawx.editors")

base_dist_dir = "dist-%s" % spaceless_version
win_dist_dir = os.path.join(base_dist_dir, "win")
mac_dist_dir = os.path.join(base_dist_dir, "mac")

is_64bit = sys.maxsize > 2**32

options = {}

# data files are only needed when building an app bundle
data_files = []

setup(
    name = 'sawx',
    version = full_version,
    author = __author__,
    author_email = __author_email__,
    url = __url__,
    download_url = ('%s/%s.tar.gz' % (__download_url__, full_version)),
    classifiers = [c.strip() for c in """\
        Development Status :: 5 - Production/Stable
        Intended Audience :: Developers
        License :: OSI Approved :: GNU General Public License (GPL)
        Operating System :: MacOS
        Operating System :: Microsoft :: Windows
        Operating System :: OS Independent
        Operating System :: POSIX
        Operating System :: Unix
        Programming Language :: Python
        Topic :: Utilities
        Topic :: Software Development :: Libraries :: Application Frameworks
        Topic :: Software Development :: User Interfaces
        """.splitlines() if len(c.strip()) > 0],
    description = "Simple Application-framework for wxPython",
    long_description = open('README.rst').read(),
    cmdclass = cmdclass,
    ext_modules = [],
    install_requires = install_requires,
    setup_requires = ["numpy"],
    license = "GPL",
    packages = packages,
    package_data = package_data,
    data_files=data_files,
    entry_points={
        "sawx.loaders": [
            'fleep = sawx.loaders.fleep',
            'text = sawx.loaders.text',
        ],
        "sawx.editors": [
            'html = sawx.editors.html_viewer',
            'text = sawx.editors.text_editor',
        ],
    },
    options=options,
    platforms = ["Windows", "Linux", "Mac OS-X", "Unix"],
    zip_safe = False,
    )
