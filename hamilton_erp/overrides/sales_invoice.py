"""Override class for the standard ERPNext Sales Invoice.

Adds Hamilton-specific helper methods without modifying ERPNext core.
Prefer doc_events in hooks.py for lifecycle reactions; use this class only
when reusable methods on the document object itself are needed.
"""

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
