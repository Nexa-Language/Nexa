import os
from setuptools import setup, find_packages

def get_version():
    """从项目根目录 VERSION 文件读取版本号"""
    with open(os.path.join(os.path.dirname(__file__), "VERSION")) as f:
        return f.read().strip()

with open("requirements.txt") as f:
    requirements = f.read().splitlines()

setup(
    name="nexa-lang",
    version=get_version(),
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
        "License :: OSI Approved :: GNU Affero General Public License v3 (AGPLv3)",
        "Operating System :: OS Independent",
    ],
)
