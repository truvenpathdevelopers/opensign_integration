app_name = "opensign_integration"
app_title = "OpenSign Integration"
app_publisher = "Your Company"
app_description = "OpenSign API Integration for Digital Signatures in Frappe/ERPNext"
app_email = "info@yourcompany.com"
app_license = "MIT"
required_apps = ["frappe"]

# Includes in <head>
app_include_css = "/assets/opensign_integration/css/opensign.css"
app_include_js = "/assets/opensign_integration/js/opensign.js"

# Document Events
doc_events = {
    "OpenSign Document": {
        "after_insert": "opensign_integration.utils.opensign_client.on_document_insert",
        "on_update": "opensign_integration.utils.opensign_client.on_document_update"
    }
}

# Scheduled Tasks
scheduler_events = {
    "hourly": [
        "opensign_integration.utils.opensign_client.sync_document_statuses"
    ]
}

# Website Route Rules
website_route_rules = [
    {"from_route": "/opensign-webhook", "to_route": "opensign_webhook"}
]

# Fixtures - export these doctypes
fixtures = [
    {
        "dt": "Custom Field",
        "filters": [["module", "=", "OpenSign Integration"]]
    }
]

# Jinja Environment
jinja = {
    "methods": [
        "opensign_integration.utils.opensign_client.get_signing_url"
    ]
}
