from distutils.core import setup
import setuptools

setup(name='telemetry-python',
      version='1.0.0',
      package_dir={"": "telemetry-python"},
      packages=setuptools.find_namespace_packages(where='telemetry-python'),
      install_requires=[
            'decorator',
            'pytest',
            'python-json-logger',
            'opentelemetry-api==0.16b1',
            'opentelemetry-exporter-prometheus==0.16b1',
            'opentelemetry-instrumentation-boto==0.16b1',
            'opentelemetry-instrumentation-dbapi==0.16b1',
            'opentelemetry-instrumentation-elasticsearch==0.16b1',
            'opentelemetry-instrumentation-flask==0.16b1',
            'opentelemetry-instrumentation-grpc==0.16b1',
            'opentelemetry-instrumentation-psycopg2==0.16b1',
            'opentelemetry-instrumentation-requests==0.16b1',
            'opentelemetry-sdk==0.16b1',
            'opentelemetry-instrumentation-sqlalchemy==0.16b1',
            'opentelemetry-instrumentation-wsgi==0.16b1',
      ]
)
