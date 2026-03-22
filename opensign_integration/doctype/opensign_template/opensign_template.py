"""
OpenSign Template DocType
=========================

Stores reusable signature templates for document generation.
"""

import frappe
from frappe.model.document import Document
from frappe import _
import json


class OpenSignTemplate(Document):
    def validate(self):
        """Validate template configuration"""
        if self.roles:
            try:
                roles = json.loads(self.roles)
                if not isinstance(roles, list):
                    frappe.throw(_("Roles must be a JSON array"))
            except json.JSONDecodeError:
                frappe.throw(_("Invalid JSON in Roles field"))
    
    @frappe.whitelist()
    def create_in_opensign(self):
        """Create or update template in OpenSign"""
        if not self.template_file:
            frappe.throw(_("Please upload a template PDF file"))
        
        if not self.roles:
            frappe.throw(_("Please specify roles"))
        
        from opensign_integration.utils.opensign_client import OpenSignClient
        client = OpenSignClient()
        
        roles = json.loads(self.roles)
        
        # Parse or generate widgets config
        if self.widgets_config:
            widgets = json.loads(self.widgets_config)
        else:
            # Generate default widgets for each role
            widgets = self._generate_default_widgets(roles)
            self.widgets_config = json.dumps(widgets, indent=2)
        
        result = client.create_template(
            file_path=self.template_file,
            title=self.template_title,
            roles=roles,
            widgets=widgets,
            is_public=self.is_public
        )
        
        self.opensign_template_id = result.get("template_id")
        if self.is_public and result.get("public_url"):
            self.public_url = result.get("public_url")
        
        self.save()
        
        frappe.msgprint(_("Template created in OpenSign. ID: {0}").format(self.opensign_template_id))
        
        return result
    
    def _generate_default_widgets(self, roles):
        """Generate default widget configuration for roles"""
        widgets = []
        y_offset = 600
        
        for role in roles:
            # Signature widget
            widgets.append({
                "role": role,
                "type": "signature",
                "page": 1,
                "x": 100,
                "y": y_offset,
                "w": 150,
                "h": 50,
                "options": {"hint": f"Signature for {role}"}
            })
            
            # Date widget
            widgets.append({
                "role": role,
                "type": "date",
                "page": 1,
                "x": 100,
                "y": y_offset - 60,
                "w": 100,
                "h": 20,
                "options": {"signing_date": True, "format": "mm/dd/yyyy"}
            })
            
            y_offset -= 120
        
        return widgets
    
    @frappe.whitelist()
    def create_document(self, signers):
        """
        Create a document from this template
        
        Args:
            signers: List of signer configurations matching template roles
        """
        if not self.opensign_template_id:
            frappe.throw(_("Template not yet created in OpenSign. Please create it first."))
        
        if isinstance(signers, str):
            signers = json.loads(signers)
        
        from opensign_integration.utils.opensign_client import OpenSignClient
        client = OpenSignClient()
        
        result = client.create_document_from_template(
            template_id=self.opensign_template_id,
            signers=signers,
            title=f"{self.template_title} - {frappe.utils.now()}"
        )
        
        # Update usage stats
        self.documents_created = (self.documents_created or 0) + 1
        self.last_used = frappe.utils.now_datetime()
        self.save()
        
        # Create tracking document
        doc = frappe.get_doc({
            "doctype": "OpenSign Document",
            "document_title": f"{self.template_title} - Document",
            "template_id": self.opensign_template_id,
            "opensign_document_id": result.get("document_id"),
            "status": "Sent"
        })
        
        for signer in signers:
            doc.append("signers", {
                "signer_name": signer.get("name"),
                "email": signer.get("email"),
                "role": signer.get("role"),
                "status": "Pending"
            })
        
        doc.insert()
        
        return {
            "success": True,
            "document_id": result.get("document_id"),
            "tracking_document": doc.name
        }
    
    @frappe.whitelist()
    def sync_from_opensign(self):
        """Sync template details from OpenSign"""
        if not self.opensign_template_id:
            frappe.throw(_("No OpenSign Template ID"))
        
        from opensign_integration.utils.opensign_client import OpenSignClient
        client = OpenSignClient()
        
        result = client.get_template(self.opensign_template_id)
        
        # Update local record with OpenSign data
        if result.get("title"):
            self.template_title = result.get("title")
        if result.get("roles"):
            self.roles = json.dumps(result.get("roles"))
        if result.get("public_url"):
            self.public_url = result.get("public_url")
        
        self.save()
        
        frappe.msgprint(_("Template synced from OpenSign"))
        
        return result
