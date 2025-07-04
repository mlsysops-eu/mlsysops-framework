from setuptools import setup, find_packages
import os

setup(
    name="mlsysops",
    version=os.getenv("CI_COMMIT_TAG","0.0.0"),
    description="The core python package for MLSysOps Agents Framework.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="MLSysOps Project Consortium",
    author_email="info@mlsysops.eu",
    url="https://github.com/mlsysops-project/mlsysops-framework",
    license='Apache License 2.0',
    packages=find_packages(),
    include_package_data=True,  # Includes non-code files specified in `MANIFEST.in`
    install_requires=[
        "numpy>=1.20",
        "pandas==2.2.3",
        "spade==3.3.3",
        "jinja2==3.0.3",
        "kubernetes==32.0.1",
        "kubernetes_asyncio==32.0.0",
        "mlstelemetry==0.3.2",
        "python-dotenv==1.1.0",
        "PyYAML==6.0.2",
        "redis",
        "ruamel.yaml",
        "watchdog"
    ],
    package_data={
        "mlsysops": ["templates/*.j2","policies/*.py"],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
    ],
)
