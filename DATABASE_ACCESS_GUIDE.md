# Database Access Guide for Odoo Project

## Connection Information

From your `odoo.conf` file:
- **Host**: localhost (default)
- **Port**: 5432
- **User**: odoo
- **Password**: #Password0910
- **Database Name**: Check your database list (e.g., `odoo-dev`)

## Methods to Edit Database

### 1. Using PostgreSQL Command Line (psql)

```bash
# Connect to PostgreSQL
psql -h localhost -p 5432 -U odoo -d your_database_name

# Example queries:
# List all tables
\dt

# View data from a table
SELECT * FROM logilink_purchase_request_header;

# Update a record
UPDATE logilink_purchase_request_header SET status = 'approved' WHERE id = 1;

# Insert a new record
INSERT INTO logilink_purchase_request_header (pr_number, date_requested, status, active) 
VALUES ('PR-001', CURRENT_DATE, 'draft', true);
```

### 2. Using pgAdmin (GUI Tool)

1. Download and install pgAdmin from https://www.pgadmin.org/
2. Connect using:
   - Host: localhost
   - Port: 5432
   - Username: odoo
   - Password: #Password0910
3. Browse and edit tables through the GUI

### 3. Using DBeaver (Free Database Tool)

1. Download DBeaver from https://dbeaver.io/
2. Create new PostgreSQL connection:
   - Host: localhost
   - Port: 5432
   - Database: your_database_name
   - Username: odoo
   - Password: #Password0910
3. Browse and edit data visually

### 4. Using Odoo's Database Manager

1. Go to: http://localhost:8069/web/database/manager
2. Select your database
3. Use the database management interface

### 5. Using Python Script

```python
import psycopg2

# Connect to database
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="your_database_name",
    user="odoo",
    password="#Password0910"
)

cursor = conn.cursor()

# Execute queries
cursor.execute("SELECT * FROM logilink_purchase_request_header")
records = cursor.fetchall()

# Update records
cursor.execute("UPDATE logilink_purchase_request_header SET status = 'approved' WHERE id = 1")
conn.commit()

cursor.close()
conn.close()
```

## Important Tables in Your Logilink Module

- `logilink_purchase_request_header` - Purchase Requests
- `logilink_purchase_request_line` - Purchase Request Lines
- `logilink_purchase_order_header` - Purchase Orders
- `logilink_purchase_order_line` - Purchase Order Lines
- `logilink_goods_receipt_header` - GRN Headers
- `logilink_goods_receipt_line` - GRN Lines
- `logilink_supplier_invoice_header` - Supplier Invoices
- `logilink_supplier_invoice_line` - Invoice Lines
- `logilink_payment_header` - Payments
- `logilink_asset` - Assets
- `logilink_department` - Departments

## ⚠️ WARNING

**Always backup your database before making direct edits!**

```bash
# Backup command
pg_dump -h localhost -U odoo -d your_database_name > backup.sql

# Restore command
psql -h localhost -U odoo -d your_database_name < backup.sql
```

## Best Practices

1. **Use Odoo Web Interface** when possible - it maintains data integrity
2. **Use Developer Mode** for technical inspections
3. **Direct SQL edits** should be done carefully and only when necessary
4. **Always backup** before making direct database changes
5. **Test changes** in a development database first
