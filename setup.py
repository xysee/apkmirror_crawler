from setuptools import setup, find_packages

setup(
    name="apkmirrorcrawler",
    version="1.0",
    packages=find_packages(),
    install_requires=[
        "requests",
        "beautifulsoup4",
        "pymongo"
    ],
    entry_points={
        "console_scripts": [
            "apkmirror-crawl=apkmirrorcrawler.cli:main"
        ]
    }
)