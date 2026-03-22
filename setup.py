from setuptools import setup, find_packages 

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

setup(
    name="opensign_integration",
    version="1.0.0",
    description="OpenSign API Integration for Digital Signatures in Frappe/ERPNext",
    author="Your Company",
    author_email="info@yourcompany.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
    python_requires=">=3.8",
)
