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
        "aiofiles",
        "aiohttp",
        "appdirs",
        "attrs",
        "boto3>=1.20.2",
        "bugout>=0.1.19",
        "bugout-brood>=0.2.2",
        "bugout-locust>=0.2.8",
        "cached-property",
        "chardet",
        "cryptography",
        "docutils",
        "elasticsearch==7.8.1",
        "fastapi>=0.75.0",
        "httptools",
        "multidict",
        "protobuf==3.19.1",
        "psycopg2-binary>=2.9.1",
        "pydantic<=1.10.2",
        "PyJWT==1.7.1",
        "redis",
        "requests",
        "sqlalchemy>=1.4.26",
        "toml",
        "typed-ast",
        "uvicorn>=0.17.6",
        "uvloop",
        "web3>=5.30.0",
        "websockets",
        "yarl",
    ],
    extras_require={
        "dev": [
            "alembic",
            "black",
            "isort",
            "mypy",
            "types-redis",
            "types-requests",
            "types-python-dateutil",
            "types-toml",
        ],
        "distribute": ["setuptools", "twine", "wheel"],
    },
    entry_points={
        "console_scripts": [
            "journals=spire.journal.cli:main",
            "public-journals=spire.public.cli:main",
        ]
    },
)
