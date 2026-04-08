from setuptools import setup, find_packages

from hamilton_erp import __version__ as version

setup(
	name="hamilton_erp",
	version=version,
	description="Custom Frappe app extending ERPNext for Club Hamilton",
	author="Chris Srnicek",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=["frappe"],
)
