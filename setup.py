from setuptools import find_packages, setup

from spire.version import SPIRE_VERSION

MODULE_NAME = "spire"

long_description = ""
with open("README.md") as ifp:
    long_description = ifp.read()

setup(
    name=MODULE_NAME,
    version=SPIRE_VERSION,
    author="Bugout.dev",
    author_email="engineering@bugout.dev",
    description="Spire: Bugout custom knowledge base",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/bugout-dev/spire",
    platforms="all",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: Implementation :: CPython",
        "Topic :: Software Development :: Libraries",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.6",
    packages=find_packages(),
    package_data={"bugout": ["py.typed"]},
    zip_safe=False,
    install_requires=[
        "alembic",
        "boto3",
        "brood @ git+ssh://git@github.com/bugout-dev/brood.git@a1bb1ab20f14540c16e2c26bded36b1b23699004",
        "bugout",
        "bugout-locust",
        "elasticsearch",
        "fastapi",
        "jwt",
        "psycopg2-binary",
        "pydantic",
        "requests",
        "SQLAlchemy",
        "uvicorn",
    ],
    extras_require={"dev": ["black", "mypy"]},
)
