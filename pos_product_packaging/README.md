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

1. Go to `Inventory > Products > Products`
2. Select a product
3. Go to the "Inventory" tab
4. In the "Packaging" section, add packaging types:
   - **Name**: e.g., "Box", "Carton", "Case"
   - **Quantity**: Number of units per package (e.g., 20)
   - **Available in POS**: Check this to make it available in POS

### Example Setup

For a product "Widget":
| Packaging Name | Quantity | Available in POS |
|----------------|----------|------------------|
| Box            | 12       | ✓                |
| Carton         | 48       | ✓                |
| Pallet         | 480      | ✓                |

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

- Odoo 17.0 Community and Enterprise
- Requires: `point_of_sale`, `product` modules

## License

LGPL-3

## Support

For issues or feature requests, please contact [your-email@example.com]
