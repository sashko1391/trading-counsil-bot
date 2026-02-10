"""
Setup file для встановлення проєкту як пакету
"""

from setuptools import setup, find_packages

setup(
    name="trading-council-bot",
    version="0.1.0",
    
    # 🔧 ФІКС: Каже де шукати пакети
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    
    # 🔧 ФІКС: Оновлена залежність для Gemini
    install_requires=[
        "python-dotenv>=1.0.0",
        "pydantic>=2.5.0",
        "pydantic-settings>=2.1.0",
        "ccxt>=4.5.0",
        "anthropic>=0.18.0",
        "openai>=1.12.0",
        "google-genai>=0.3.0",  # 🔧 ЗМІНИЛИ: було google-generativeai
        "instructor>=0.4.0",
        "pytest>=7.4.0",
        "pytest-asyncio>=0.21.0",
    ],
    
    python_requires=">=3.10",
)
