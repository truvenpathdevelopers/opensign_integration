# OpenSign Integration for Frappe/ERPNext

A complete integration of [OpenSign](https://opensignlabs.com) digital signature platform with Frappe Framework. Send documents for e-signature, track signing status, and manage signature workflows directly from your Frappe/ERPNext system.

## Features

- ✅ **User Creation & Management** - Sync contacts between Frappe and OpenSign
- ✅ **PDF Signature Workflow** - Send any PDF for digital signatures
- ✅ **Multi-Signer Support** - Sequential or parallel signing workflows
- ✅ **Template-Based Generation** - Create reusable signature templates
- ✅ **Visual Widget Positioner** - Drag-and-drop signature placement
- ✅ **Webhook Integration** - Real-time status updates
- ✅ **Audit Trail** - Complete signing history with IP tracking
- ✅ **Form Integration** - Add signature buttons to any DocType

## Installation

### 1. Install the App

```bash
cd ~/frappe-bench
bench get-app https://github.com/your-org/opensign_integration
bench --site your-site.local install-app opensign_integration
bench migrate
bench build
bench restart
```

### 2. Configure API Token

1. Log in to [OpenSign](https://app.opensignlabs.com)
2. Go to **Settings → API Token**
3. Generate a **Live API Token** (requires paid plan) or **Sandbox Token** (free for testing)
4. In Frappe, go to **OpenSign Settings**
5. Enter your API Token
6. Save

### 3. Setup Webhook (Optional but Recommended)

1. Go to **OpenSign Settings**
2. Click **Setup Webhook**
3. This configures OpenSign to send real-time updates to your Frappe site

---

## Usage Guide

### 1. Sending a Document for Signature

#### From Any DocType Form

```javascript
// In your DocType's JS file
frappe.ui.form.on('Sales Invoice', {
    refresh: function(frm) {
        if (frm.doc.docstatus === 1) {
            frm.add_custom_button(__('Send for Signature'), function() {
                opensign.send_for_signature(frm.doctype, frm.doc.name);
            }, __('Actions'));
        }
    }
});
```

#### Programmatically via Python

```python
from opensign_integration.utils.opensign_client import OpenSignClient

client = OpenSignClient()

# Create and send document
result = client.create_document(
    file_path="/files/contract.pdf",
    title="Service Agreement",
    signers=[
        {
            "name": "John Doe",
            "email": "john@example.com",
            "widgets": [
                {
                    "type": "signature",
                    "page": 1,
                    "x": 350,
                    "y": 600,
                    "w": 150,
                    "h": 50
                },
                {
                    "type": "date",
                    "page": 1,
                    "x": 350,
                    "y": 540,
                    "w": 100,
                    "h": 20,
                    "options": {"signing_date": True}
                }
            ]
        }
    ],
    send_in_order=False,
    expiry_days=7
)

print(f"Document ID: {result['document_id']}")
```

### 2. Multi-Signer Workflow

#### Sequential Signing (Sign in Order)

```python
result = client.create_document(
    file_path="/files/contract.pdf",
    title="Multi-Party Agreement",
    signers=[
        {"name": "CEO", "email": "ceo@company.com", "widgets": [...]},
        {"name": "CFO", "email": "cfo@company.com", "widgets": [...]},
        {"name": "Client", "email": "client@example.com", "widgets": [...]}
    ],
    send_in_order=True  # CEO signs first, then CFO, then Client
)
```

#### Parallel Signing (All at Once)

```python
result = client.create_document(
    file_path="/files/contract.pdf",
    title="Multi-Party Agreement",
    signers=[
        {"name": "Party A", "email": "a@example.com", "widgets": [...]},
        {"name": "Party B", "email": "b@example.com", "widgets": [...]},
    ],
    send_in_order=False  # Both receive and can sign simultaneously
)
```

#### Using the Multi-Signer Dialog (JavaScript)

```javascript
opensign.create_multi_signer_document({
    title: 'Partnership Agreement',
    workflow: 'sequential'  // or 'parallel'
});
```

### 3. Template-Based Document Generation

#### Creating a Template

```python
client = OpenSignClient()

# Create a reusable template
result = client.create_template(
    file_path="/files/nda_template.pdf",
    title="Standard NDA",
    roles=["Disclosing Party", "Receiving Party"],
    widgets=[
        {
            "role": "Disclosing Party",
            "type": "signature",
            "page": 2,
            "x": 100,
            "y": 500,
            "w": 150,
            "h": 50
        },
        {
            "role": "Disclosing Party",
            "type": "date",
            "page": 2,
            "x": 100,
            "y": 440,
            "w": 100,
            "h": 20,
            "options": {"signing_date": True}
        },
        {
            "role": "Receiving Party",
            "type": "signature",
            "page": 2,
            "x": 350,
            "y": 500,
            "w": 150,
            "h": 50
        },
        {
            "role": "Receiving Party",
            "type": "date",
            "page": 2,
            "x": 350,
            "y": 440,
            "w": 100,
            "h": 20,
            "options": {"signing_date": True}
        }
    ],
    is_public=False
)

template_id = result['template_id']
```

#### Using a Template

```python
# Create document from template
result = client.create_document_from_template(
    template_id="abc123",
    signers=[
        {"name": "Acme Corp", "email": "legal@acme.com", "role": "Disclosing Party"},
        {"name": "John Smith", "email": "john@example.com", "role": "Receiving Party"}
    ],
    title="NDA - Acme Corp & John Smith"
)
```

#### Using the Template Dialog (JavaScript)

```javascript
// Open template selector
opensign.select_template();

// Or directly create from a specific template
opensign.create_from_template('OSTPL-000001');
```

---

## Widget Positioning Guide

### Understanding Coordinates

OpenSign uses a coordinate system where:
- **Origin (0, 0)** is at the **top-left** corner of each page
- **X** increases going **right**
- **Y** increases going **down**
- Units are in **points** (1 point ≈ 1/72 inch)

### Standard Page Dimensions

| Page Size | Width (points) | Height (points) |
|-----------|----------------|-----------------|
| US Letter | 612 | 792 |
| A4 | 595 | 842 |
| Legal | 612 | 1008 |

### Widget Types and Recommended Sizes

| Widget Type | Description | Recommended Size (w × h) |
|-------------|-------------|--------------------------|
| `signature` | Handwritten/drawn signature | 150 × 50 |
| `initials` | Signer's initials | 60 × 30 |
| `stamp` | Company stamp/seal | 100 × 100 |
| `date` | Date picker | 100 × 20 |
| `textbox` | Free text input | 150 × 20 |
| `name` | Auto-filled signer name | 150 × 20 |
| `email` | Auto-filled signer email | 200 × 20 |
| `checkbox` | Multiple choice checkboxes | 150 × varies |
| `radio button` | Single choice radio | 150 × varies |
| `dropdown` | Dropdown selection | 150 × 25 |
| `image` | Image upload | 100 × 100 |
| `number` | Numeric input | 80 × 20 |

### Common Signature Placements

#### Bottom of Page (US Letter)

```python
# Single signature at bottom right
{
    "type": "signature",
    "page": 1,
    "x": 400,  # Right side
    "y": 700,  # Near bottom
    "w": 150,
    "h": 50
}

# Date below signature
{
    "type": "date",
    "page": 1,
    "x": 400,
    "y": 760,
    "w": 100,
    "h": 20
}
```

#### Two Signatures Side by Side

```python
# Left signature (Party A)
{
    "type": "signature",
    "page": 2,
    "x": 50,
    "y": 650,
    "w": 150,
    "h": 50
}

# Right signature (Party B)
{
    "type": "signature",
    "page": 2,
    "x": 350,
    "y": 650,
    "w": 150,
    "h": 50
}
```

#### Stacked Signatures (Multiple Signers)

```python
signers = []
y_position = 500

for i, signer in enumerate(signer_list):
    signers.append({
        "name": signer["name"],
        "email": signer["email"],
        "widgets": [
            {
                "type": "signature",
                "page": 1,
                "x": 100,
                "y": y_position,
                "w": 150,
                "h": 50
            },
            {
                "type": "date",
                "page": 1,
                "x": 270,
                "y": y_position + 15,
                "w": 100,
                "h": 20,
                "options": {"signing_date": True}
            }
        ]
    })
    y_position += 80  # Stack vertically with 80pt spacing
```

### Using the Visual Positioner

The app includes a visual widget positioner that lets you click on a PDF to place widgets:

```javascript
// Open the visual positioner
opensign.show_widget_positioner('/files/contract.pdf', function(widgets) {
    console.log('Placed widgets:', widgets);
    // Use these widget positions in your document
});
```

### Using OpenSign's Debug UI

OpenSign provides a [Debug UI](https://app.opensignlabs.com/debugpdf) for testing widget positions:

1. Upload your PDF to the Debug UI
2. Click to add widgets visually
3. Copy the generated JSON coordinates
4. Use those coordinates in your API calls

### Widget Options Reference

#### Signature Widget

```python
{
    "type": "signature",
    "page": 1,
    "x": 350,
    "y": 600,
    "w": 150,
    "h": 50,
    "options": {
        "hint": "Please sign here"  # Tooltip text
    }
}
```

#### Date Widget

```python
{
    "type": "date",
    "page": 1,
    "x": 350,
    "y": 540,
    "w": 100,
    "h": 20,
    "options": {
        "required": True,
        "signing_date": True,  # Auto-fill with signing date
        "format": "mm/dd/yyyy",  # Date format
        "min_date": "2024-01-01",  # Optional minimum date
        "max_date": "2024-12-31"   # Optional maximum date
    }
}
```

#### Textbox Widget

```python
{
    "type": "textbox",
    "page": 1,
    "x": 200,
    "y": 400,
    "w": 200,
    "h": 25,
    "options": {
        "required": True,
        "hint": "Enter company name",
        "default": "",  # Pre-filled value
        "readonly": False,
        "regularexpression": "^[A-Za-z ]+$"  # Validation regex
    }
}
```

#### Checkbox Widget

```python
{
    "type": "checkbox",
    "page": 1,
    "x": 100,
    "y": 300,
    "w": 200,
    "h": 80,
    "options": {
        "required": True,
        "values": ["Option A", "Option B", "Option C"],
        "selectedvalues": ["Option A"],  # Pre-selected
        "layout": "vertical",  # or "horizontal"
        "validation": {
            "minselections": 1,
            "maxselections": 2
        }
    }
}
```

#### Dropdown Widget

```python
{
    "type": "dropdown",
    "page": 1,
    "x": 100,
    "y": 250,
    "w": 150,
    "h": 25,
    "options": {
        "required": True,
        "values": ["Yes", "No", "Maybe"],
        "default": "Yes"
    }
}
```

---

## API Reference

### OpenSignClient Methods

#### User Management

| Method | Description |
|--------|-------------|
| `get_user()` | Get current account details |
| `get_api_credits()` | Get remaining API credits |

#### Contact Management

| Method | Description |
|--------|-------------|
| `create_contact(name, email, phone)` | Create a signer contact |
| `get_contact(contact_id)` | Get contact details |
| `get_contact_list()` | Get all contacts |
| `delete_contact(contact_id)` | Delete a contact |

#### Document Management

| Method | Description |
|--------|-------------|
| `create_document(...)` | Create and send document |
| `create_draft_document(...)` | Create draft (not sent) |
| `create_document_from_template(...)` | Create from template |
| `get_document(document_id)` | Get document details |
| `get_document_list(status)` | List documents by status |
| `revoke_document(document_id)` | Cancel a document |
| `delete_document(document_id)` | Delete a document |
| `resend_request_mail(...)` | Resend to signer |
| `self_sign(...)` | Generate self-sign URL |

#### Template Management

| Method | Description |
|--------|-------------|
| `create_template(...)` | Create reusable template |
| `get_template(template_id)` | Get template details |
| `get_template_list()` | List all templates |
| `delete_template(template_id)` | Delete template |

#### Webhook Management

| Method | Description |
|--------|-------------|
| `create_webhook(url, events)` | Register webhook |
| `get_webhooks()` | List webhooks |
| `delete_webhook(webhook_id)` | Delete webhook |

---

## Webhook Events

| Event | Description |
|-------|-------------|
| `document.completed` | All signers have signed |
| `document.declined` | A signer declined |
| `document.viewed` | A signer viewed the document |
| `document.signed` | A signer completed their signature |
| `document.expired` | Document reached expiry date |

---

## Troubleshooting

### Common Issues

**"Invalid API Token"**
- Verify your API token in OpenSign Settings
- Ensure you're using the correct token (Live vs Sandbox)
- Check if your OpenSign plan includes API access

**"Document not found"**
- The OpenSign Document ID may be incorrect
- The document may have been deleted in OpenSign

**Webhook not receiving events**
- Verify your site URL is publicly accessible
- Check the webhook URL in OpenSign Settings
- Review Frappe error logs for webhook errors

**PDF not rendering in positioner**
- Ensure the PDF is accessible via the provided URL
- Check browser console for PDF.js errors

### Debug Mode

Enable debug logging in `site_config.json`:

```json
{
    "developer_mode": 1
}
```

This will log all API requests and responses to the Error Log.

---

## License

MIT License - see LICENSE file for details.

## Support

- **Documentation**: https://docs.opensignlabs.com
- **GitHub Issues**: [Report bugs](https://github.com/your-org/opensign_integration/issues)
- **OpenSign Support**: support@opensignlabs.com
