from setuptools import setup, find_packages

setup(
    name="ain-second-brain",
    version="1.0.0",
    description="Autonomous Intelligence Network (AIN) - Local Agentic Second Brain",
    author="Sambit Mishra",
    packages=find_packages(),
    install_requires=[
        "numpy>=1.24.0",
        "pandas>=2.0.0",
        "scikit-learn>=1.3.0",
        "faiss-cpu>=1.7.4",
        "yfinance>=0.2.28",
        "ollama>=0.1.0"
    ],
    entry_points={
        "console_scripts": [
            "ain=ain:main",
        ],
    },
)
