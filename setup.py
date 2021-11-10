from setuptools import find_packages, setup

from spire.version import SPIRE_VERSION

long_description = ""
with open("README.md") as ifp:
    long_description = ifp.read()

setup(
    name="bugout-spire",
    version=SPIRE_VERSION,
    author="Bugout.dev",
    author_email="engineering@bugout.dev",
    description="Spire: Bugout custom knowledge base",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/bugout-dev/spire",
    platforms="all",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Natural Language :: English",
        "Programming Language :: Python",
        "License :: OSI Approved :: Apache Software License",
        "Topic :: Software Development :: Libraries",
    ],
    python_requires=">=3.6",
    packages=find_packages(),
    package_data={"bugout": ["py.typed"]},
    zip_safe=False,
    install_requires=[
        "appdirs",
        "boto3>=1.20.2",
        "bugout>=0.1.18",
        "bugout-brood>=0.2.0",
        "bugout-locust>=0.2.8",
        "cached-property",
        "chardet",
        "elasticsearch",
        "fastapi>=0.70.0",
        "jwt",
        "httptools",
        "multidict",
        "psycopg2-binary>=2.9.1",
        "pydantic",
        "pyjwt",
        "redis",
        "requests",
        "sqlalchemy>=1.4.26",
        "typed-ast",
        "uvicorn>=0.15.0",
    ],
    extras_require={
        "dev": ["alembic", "black", "isort", "mypy", "types-requests"],
        "distribute": ["setuptools", "twine", "wheel"],
    },
)
