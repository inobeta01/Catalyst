# Package configuration for Catalyst CLI.
# The CLI now uses task templates (workload/prompts/templates.py) for input
# instead of external fixture JSON files. No additional runtime dependencies
# are required beyond those already listed.
from setuptools import setup, find_packages

setup(
    name="catalyst",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "langgraph>=0.2.0",
        "langchain>=0.2.0",
        "langchain-core>=0.2.0",
        "langchain-community>=0.2.0",
        "langchain-openai>=0.1.0",
        "langchain-anthropic>=0.1.0",
        "arize-phoenix>=4.0.0",
        "agentops>=0.3.0",
        "openinference-instrumentation-langchain>=0.1.0",
        "opentelemetry-api>=1.20.0",
        "opentelemetry-sdk>=1.20.0",
        "opentelemetry-exporter-otlp>=1.20.0",
        "requests>=2.31.0",
        "pyyaml>=6.0",
        "python-dotenv>=1.0.0",
        "pydantic>=2.0.0",
        "presidio-analyzer>=2.2.0",
        "presidio-anonymizer>=2.2.0",
        "e2b-code-interpreter>=0.0.8",
        "pytest>=8.0.0",
    ],
    entry_points={
        'console_scripts': [
            'catalyst=cli.catalyst:main',
        ],
    },
)