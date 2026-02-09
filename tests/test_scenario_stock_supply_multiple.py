import datetime
import unittest
from decimal import Decimal

from proteus import Model, Wizard
from trytond.modules.account.tests.tools import create_chart, get_accounts
from trytond.modules.company.tests.tools import create_company, get_company
from trytond.tests.test_tryton import drop_db
from trytond.tests.tools import activate_modules


class Test(unittest.TestCase):

    def setUp(self):
        drop_db()
        super().setUp()

    def tearDown(self):
        drop_db()
        super().tearDown()

    def test(self):

        # Install modules
        config = activate_modules(['stock_supply', 'stock_supply_multiple'])

        # Create company
        _ = create_company()
        company = get_company()

        # Reload the context
        User = Model.get('res.user')
        config._context = User.get_preferences(True, config.context)

        # Create chart of accounts
        _ = create_chart(company)
        accounts = get_accounts(company)
        expense = accounts['expense']
        revenue = accounts['revenue']

        # Create parties
        Party = Model.get('party.party')
        supplier = Party(name='Supplier')
        supplier.save()
        customer = Party(name='Customer')
        customer.save()

        # Create account category
        ProductCategory = Model.get('product.category')
        account_category = ProductCategory(name="Account Category")
        account_category.accounting = True
        account_category.account_expense = expense
        account_category.account_revenue = revenue
        account_category.save()

        # Base data
        ProductUom = Model.get('product.uom')
        ProductTemplate = Model.get('product.template')
        unit, = ProductUom.find([('name', '=', 'Unit')])

        def create_product(name, multiple_quantity):
            template = ProductTemplate()
            template.name = name
            template.default_uom = unit
            template.type = 'goods'
            template.purchasable = True
            template.list_price = Decimal('0')
            template.account_category = account_category
            product_supplier = template.product_suppliers.new()
            product_supplier.company = company
            product_supplier.party = supplier
            product_supplier.multiple_quantity = multiple_quantity
            template.save()
            product, = template.products
            return product

        product_multiple = create_product('Product Multiple', 5)
        product_round_up = create_product('Product Round Up', 4)

        # Get stock locations
        Location = Model.get('stock.location')
        warehouse_loc, = Location.find([('code', '=', 'WH')])
        customer_loc, = Location.find([('code', '=', 'CUS')])
        output_loc, = Location.find([('code', '=', 'OUT')])

        # Create needs for missing products
        ShipmentOut = Model.get('stock.shipment.out')
        shipment_out = ShipmentOut()
        shipment_out.planned_date = datetime.date.today()
        shipment_out.effective_date = datetime.date.today()
        shipment_out.customer = customer
        shipment_out.warehouse = warehouse_loc
        shipment_out.company = company

        move = shipment_out.outgoing_moves.new()
        move.product = product_multiple
        move.unit = unit
        move.quantity = 10
        move.from_location = output_loc
        move.to_location = customer_loc
        move.company = company
        move.unit_price = Decimal('1')
        move.currency = company.currency

        move = shipment_out.outgoing_moves.new()
        move.product = product_round_up
        move.unit = unit
        move.quantity = 10
        move.from_location = output_loc
        move.to_location = customer_loc
        move.company = company
        move.unit_price = Decimal('1')
        move.currency = company.currency

        shipment_out.click('wait')

        # Create the purchase requests
        create_pr = Wizard('stock.supply')
        create_pr.execute('create_')

        PurchaseRequest = Model.get('purchase.request')
        requests = PurchaseRequest.find([('state', '=', 'draft')])
        self.assertEqual(len(requests), 2)
        request_multiple = [r for r in requests if r.product == product_multiple][0]
        request_round_up = [r for r in requests if r.product == product_round_up][0]
        self.assertEqual(request_multiple.quantity, 10.0)
        self.assertEqual(request_multiple.multiple_quantity, 5.0)
        self.assertEqual(request_round_up.quantity, 10.0)
        self.assertEqual(request_round_up.multiple_quantity, 4.0)

        # Create purchase and check multiple quantity
        Wizard('purchase.request.create_purchase',
            [request_multiple, request_round_up])

        Purchase = Model.get('purchase.purchase')
        purchase, = Purchase.find()
        lines_by_product = {line.product.id: line for line in purchase.lines}

        self.assertEqual(lines_by_product[product_multiple.id].quantity, 10.0)
        self.assertEqual(lines_by_product[product_round_up.id].quantity, 12.0)
