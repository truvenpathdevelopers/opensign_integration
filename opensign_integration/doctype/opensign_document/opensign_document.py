"""
OpenSign Document DocType
=========================

Main DocType for tracking documents sent for digital signature.
Handles sending, status tracking, and downloading signed documents.
"""

import frappe
from frappe.model.document import Document
from frappe import _
from frappe.utils import now_datetime, add_days, getdate
import requests
import json


class OpenSignDocument(Document):
    def validate(self):
        """Validate document before saving"""
        if not self.signers and not self.template_id:
            frappe.throw(_("Please add at least one signer or specify a template"))
        
        # Set default expiry days from settings
        if not self.expiry_days:
            settings = frappe.get_single("OpenSign Settings")
            self.expiry_days = settings.default_expiry_days or 30
    
    def after_insert(self):
        """Handle post-creation actions"""
        self.add_activity("Created", details="Document created in Frappe")
        
        if self.auto_send and self.pdf_file:
            self.send_for_signature()
    
    def add_activity(self, event, signer_email=None, ip_address=None, details=None):
        """Add an activity log entry"""
        self.append("activity_log", {
            "event": event,
            "signer_email": signer_email,
            "timestamp": now_datetime(),
            "ip_address": ip_address,
            "details": details
        })
    
    @frappe.whitelist()
    def send_for_signature(self):
        """
        Send document to OpenSign for signatures
        
        Creates the document in OpenSign and updates local record with
        document ID and signing URL.
        """
        if not self.pdf_file and not self.linked_document:
            frappe.throw(_("Please upload a PDF file or link a document"))
        
        if self.opensign_document_id:
            frappe.throw(_("Document has already been sent to OpenSign"))
        
        from opensign_integration.utils.opensign_client import OpenSignClient
        client = OpenSignClient()
        
        # Get PDF content
        if self.pdf_file:
            file_path = self.pdf_file
        elif self.linked_document:
            # Generate PDF from linked document
            file_path = self._generate_pdf_from_linked_doc()
        else:
            frappe.throw(_("No PDF source available"))
        
        # Build signers list with widgets
        signers = self._build_signers_list()
        
        # Check if using template
        if self.template_id:
            result = client.create_document_from_template(
                template_id=self.template_id,
                signers=signers,
                title=self.document_title
            )
        else:
            result = client.create_document(
                file_path=file_path,
                title=self.document_title,
                signers=signers,
                send_in_order=self.send_in_order,
                expiry_days=self.expiry_days,
                folder_id=self.folder_id
            )
        
        # Update document with OpenSign response
        self.opensign_document_id = result.get("document_id")
        self.status = "Sent"
        self.signing_url = result.get("signing_url")
        self.sent_at = now_datetime()
        
        if self.expiry_days:
            self.expires_at = add_days(getdate(), self.expiry_days)
        
        self.add_activity("Sent", details=f"Document ID: {self.opensign_document_id}")
        self.save()
        
        frappe.msgprint(
            _("Document sent for signature successfully!<br>Document ID: {0}").format(
                self.opensign_document_id
            ),
            indicator="green"
        )
        
        return result
    
    def _build_signers_list(self):
        """Build signers list with widget configurations"""
        signers = []
        
        for signer in self.signers:
            signer_data = {
                "name": signer.signer_name,
                "email": signer.email,
                "widgets": []
            }
            
            # Add role if specified (for template-based signing)
            if signer.role:
                signer_data["role"] = signer.role
            
            # Add signature widget
            signer_data["widgets"].append({
                "type": "signature",
                "page": signer.signature_page or 1,
                "x": signer.signature_x or 350,
                "y": signer.signature_y or 600,
                "w": signer.signature_width or 150,
                "h": signer.signature_height or 50,
                "options": {"hint": "Please sign here"}
            })
            
            # Add date widget if requested
            if signer.include_date:
                signer_data["widgets"].append({
                    "type": "date",
                    "page": signer.signature_page or 1,
                    "x": signer.date_x or 350,
                    "y": signer.date_y or 540,
                    "w": 100,
                    "h": 20,
                    "options": {
                        "signing_date": True,
                        "format": frappe.get_single("OpenSign Settings").date_format or "mm/dd/yyyy"
                    }
                })
            
            signers.append(signer_data)
        
        return signers
    
    def _generate_pdf_from_linked_doc(self):
        """Generate PDF from linked Frappe document"""
        import tempfile
        
        pdf_content = frappe.get_print(
            self.linked_doctype,
            self.linked_document,
            print_format=frappe.db.get_value(
                self.linked_doctype, 
                self.linked_document, 
                "default_print_format"
            ) or "Standard",
            as_pdf=True
        )
        
        # Save to temp file and return path
        temp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        temp_file.write(pdf_content)
        temp_file.close()
        
        return temp_file.name
    
    @frappe.whitelist()
    def check_status(self):
        """
        Check and update document status from OpenSign
        
        Fetches current status and updates local record.
        Downloads signed PDF if document is completed.
        """
        if not self.opensign_document_id:
            frappe.throw(_("Document not yet sent to OpenSign"))
        
        from opensign_integration.utils.opensign_client import OpenSignClient
        client = OpenSignClient()
        
        result = client.get_document(self.opensign_document_id)
        
        old_status = self.status
        new_status = self._map_opensign_status(result.get("status", ""))
        
        if new_status != old_status:
            self.status = new_status
            self.add_activity(new_status, details="Status updated from OpenSign")
        
        # Update signer statuses
        self._update_signer_statuses(result.get("signers", []))
        
        # Download signed document if completed
        if self.status == "Completed":
            self.completed_at = now_datetime()
            self.download_signed_document(result)
        
        self.save()
        
        frappe.msgprint(_("Status: {0}").format(self.status))
        
        return result
    
    def _map_opensign_status(self, opensign_status):
        """Map OpenSign status to local status"""
        status_map = {
            "draft": "Draft",
            "in-progress": "In Progress",
            "completed": "Completed",
            "declined": "Declined",
            "expired": "Expired",
            "revoked": "Revoked"
        }
        return status_map.get(opensign_status.lower(), "In Progress")
    
    def _update_signer_statuses(self, opensign_signers):
        """Update local signer records with OpenSign data"""
        for os_signer in opensign_signers:
            for local_signer in self.signers:
                if local_signer.email == os_signer.get("email"):
                    local_signer.status = os_signer.get("status", "Pending").capitalize()
                    if os_signer.get("signed_at"):
                        local_signer.signed_at = os_signer.get("signed_at")
                    if os_signer.get("ip"):
                        local_signer.ip_address = os_signer.get("ip")
                    break
    
    def download_signed_document(self, doc_data):
        """
        Download and attach the signed PDF and completion certificate
        
        Args:
            doc_data: Document data from OpenSign API
        """
        # Download signed PDF
        if doc_data.get("signed_file_url"):
            try:
                response = requests.get(doc_data["signed_file_url"], timeout=60)
                response.raise_for_status()
                
                file_doc = frappe.get_doc({
                    "doctype": "File",
                    "file_name": f"signed_{self.document_title}.pdf",
                    "attached_to_doctype": self.doctype,
                    "attached_to_name": self.name,
                    "content": response.content,
                    "is_private": 1
                })
                file_doc.save()
                
                self.signed_pdf = file_doc.file_url
                
            except Exception as e:
                frappe.log_error(f"Failed to download signed PDF: {str(e)}")
        
        # Download completion certificate
        if doc_data.get("certificate_url"):
            try:
                response = requests.get(doc_data["certificate_url"], timeout=60)
                response.raise_for_status()
                
                file_doc = frappe.get_doc({
                    "doctype": "File",
                    "file_name": f"certificate_{self.document_title}.pdf",
                    "attached_to_doctype": self.doctype,
                    "attached_to_name": self.name,
                    "content": response.content,
                    "is_private": 1
                })
                file_doc.save()
                
                self.completion_certificate = file_doc.file_url
                
            except Exception as e:
                frappe.log_error(f"Failed to download certificate: {str(e)}")
    
    @frappe.whitelist()
    def resend_to_signer(self, email):
        """
        Resend signature request to a specific signer
        
        Args:
            email: Email address of the signer
        """
        if not self.opensign_document_id:
            frappe.throw(_("Document not yet sent to OpenSign"))
        
        from opensign_integration.utils.opensign_client import OpenSignClient
        client = OpenSignClient()
        
        client.resend_request_mail(self.opensign_document_id, email)
        
        self.add_activity("Resent", signer_email=email, details="Signature request resent")
        self.save()
        
        frappe.msgprint(_("Signature request resent to {0}").format(email))
    
    @frappe.whitelist()
    def revoke(self):
        """Revoke/cancel the document"""
        if not self.opensign_document_id:
            frappe.throw(_("Document not yet sent to OpenSign"))
        
        if self.status in ["Completed", "Revoked"]:
            frappe.throw(_("Cannot revoke a {0} document").format(self.status.lower()))
        
        from opensign_integration.utils.opensign_client import OpenSignClient
        client = OpenSignClient()
        
        client.revoke_document(self.opensign_document_id)
        
        self.status = "Revoked"
        self.add_activity("Revoked", details="Document revoked by user")
        self.save()
        
        frappe.msgprint(_("Document revoked successfully"))
    
    @frappe.whitelist()
    def get_signing_link(self, signer_email=None):
        """
        Get signing link for the document
        
        Args:
            signer_email: Optional specific signer email
            
        Returns:
            Signing URL
        """
        if not self.opensign_document_id:
            frappe.throw(_("Document not yet sent to OpenSign"))
        
        from opensign_integration.utils.opensign_client import OpenSignClient
        client = OpenSignClient()
        
        result = client.get_document(self.opensign_document_id)
        
        # Return specific signer's link if requested
        if signer_email:
            for signer in result.get("signers", []):
                if signer.get("email") == signer_email:
                    return signer.get("signing_url", self.signing_url)
        
        return result.get("signing_url", self.signing_url)
    
    @frappe.whitelist()
    def get_audit_trail(self):
        """Get detailed audit trail from OpenSign"""
        if not self.opensign_document_id:
            frappe.throw(_("Document not yet sent to OpenSign"))
        
        from opensign_integration.utils.opensign_client import OpenSignClient
        client = OpenSignClient()
        
        # Get signer IPs for audit
        ips = client.get_signer_ips(self.opensign_document_id)
        
        # Get form data if available
        try:
            form_data = client.get_form_data(self.opensign_document_id)
        except:
            form_data = {}
        
        return {
            "signer_ips": ips,
            "form_data": form_data,
            "activity_log": [
                {
                    "event": log.event,
                    "signer_email": log.signer_email,
                    "timestamp": str(log.timestamp),
                    "ip_address": log.ip_address,
                    "details": log.details
                }
                for log in self.activity_log
            ]
        }
