from setuptools import setup, find_packages
import os

setup(
    name="mlsysops-cli",
    version=os.getenv("CI_COMMIT_TAG","0.0.0"),
    description="The MLSysOps Agents Framework CLI.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="MLSysOps Project Consortium",
    author_email="info@mlsysops.eu",
    url="https://github.com/mlsysops-project/mlsysops-framework",
    license='Apache License 2.0',
    packages=find_packages(),
    include_package_data=True,  # Includes non-code files specified in `MANIFEST.in`
    install_requires=[
        "click>=8.0",
          "requests>=2.25",
          "PyYAML>=5.4",
          "ruamel.yaml>=0.17",
          "kubernetes>=26.1.0",
          "jinja2>=3.1"
    ],
    package_data={
        "mlsysops_cli": ["templates/*.j2","deployment/*/*.yaml"],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
    ],
)
