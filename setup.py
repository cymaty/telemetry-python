from distutils.core import setup
import setuptools

setup(name='telemetry-python',
      version='1.0.0',
      package_dir={"": "telemetry-python"},
      packages=setuptools.find_namespace_packages(where='telemetry-python')
)
