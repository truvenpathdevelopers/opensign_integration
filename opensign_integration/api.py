"""
OpenSign Template API
=====================

Additional API methods for template-based document generation.
"""

import frappe
import json
from typing import List, Dict, Any, Optional, Union


@frappe.whitelist()
def create_document_from_template(
    template_id: str,
    signers: Union[str, List[Dict]],
    title: Optional[str] = None,
    prefill: Optional[Union[str, List[Dict]]] = None
):
    """
    Create a document from an OpenSign template
    
    Args:
        template_id: OpenSign template ID
        signers: List of signer configurations with role assignments
        title: Optional custom document title
        prefill: Optional prefill widget values
        
    Returns:
        Document creation result with tracking document
        
    Example signers:
        [
            {"name": "John Doe", "email": "john@example.com", "role": "Client"},
            {"name": "Jane Smith", "email": "jane@example.com", "role": "Vendor"}
        ]
    """
    from opensign_integration.utils.opensign_client import OpenSignClient
    
    # Parse JSON strings if needed
    if isinstance(signers, str):
        signers = json.loads(signers)
    if isinstance(prefill, str):
        prefill = json.loads(prefill)
    
    client = OpenSignClient()
    
    # Create document from template
    result = client.create_document_from_template(
        template_id=template_id,
        signers=signers,
        title=title,
        prefill_widgets=prefill
    )
    
    # Find the local template record if it exists
    template_doc = frappe.get_all(
        "OpenSign Template",
        filters={"opensign_template_id": template_id},
        limit=1
    )
    
    # Create tracking document
    doc = frappe.get_doc({
        "doctype": "OpenSign Document",
        "document_title": title or f"Document from Template {template_id}",
        "template_id": template_id,
        "opensign_document_id": result.get("document_id"),
        "status": "Sent",
        "sent_at": frappe.utils.now_datetime()
    })
    
    # Add signers
    for signer in signers:
        doc.append("signers", {
            "signer_name": signer.get("name"),
            "email": signer.get("email"),
            "role": signer.get("role"),
            "status": "Pending"
        })
    
    doc.insert()
    
    # Update template usage stats
    if template_doc:
        frappe.db.set_value(
            "OpenSign Template",
            template_doc[0].name,
            {
                "documents_created": frappe.db.get_value(
                    "OpenSign Template", template_doc[0].name, "documents_created"
                ) + 1,
                "last_used": frappe.utils.now_datetime()
            }
        )
    
    return {
        "success": True,
        "document_id": result.get("document_id"),
        "tracking_document": doc.name,
        "signing_url": result.get("signing_url")
    }


@frappe.whitelist()
def get_template_roles(template_name: str):
    """
    Get roles defined in a template
    
    Args:
        template_name: OpenSign Template document name
        
    Returns:
        List of role names
    """
    template = frappe.get_doc("OpenSign Template", template_name)
    
    if template.roles:
        try:
            return json.loads(template.roles)
        except:
            return []
    
    return []


@frappe.whitelist()
def get_templates_list():
    """
    Get list of available templates with their details
    
    Returns:
        List of template summaries
    """
    templates = frappe.get_all(
        "OpenSign Template",
        filters={"opensign_template_id": ["!=", ""]},
        fields=[
            "name", "template_title", "opensign_template_id",
            "is_public", "roles", "documents_created", "last_used"
        ]
    )
    
    # Parse roles JSON
    for template in templates:
        try:
            template["roles_list"] = json.loads(template.get("roles") or "[]")
        except:
            template["roles_list"] = []
    
    return templates


@frappe.whitelist()
def create_template_from_document(
    document_name: str,
    template_title: str,
    roles: Union[str, List[str]],
    is_public: bool = False
):
    """
    Create a template from an existing OpenSign Document
    
    Args:
        document_name: OpenSign Document name
        template_title: Title for the new template
        roles: List of role names
        is_public: Whether template is publicly shareable
        
    Returns:
        Created template details
    """
    from opensign_integration.utils.opensign_client import OpenSignClient
    
    # Parse roles if string
    if isinstance(roles, str):
        roles = json.loads(roles)
    
    # Get the source document
    source_doc = frappe.get_doc("OpenSign Document", document_name)
    
    if not source_doc.pdf_file:
        frappe.throw("Source document must have a PDF file attached")
    
    # Build widgets from signers
    widgets = []
    for signer in source_doc.signers:
        # Map signer to role (use signer name as role if not specified)
        role = signer.role or signer.signer_name
        
        widgets.append({
            "role": role,
            "type": "signature",
            "page": signer.signature_page or 1,
            "x": signer.signature_x or 350,
            "y": signer.signature_y or 600,
            "w": signer.signature_width or 150,
            "h": signer.signature_height or 50
        })
        
        if signer.include_date:
            widgets.append({
                "role": role,
                "type": "date",
                "page": signer.signature_page or 1,
                "x": signer.date_x or 350,
                "y": signer.date_y or 540,
                "w": 100,
                "h": 20,
                "options": {"signing_date": True}
            })
    
    # Create template in OpenSign
    client = OpenSignClient()
    result = client.create_template(
        file_path=source_doc.pdf_file,
        title=template_title,
        roles=roles,
        widgets=widgets,
        is_public=is_public
    )
    
    # Create local template record
    template_doc = frappe.get_doc({
        "doctype": "OpenSign Template",
        "template_title": template_title,
        "opensign_template_id": result.get("template_id"),
        "is_public": is_public,
        "roles": json.dumps(roles),
        "widgets_config": json.dumps(widgets, indent=2)
    })
    template_doc.insert()
    
    return {
        "success": True,
        "template_id": result.get("template_id"),
        "template_document": template_doc.name
    }


@frappe.whitelist()
def bulk_create_from_template(
    template_id: str,
    signers_list: Union[str, List[List[Dict]]],
    title_prefix: Optional[str] = None
):
    """
    Create multiple documents from a template (bulk operation)
    
    Args:
        template_id: OpenSign template ID
        signers_list: List of signer lists (one per document)
        title_prefix: Prefix for document titles
        
    Returns:
        List of created document results
        
    Example signers_list:
        [
            [{"name": "John", "email": "john@a.com", "role": "Client"}],
            [{"name": "Jane", "email": "jane@b.com", "role": "Client"}],
            [{"name": "Bob", "email": "bob@c.com", "role": "Client"}]
        ]
    """
    if isinstance(signers_list, str):
        signers_list = json.loads(signers_list)
    
    results = []
    
    for idx, signers in enumerate(signers_list):
        title = f"{title_prefix or 'Document'} #{idx + 1}"
        
        try:
            result = create_document_from_template(
                template_id=template_id,
                signers=signers,
                title=title
            )
            results.append({
                "index": idx,
                "success": True,
                "document_id": result.get("document_id"),
                "tracking_document": result.get("tracking_document")
            })
        except Exception as e:
            results.append({
                "index": idx,
                "success": False,
                "error": str(e)
            })
    
    return {
        "total": len(signers_list),
        "successful": len([r for r in results if r["success"]]),
        "failed": len([r for r in results if not r["success"]]),
        "results": results
    }


@frappe.whitelist()
def preview_template(template_name: str):
    """
    Get preview information for a template
    
    Args:
        template_name: OpenSign Template document name
        
    Returns:
        Template details including widget positions
    """
    template = frappe.get_doc("OpenSign Template", template_name)
    
    # Parse configurations
    roles = []
    widgets = []
    
    try:
        roles = json.loads(template.roles or "[]")
    except:
        pass
    
    try:
        widgets = json.loads(template.widgets_config or "[]")
    except:
        pass
    
    return {
        "name": template.name,
        "title": template.template_title,
        "opensign_id": template.opensign_template_id,
        "is_public": template.is_public,
        "public_url": template.public_url,
        "roles": roles,
        "widgets": widgets,
        "usage": {
            "documents_created": template.documents_created,
            "last_used": template.last_used
        }
    }
