from setuptools import setup

setup(name='nuimo',
      version='1.0.0',
      description='Nuimo SDK for Python on Linux',
      url='https://github.com/getsenic/nuimo-linux-python',
      maintainer='Lars Blumberg',
      maintainer_email='lars@senic.com',
      license='MIT',
      install_requires=['gattlib'],
      py_modules=['nuimo'])
