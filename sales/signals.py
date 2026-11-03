"""Legacy module retained for compatibility.

Inventory is consumed explicitly within the payment transaction in
``sales.api.PaymentSerializer``. Keeping that operation out of signals makes
the payment, order state, table state and inventory movement a single
testable unit of work.
"""

