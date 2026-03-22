"""
OpenSign API Client for Frappe Framework
=========================================

Complete API wrapper for OpenSign digital signature platform.
Supports user management, contacts, documents, templates, webhooks, and folders.

Usage:
    from opensign_integration.utils.opensign_client import OpenSignClient
    client = OpenSignClient()
    result = client.create_document(...)
"""

import frappe
import requests
import base64
import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any, Union


class OpenSignClient:
    """
    OpenSign API Client
    
    Handles all communication with OpenSign API including:
    - User account management
    - Contact (signer) management
    - Document creation and tracking
    - Template management
    - Webhook configuration
    - Folder organization
    """
    
    BASE_URL_LIVE = "https://api.opensignlabs.com/v1"
    BASE_URL_SANDBOX = "https://sandbox.opensignlabs.com/v1"
    
    def __init__(self):
        """Initialize client with settings from OpenSign Settings DocType"""
        settings = frappe.get_single("OpenSign Settings")
        
        if not settings.api_token:
            frappe.throw("OpenSign API Token not configured. Please set it in OpenSign Settings.")
        
        self.api_token = settings.get_password("api_token")
        self.sandbox_mode = settings.sandbox_mode
        self.base_url = settings.base_url or (
            self.BASE_URL_SANDBOX if self.sandbox_mode else self.BASE_URL_LIVE
        )
        
        self.headers = {
            "Content-Type": "application/json",
            "x-api-token": self.api_token
        }
        
        # Default widget configurations
        self.default_signature_widget = {
            "type": "signature",
            "page": 1,
            "x": 350,
            "y": 600,
            "w": 150,
            "h": 50,
            "options": {"hint": "Please sign here"}
        }
    
    def _request(self, method: str, endpoint: str, data: Optional[Dict] = None, 
                 params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Make HTTP request to OpenSign API
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            data: Request body data
            params: Query parameters
            
        Returns:
            API response as dictionary
            
        Raises:
            frappe.ValidationError on API errors
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                params=params,
                timeout=60
            )
            
            # Log request for debugging
            if frappe.conf.get("developer_mode"):
                frappe.log_error(
                    title=f"OpenSign API: {method} {endpoint}",
                    message=f"Status: {response.status_code}\nResponse: {response.text[:500]}"
                )
            
            # Handle error responses
            if response.status_code == 405:
                frappe.throw("Invalid API Token. Please check your OpenSign API configuration.")
            elif response.status_code == 400:
                error_msg = response.json().get("message", "Bad request")
                frappe.throw(f"OpenSign API Error: {error_msg}")
            elif response.status_code == 404:
                frappe.throw("Resource not found in OpenSign")
            elif response.status_code >= 500:
                frappe.throw("OpenSign server error. Please try again later.")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.Timeout:
            frappe.log_error("OpenSign API request timed out", "OpenSign Integration")
            frappe.throw("OpenSign API request timed out. Please try again.")
        except requests.exceptions.ConnectionError:
            frappe.log_error("Could not connect to OpenSign API", "OpenSign Integration")
            frappe.throw("Could not connect to OpenSign. Please check your internet connection.")
        except requests.exceptions.RequestException as e:
            frappe.log_error(f"OpenSign API Error: {str(e)}", "OpenSign Integration")
            frappe.throw(f"OpenSign API Error: {str(e)}")
    
    # ========================================================================
    # USER MANAGEMENT
    # ========================================================================
    
    def get_user(self) -> Dict[str, Any]:
        """
        Get current user account details
        
        Returns:
            User account information including name, email, plan details
        """
        return self._request("GET", "getuser")
    
    def get_api_credits(self) -> Dict[str, Any]:
        """
        Get remaining API credits
        
        Returns:
            Credit balance and usage information
        """
        return self._request("GET", "getcredits")
    
    # ========================================================================
    # CONTACT MANAGEMENT
    # ========================================================================
    
    def create_contact(self, name: str, email: str, phone: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new signer contact
        
        Args:
            name: Full name of the contact
            email: Email address
            phone: Optional phone number
            
        Returns:
            Created contact details with contact_id
        """
        data = {
            "name": name,
            "email": email
        }
        if phone:
            data["phone"] = phone
            
        return self._request("POST", "createcontact", data)
    
    def get_contact(self, contact_id: str) -> Dict[str, Any]:
        """Get contact details by ID"""
        return self._request("GET", f"getcontact/{contact_id}")
    
    def get_contact_list(self) -> Dict[str, Any]:
        """Get all contacts"""
        return self._request("GET", "contactlist")
    
    def delete_contact(self, contact_id: str) -> Dict[str, Any]:
        """Delete a contact"""
        return self._request("DELETE", f"deletecontact/{contact_id}")
    
    # ========================================================================
    # DOCUMENT MANAGEMENT
    # ========================================================================
    
    def create_document(
        self,
        file_path: str,
        title: str,
        signers: List[Dict[str, Any]],
        send_in_order: bool = False,
        expiry_days: Optional[int] = None,
        folder_id: Optional[str] = None,
        prefill_widgets: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Create a document for signature
        
        Args:
            file_path: Path to PDF file or Frappe file URL
            title: Document title
            signers: List of signer configurations with widgets
            send_in_order: Whether signers should sign sequentially
            expiry_days: Days until document expires
            folder_id: Optional folder to organize document
            prefill_widgets: Pre-filled widgets (readonly values)
            
        Returns:
            Document creation response with document_id and signing URLs
            
        Example signers format:
            [
                {
                    "name": "John Doe",
                    "email": "john@example.com",
                    "widgets": [
                        {"type": "signature", "page": 1, "x": 350, "y": 600, "w": 150, "h": 50}
                    ]
                }
            ]
        """
        # Read and encode file
        file_content = self._get_file_content(file_path)
        base64_file = base64.b64encode(file_content).decode('utf-8')
        
        data = {
            "file": base64_file,
            "title": title,
            "signers": signers,
            "send_in_order": send_in_order
        }
        
        if expiry_days:
            data["expiry_days"] = expiry_days
        if folder_id:
            data["folder_id"] = folder_id
        if prefill_widgets:
            data["prefill"] = prefill_widgets
            
        return self._request("POST", "createdocument", data)
    
    def create_draft_document(
        self,
        file_path: str,
        title: str,
        signers: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Create a draft document (not sent to signers)
        
        Args:
            file_path: Path to PDF file
            title: Document title
            signers: Optional signer configurations
            
        Returns:
            Draft document details with document_id
        """
        file_content = self._get_file_content(file_path)
        base64_file = base64.b64encode(file_content).decode('utf-8')
        
        data = {
            "file": base64_file,
            "title": title
        }
        
        if signers:
            data["signers"] = signers
            
        return self._request("POST", "draftdocument", data)
    
    def create_document_from_template(
        self,
        template_id: str,
        signers: List[Dict[str, Any]],
        title: Optional[str] = None,
        prefill_widgets: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Create document from existing template
        
        Args:
            template_id: OpenSign template ID
            signers: Signer configurations (must match template roles)
            title: Optional custom title
            prefill_widgets: Pre-filled values
            
        Returns:
            Document creation response
        """
        data = {
            "template_id": template_id,
            "signers": signers
        }
        
        if title:
            data["title"] = title
        if prefill_widgets:
            data["prefill"] = prefill_widgets
            
        return self._request("POST", "createdocumentwithtemplateid", data)
    
    def get_document(self, document_id: str) -> Dict[str, Any]:
        """
        Get document details and current status
        
        Returns:
            Document details including status, signers, signed file URL
        """
        return self._request("GET", f"getdocument/{document_id}")
    
    def get_document_list(self, status: Optional[str] = None) -> Dict[str, Any]:
        """
        Get documents filtered by status
        
        Args:
            status: Filter by status (draft, in-progress, completed, declined, expired)
            
        Returns:
            List of documents
        """
        params = {"status": status} if status else None
        return self._request("GET", "getdocumentlist", params=params)
    
    def update_document(self, document_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update document properties"""
        return self._request("PUT", f"updatedocument/{document_id}", updates)
    
    def revoke_document(self, document_id: str) -> Dict[str, Any]:
        """Revoke/cancel a document"""
        return self._request("POST", f"revokedocument/{document_id}")
    
    def delete_document(self, document_id: str) -> Dict[str, Any]:
        """Permanently delete a document"""
        return self._request("DELETE", f"deletedocument/{document_id}")
    
    def resend_request_mail(self, document_id: str, signer_email: str) -> Dict[str, Any]:
        """
        Resend signature request email to a signer
        
        Args:
            document_id: OpenSign document ID
            signer_email: Email of the signer to resend to
        """
        data = {
            "document_id": document_id,
            "email": signer_email
        }
        return self._request("POST", "resendrequestmail", data)
    
    def get_signer_ips(self, document_id: str) -> Dict[str, Any]:
        """Get IP addresses of signers for audit trail"""
        return self._request("GET", f"getsignerips/{document_id}")
    
    def get_form_data(self, document_id: str) -> Dict[str, Any]:
        """Get form field data from a completed document"""
        return self._request("GET", f"getformdata/{document_id}")
    
    # ========================================================================
    # SELF SIGN
    # ========================================================================
    
    def self_sign(
        self,
        file_path: str,
        title: str,
        widgets: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Generate a self-sign URL for document owner
        
        Args:
            file_path: Path to PDF file
            title: Document title
            widgets: Optional widget configurations
            
        Returns:
            Self-sign URL that owner can use to sign directly
        """
        file_content = self._get_file_content(file_path)
        base64_file = base64.b64encode(file_content).decode('utf-8')
        
        data = {
            "file": base64_file,
            "title": title
        }
        
        if widgets:
            data["widgets"] = widgets
        else:
            data["widgets"] = [self.default_signature_widget]
            
        return self._request("POST", "selfsign", data)
    
    # ========================================================================
    # TEMPLATE MANAGEMENT
    # ========================================================================
    
    def create_template(
        self,
        file_path: str,
        title: str,
        roles: List[str],
        widgets: List[Dict[str, Any]],
        is_public: bool = False
    ) -> Dict[str, Any]:
        """
        Create a reusable template
        
        Args:
            file_path: Path to PDF file
            title: Template title
            roles: List of signer roles (e.g., ["Client", "Vendor"])
            widgets: Widget configurations with role assignments
            is_public: Whether template can be shared via public link
            
        Returns:
            Template creation response with template_id
            
        Example widgets:
            [
                {
                    "role": "Client",
                    "type": "signature",
                    "page": 1,
                    "x": 100,
                    "y": 600,
                    "w": 150,
                    "h": 50
                }
            ]
        """
        file_content = self._get_file_content(file_path)
        base64_file = base64.b64encode(file_content).decode('utf-8')
        
        data = {
            "file": base64_file,
            "title": title,
            "roles": roles,
            "widgets": widgets,
            "public": is_public
        }
        
        return self._request("POST", "createtemplate", data)
    
    def create_draft_template(
        self,
        file_path: str,
        title: str,
        roles: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create a draft template"""
        file_content = self._get_file_content(file_path)
        base64_file = base64.b64encode(file_content).decode('utf-8')
        
        data = {
            "file": base64_file,
            "title": title
        }
        
        if roles:
            data["roles"] = roles
            
        return self._request("POST", "drafttemplate", data)
    
    def get_template(self, template_id: str) -> Dict[str, Any]:
        """Get template details"""
        return self._request("GET", f"gettemplate/{template_id}")
    
    def get_template_list(self) -> Dict[str, Any]:
        """Get all templates"""
        return self._request("GET", "templatelist")
    
    def delete_template(self, template_id: str) -> Dict[str, Any]:
        """Delete a template"""
        return self._request("DELETE", f"deletetemplate/{template_id}")
    
    # ========================================================================
    # WEBHOOK MANAGEMENT
    # ========================================================================
    
    def create_webhook(self, url: str, events: List[str]) -> Dict[str, Any]:
        """
        Create webhook for document events
        
        Args:
            url: Webhook endpoint URL
            events: List of events to subscribe to
                    Options: document.completed, document.declined, 
                            document.viewed, document.signed
                            
        Returns:
            Webhook configuration details
        """
        data = {
            "url": url,
            "events": events
        }
        return self._request("POST", "createwebhook", data)
    
    def get_webhooks(self) -> Dict[str, Any]:
        """Get all configured webhooks"""
        return self._request("GET", "getwebhook")
    
    def delete_webhook(self, webhook_id: str) -> Dict[str, Any]:
        """Delete a webhook"""
        return self._request("DELETE", f"deletewebhook/{webhook_id}")
    
    # ========================================================================
    # FOLDER MANAGEMENT
    # ========================================================================
    
    def create_folder(self, name: str, parent_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a folder for organizing documents
        
        Args:
            name: Folder name
            parent_id: Optional parent folder ID for nesting
            
        Returns:
            Created folder details with folder_id
        """
        data = {"name": name}
        if parent_id:
            data["parent_id"] = parent_id
        return self._request("POST", "createfolder", data)
    
    def get_folders(self) -> Dict[str, Any]:
        """Get all folders"""
        return self._request("GET", "getfolders")
    
    def delete_folder(self, folder_id: str) -> Dict[str, Any]:
        """Delete a folder"""
        return self._request("DELETE", f"deletefolder/{folder_id}")
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _get_file_content(self, file_path: str) -> bytes:
        """
        Get file content from Frappe file or filesystem path
        
        Handles:
        - Frappe file URLs (/files/..., /private/files/...)
        - File document names
        - Direct filesystem paths
        """
        # Frappe file URL
        if file_path.startswith("/files/") or file_path.startswith("/private/files/"):
            file_doc = frappe.get_doc("File", {"file_url": file_path})
            return file_doc.get_content()
        
        # File document name
        elif frappe.db.exists("File", file_path):
            file_doc = frappe.get_doc("File", file_path)
            return file_doc.get_content()
        
        # Direct filesystem path
        elif os.path.exists(file_path):
            with open(file_path, "rb") as f:
                return f.read()
        
        else:
            frappe.throw(f"File not found: {file_path}")
    
    def build_signer_widgets(
        self,
        signer_email: str,
        signer_name: str,
        signature_page: int = 1,
        signature_x: int = 350,
        signature_y: int = 600,
        include_date: bool = True,
        include_name: bool = False,
        date_format: str = "mm/dd/yyyy"
    ) -> Dict[str, Any]:
        """
        Build a complete signer configuration with widgets
        
        Helper method to create properly formatted signer data
        
        Args:
            signer_email: Signer's email address
            signer_name: Signer's full name
            signature_page: Page number for signature
            signature_x: X coordinate for signature widget
            signature_y: Y coordinate for signature widget
            include_date: Whether to include date widget
            include_name: Whether to include name widget
            date_format: Date format string
            
        Returns:
            Complete signer configuration dict
        """
        widgets = [
            {
                "type": "signature",
                "page": signature_page,
                "x": signature_x,
                "y": signature_y,
                "w": 150,
                "h": 50,
                "options": {"hint": "Please sign here"}
            }
        ]
        
        if include_date:
            widgets.append({
                "type": "date",
                "page": signature_page,
                "x": signature_x,
                "y": signature_y - 60,
                "w": 100,
                "h": 20,
                "options": {
                    "signing_date": True,
                    "format": date_format
                }
            })
        
        if include_name:
            widgets.append({
                "type": "name",
                "page": signature_page,
                "x": signature_x,
                "y": signature_y - 90,
                "w": 150,
                "h": 20,
                "options": {
                    "hint": "Enter your full name"
                }
            })
        
        return {
            "name": signer_name,
            "email": signer_email,
            "widgets": widgets
        }


# ============================================================================
# FRAPPE EVENT HANDLERS
# ============================================================================

def on_document_insert(doc, method):
    """Handle OpenSign Document creation"""
    if doc.auto_send and doc.pdf_file:
        try:
            doc.send_for_signature()
        except Exception as e:
            frappe.log_error(f"Auto-send failed: {str(e)}", "OpenSign Integration")


def on_document_update(doc, method):
    """Handle OpenSign Document updates"""
    pass


def sync_document_statuses():
    """
    Scheduled task to sync document statuses from OpenSign
    
    Runs hourly to update status of all pending documents
    """
    client = OpenSignClient()
    
    # Get all documents that are in pending states
    pending_docs = frappe.get_all(
        "OpenSign Document",
        filters={"status": ["in", ["Sent", "In Progress", "Partially Signed"]]},
        fields=["name", "opensign_document_id"]
    )
    
    for doc_data in pending_docs:
        if not doc_data.opensign_document_id:
            continue
            
        try:
            result = client.get_document(doc_data.opensign_document_id)
            doc = frappe.get_doc("OpenSign Document", doc_data.name)
            
            new_status = result.get("status", "").capitalize()
            if new_status and new_status != doc.status:
                doc.status = new_status
                
                # Download signed document if completed
                if new_status == "Completed" and result.get("signed_file_url"):
                    doc.download_signed_document(result)
                
                doc.save(ignore_permissions=True)
                
        except Exception as e:
            frappe.log_error(
                f"Failed to sync document {doc_data.name}: {str(e)}",
                "OpenSign Sync Error"
            )
    
    frappe.db.commit()


def get_signing_url(document_id: str) -> Optional[str]:
    """
    Jinja helper to get signing URL for a document
    
    Usage in templates:
        {{ get_signing_url(doc.opensign_document_id) }}
    """
    client = OpenSignClient()
    try:
        result = client.get_document(document_id)
        return result.get("signing_url")
    except:
        return None


# ============================================================================
# FRAPPE WHITELISTED API METHODS
# ============================================================================

@frappe.whitelist()
def get_opensign_user():
    """Get OpenSign account details - API endpoint"""
    client = OpenSignClient()
    return client.get_user()


@frappe.whitelist()
def get_api_credits():
    """Get remaining API credits - API endpoint"""
    client = OpenSignClient()
    return client.get_api_credits()


@frappe.whitelist()
def create_contact(name: str, email: str, phone: Optional[str] = None):
    """Create a signer contact - API endpoint"""
    client = OpenSignClient()
    return client.create_contact(name, email, phone)


@frappe.whitelist()
def send_document_for_signature(
    doctype: str,
    docname: str,
    signers: Union[str, List],
    title: Optional[str] = None,
    send_in_order: bool = False,
    expiry_days: Optional[int] = None
):
    """
    Send any Frappe document's PDF for signature
    
    Args:
        doctype: Source DocType
        docname: Document name
        signers: JSON string or list of signer configurations
        title: Optional custom title
        send_in_order: Sequential signing
        expiry_days: Document expiry
        
    Returns:
        OpenSign API response and created tracking document
    """
    # Parse signers if JSON string
    if isinstance(signers, str):
        signers_list = json.loads(signers)
    else:
        signers_list = signers
    
    # Generate PDF from Frappe document
    pdf_content = frappe.get_print(
        doctype, docname, 
        print_format=frappe.db.get_value(doctype, docname, "default_print_format") or "Standard",
        as_pdf=True
    )
    
    # Save to temp file
    import tempfile
    temp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    temp_file.write(pdf_content)
    temp_file.close()
    temp_path = temp_file.name
    
    try:
        # Build formatted signers with widgets
        client = OpenSignClient()
        formatted_signers = []
        y_offset = 600
        
        for signer in signers_list:
            formatted_signers.append(
                client.build_signer_widgets(
                    signer_email=signer.get("email"),
                    signer_name=signer.get("name"),
                    signature_y=y_offset,
                    include_date=signer.get("include_date", True)
                )
            )
            y_offset -= 100  # Stack signatures vertically
        
        # Send to OpenSign
        result = client.create_document(
            file_path=temp_path,
            title=title or f"{doctype} - {docname}",
            signers=formatted_signers,
            send_in_order=send_in_order,
            expiry_days=expiry_days
        )
        
        # Create tracking record
        tracking_doc = frappe.get_doc({
            "doctype": "OpenSign Document",
            "document_title": title or f"{doctype} - {docname}",
            "linked_doctype": doctype,
            "linked_document": docname,
            "opensign_document_id": result.get("document_id"),
            "status": "Sent",
            "send_in_order": send_in_order,
            "expiry_days": expiry_days
        })
        
        # Add signers to child table
        for signer in signers_list:
            tracking_doc.append("signers", {
                "signer_name": signer.get("name"),
                "email": signer.get("email"),
                "status": "Pending"
            })
        
        tracking_doc.insert()
        
        return {
            "success": True,
            "document_id": result.get("document_id"),
            "tracking_document": tracking_doc.name,
            "message": "Document sent for signature successfully"
        }
        
    finally:
        # Clean up temp file
        os.unlink(temp_path)


@frappe.whitelist()
def check_document_status(document_id: str):
    """Check status of a document - API endpoint"""
    client = OpenSignClient()
    return client.get_document(document_id)


@frappe.whitelist()
def create_signature_template(
    file_url: str,
    title: str,
    roles: Union[str, List],
    is_public: bool = False
):
    """
    Create a reusable signature template
    
    Args:
        file_url: Frappe file URL
        title: Template title
        roles: JSON string or list of role names
        is_public: Whether template is publicly shareable
    """
    if isinstance(roles, str):
        roles_list = json.loads(roles)
    else:
        roles_list = roles
    
    # Build default widgets for each role
    widgets = []
    for idx, role in enumerate(roles_list):
        widgets.append({
            "role": role,
            "type": "signature",
            "page": 1,
            "x": 100,
            "y": 600 - (idx * 100),
            "w": 150,
            "h": 50,
            "options": {"hint": f"Signature for {role}"}
        })
        widgets.append({
            "role": role,
            "type": "date",
            "page": 1,
            "x": 100,
            "y": 540 - (idx * 100),
            "w": 100,
            "h": 20,
            "options": {"signing_date": True, "format": "mm/dd/yyyy"}
        })
    
    client = OpenSignClient()
    result = client.create_template(
        file_path=file_url,
        title=title,
        roles=roles_list,
        widgets=widgets,
        is_public=is_public
    )
    
    # Create tracking record
    template_doc = frappe.get_doc({
        "doctype": "OpenSign Template",
        "template_title": title,
        "opensign_template_id": result.get("template_id"),
        "is_public": is_public,
        "roles": json.dumps(roles_list)
    })
    template_doc.insert()
    
    return {
        "success": True,
        "template_id": result.get("template_id"),
        "tracking_document": template_doc.name
    }


@frappe.whitelist()
def self_sign_document(file_url: str, title: str):
    """Generate self-sign URL - API endpoint"""
    client = OpenSignClient()
    return client.self_sign(file_path=file_url, title=title)


@frappe.whitelist()
def resend_signature_request(document_name: str, signer_email: str):
    """Resend signature request to a signer"""
    doc = frappe.get_doc("OpenSign Document", document_name)
    if not doc.opensign_document_id:
        frappe.throw("Document not yet sent to OpenSign")
    
    client = OpenSignClient()
    result = client.resend_request_mail(doc.opensign_document_id, signer_email)
    
    return {"success": True, "message": f"Request resent to {signer_email}"}


@frappe.whitelist()
def revoke_document(document_name: str):
    """Revoke/cancel a document"""
    doc = frappe.get_doc("OpenSign Document", document_name)
    if not doc.opensign_document_id:
        frappe.throw("Document not yet sent to OpenSign")
    
    client = OpenSignClient()
    client.revoke_document(doc.opensign_document_id)
    
    doc.status = "Revoked"
    doc.save()
    
    return {"success": True, "message": "Document revoked successfully"}


@frappe.whitelist()
def setup_webhook(site_url: Optional[str] = None):
    """
    Configure OpenSign webhook for this Frappe site
    
    Args:
        site_url: Base URL of the site (auto-detected if not provided)
    """
    if not site_url:
        site_url = frappe.utils.get_url()
    
    webhook_url = f"{site_url}/api/method/opensign_integration.www.opensign_webhook.handle_webhook"
    
    client = OpenSignClient()
    result = client.create_webhook(
        url=webhook_url,
        events=["document.completed", "document.declined", "document.viewed", "document.signed"]
    )
    
    # Save webhook ID to settings
    settings = frappe.get_single("OpenSign Settings")
    settings.webhook_id = result.get("webhook_id")
    settings.webhook_url = webhook_url
    settings.save()
    
    return {
        "success": True,
        "webhook_id": result.get("webhook_id"),
        "webhook_url": webhook_url
    }
