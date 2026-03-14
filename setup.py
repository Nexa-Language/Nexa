from setuptools import setup, find_packages

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    name="nexa-lang",
    version="0.1.0",
    description="An Agent-Native Programming Language for the AI Era",
    long_description=open("README.md", "r", encoding="utf-8").read() if open("README.md").readable() else "",
    long_description_content_type="text/markdown",
    author="Nexa Core Team",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "nexa=src.cli:main",
        ],
    },
    install_requires=requirements,
    python_requires=">=3.10",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
