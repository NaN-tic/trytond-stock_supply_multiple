# This file is part of Tryton.  The COPYRIGHT file at the top level of
# this repository contains the full copyright notices and license terms.
import math
from trytond.model import fields
from trytond.pool import PoolMeta

__all__ = ['ProductSupplier', 'PurchaseRequest', 'CreatePurchase']


class ProductSupplier(metaclass=PoolMeta):
    __name__ = 'purchase.product_supplier'
    multiple_quantity = fields.Float('Multiple Quantity')


class PurchaseRequest(metaclass=PoolMeta):
    __name__ = 'purchase.request'
    multiple_quantity = fields.Function(fields.Float('Multiple Quantity'),
        'on_change_with_multiple_quantity')

    @fields.depends('_parent_product.id','product')
    def on_change_with_multiple_quantity(self, name=None):
        if not self.product:
            return
        for product_supplier in self.product.product_suppliers_used():
            if product_supplier.party == self.party:
                return product_supplier.multiple_quantity


class CreatePurchase(metaclass=PoolMeta):
    __name__ = 'purchase.request.create_purchase'

    @classmethod
    def compute_purchase_line(cls, key, requests, purchase):
        line = super(CreatePurchase, cls).compute_purchase_line(key, requests,
            purchase)
        multiples = [x.multiple_quantity for x in requests if
                x.multiple_quantity]
        if multiples:
            multiple_quantity = max(multiples)
            line.quantity = (math.ceil(line.quantity /
                    multiple_quantity) * multiple_quantity)
        return line
