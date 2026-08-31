# POS Product Packaging - Odoo 17

This module allows Point of Sale users to add products using packaging (packages/boxes/cartons) instead of individual units.

## Features

- **Select Product Packaging**: Choose from available packaging options (Box, Carton, Pallet, etc.)
- **Enter Package Quantity**: Specify how many packages to add
- **Automatic Calculation**: Total units and price are calculated automatically
- **Order Line Display**: Shows package quantity alongside the regular quantity
- **Edit Packaging**: Modify packaging on existing order lines
- **Backend Integration**: View packaging info in POS orders

## Installation

1. Copy the `pos_product_packaging` folder to your Odoo addons directory
2. Update the apps list: `Settings > Apps > Update Apps List`
3. Install the module: Search for "POS Product Packaging" and click Install

## Configuration

### Setting Up Product Packaging

In Odoo 19 a packaging **is a unit of measure**. There is no separate packaging
model any more, so setting one up is two steps: define the unit, then say which
products are sold in it.

**1. Define the unit** - `Inventory > Configuration > Units of Measure`
   - **Name**: e.g. "Box of 12", "25 kg Bag", "Pallet"
   - **Relative Factor / Relative UoM**: how many of the smaller unit it holds,
     e.g. `12` &times; `Units`

**2. Allow it in the POS** - `Point of Sale > Configuration > POS Packagings`
   - Clear the **Available in POS** filter to see every unit
   - Tick the units the POS should offer

   This flag lives on the unit itself, so ticking "Box of 12" once enables it
   for every product sold in boxes of twelve.

**3. Put it on the product** - open the product and add the unit under
   **Packagings**. A product offers a packaging only when the unit is listed
   there *and* ticked in step 2.

### Example Setup

For a product "Widget" whose selling unit is Units:

| Unit          | Relative Factor | Available in POS |
|---------------|-----------------|------------------|
| Box of 12     | 12 &times; Units | Yes             |
| Carton of 48  | 48 &times; Units | Yes             |
| Pallet        | 480 &times; Units | Yes            |

Add all three under **Packagings** on the Widget, and the POS offers all three.

## Usage

### Adding Products with Packaging

1. Open Point of Sale
2. Click on a product that has packaging configured
3. A popup will appear with available packaging options
4. Select the packaging type (e.g., "Box - 12 units")
5. Enter the package quantity (e.g., 2)
6. The popup shows:
   - Total units: 24 (2 boxes × 12 units)
   - Total price: calculated automatically
7. Click "Confirm" to add to the order

### Order Line Display

The order line will show:
- Product name
- Total quantity (e.g., 24)
- Packaging info (e.g., "2 x Box")
- Total price

### Editing Packaging

1. Select an order line with packaging
2. Click the "Packaging" button in the control buttons
3. Modify the packaging type or quantity
4. Click "Confirm" to update

### Adding Without Packaging

If you want to add a single unit instead of using packaging:
1. In the packaging popup, click "Add Single Unit"
2. The product will be added with quantity 1

## Technical Details

### Models Extended

- `product.packaging`: Added `available_in_pos` field
- `pos.order.line`: Added `packaging_id` and `package_qty` fields
- `pos.session`: Extended to load packaging data

### JavaScript Components

- `PosStore`: Extended to index packaging by product
- `Orderline`: Extended to handle packaging data
- `ProductScreen`: Extended to show packaging popup
- `PackagingPopup`: New popup for packaging selection
- `PackagingButton`: Control button to edit packaging

## Compatibility

- Odoo 19.0 Community and Enterprise
- Requires: `point_of_sale`, `product` modules

## License

LGPL-3

## Credits

**Author:** Mohamed Yaseen Dahab

**Contributor:** Brice Michael Tchamou - reported the Odoo 19 incompatibility, identified
that packagings are `uom.uom` records rather than `product.uom` link rows, and
contributed the multi-packaging cart design that keeps two packaging sizes of
the same product on separate order lines.

## Support

For issues or feature requests:

- WhatsApp: <https://wa.me/201007802335> (+20 100 780 2335)
- Email: mohamed.yaseen.dahab@gmail.com
