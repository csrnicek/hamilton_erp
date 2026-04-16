"""Override class for the standard ERPNext Sales Invoice.

Adds Hamilton-specific helper methods without modifying ERPNext core.
Prefer doc_events in hooks.py for lifecycle reactions; use this class only
when reusable methods on the document object itself are needed.
"""

# UPGRADE CHECKPOINT — verified against ERPNext 16.13.2 (2026-04-15).
# This import path is tightly coupled to ERPNext's internal module layout.
# Re-verify after every ERPNext version bump: if the path moves, Hamilton
# ERP will fail to start. The test_override_doctype_class_loads_correctly
# test in test_database_advanced.py catches this at test time.
from erpnext.accounts.doctype.sales_invoice.sales_invoice import SalesInvoice


class HamiltonSalesInvoice(SalesInvoice):
	def has_admission_item(self) -> bool:
		"""Return True if the invoice contains at least one admission item."""
		return any(item.get("hamilton_is_admission") for item in self.items)

	def get_admission_category(self) -> str | None:
		"""Return the asset_category of the first admission item, or None."""
		for item in self.items:
			if item.get("hamilton_is_admission"):
				return item.get("hamilton_asset_category")
		return None

	def has_comp_admission(self) -> bool:
		"""Return True if any admission item is marked as a comp."""
		return any(
			item.get("hamilton_is_comp")
			for item in self.items
			if item.get("hamilton_is_admission")
		)
