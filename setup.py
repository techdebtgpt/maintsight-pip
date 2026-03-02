#!/usr/bin/env python3

import os

from setuptools import find_packages, setup


# Read README for long description
def read_readme():
    here = os.path.abspath(os.path.dirname(__file__))
    with open(os.path.join(here, "README.md"), "r", encoding="utf-8") as f:
        return f.read()


# Read version from __init__.py
def read_version():
    here = os.path.abspath(os.path.dirname(__file__))
    version_file = os.path.join(here, "__init__.py")
    with open(version_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("__version__"):
                return line.split("=")[1].strip().strip('"').strip("'")
    return "0.1.0"


setup(
    name="maintsight",
    version=read_version(),
    description=(
        "AI-powered maintenance risk predictor for git repositories "
        "with interactive HTML reports and database integration"
    ),
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    author="TechDebtGPT Team",
    author_email="support@techdebtgpt.com",
    url="https://github.com/techdebtgpt/maintsight-pip",
    project_urls={
        "Bug Tracker": "https://github.com/techdebtgpt/maintsight-pip/issues",
        "Documentation": "https://github.com/techdebtgpt/maintsight-pip#readme",
        "Source Code": "https://github.com/techdebtgpt/maintsight-pip",
    },
    packages=find_packages(exclude=["tests*"]),
    package_data={
        "models": ["*.pkl", "*.json"],
        "utils": ["templates/*.html"],
    },
    include_package_data=True,
    python_requires=">=3.8",
    install_requires=[
        "click>=8.0.0",
        "dill>=0.3.6",
        "gitpython>=3.1.0",
        "joblib>=1.3.0",
        "numpy>=1.21.0",
        "pandas>=1.3.0",
        "scikit-learn>=1.1.0",
        "xgboost>=1.7.0",
        "rich>=12.0.0",
        "tqdm>=4.62.0",
        'typing-extensions>=4.0.0; python_version<"3.10"',
        "requests>=2.25.0",
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0.0",
            "pytest-cov>=2.12.0",
            "ruff>=0.1.0",
            "mypy>=0.950",
            "pre-commit>=2.15.0",
        ],
        "api": [
            "fastapi>=0.104.0",
            "uvicorn[standard]>=0.24.0",
            "pydantic>=2.4.0",
            "sqlalchemy>=2.0.0",
            "psycopg2-binary>=2.9.0",
            "alembic>=1.12.0",
            "python-dotenv>=1.0.0",
            "python-multipart>=0.0.6",
        ],
    },
    entry_points={
        "console_scripts": [
            "maintsight=cli:main",
            "ms=cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: Software Development :: Version Control :: Git",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    keywords=(
        "maintenance technical-debt risk-prediction xgboost git "
        "code-quality machine-learning repository-health"
    ),
    license="Apache-2.0",
    zip_safe=False,
)
