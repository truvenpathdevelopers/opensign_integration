"""
OpenSign Webhook Handler
========================

Handles incoming webhook events from OpenSign for document status updates.

Endpoint: /api/method/opensign_integration.www.opensign_webhook.handle_webhook
"""

import frappe
import json
from frappe import _


@frappe.whitelist(allow_guest=True)
def handle_webhook():
    """
    Handle OpenSign webhook callbacks
    
    Processes events like document.completed, document.declined, etc.
    Updates local OpenSign Document records accordingly.
    """
    try:
        # Parse webhook payload
        if frappe.request.data:
            data = json.loads(frappe.request.data)
        else:
            return {"status": "error", "message": "No data received"}
        
        # Log webhook for debugging
        frappe.log_error(
            title="OpenSign Webhook Received",
            message=json.dumps(data, indent=2)
        )
        
        event = data.get("event")
        document_id = data.get("document_id")
        
        if not event or not document_id:
            return {"status": "error", "message": "Missing event or document_id"}
        
        # Find matching local document
        docs = frappe.get_all(
            "OpenSign Document",
            filters={"opensign_document_id": document_id},
            limit=1
        )
        
        if not docs:
            frappe.log_error(
                f"OpenSign webhook: Document not found - {document_id}",
                "OpenSign Integration"
            )
            return {"status": "not_found", "message": f"Document {document_id} not found"}
        
        doc = frappe.get_doc("OpenSign Document", docs[0].name)
        
        # Process event
        if event == "document.completed":
            handle_document_completed(doc, data)
        elif event == "document.declined":
            handle_document_declined(doc, data)
        elif event == "document.viewed":
            handle_document_viewed(doc, data)
        elif event == "document.signed":
            handle_document_signed(doc, data)
        elif event == "document.expired":
            handle_document_expired(doc, data)
        else:
            # Log unknown event
            frappe.log_error(
                f"Unknown OpenSign event: {event}",
                "OpenSign Integration"
            )
        
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        
        return {"status": "success", "event": event}
        
    except Exception as e:
        frappe.log_error(
            f"OpenSign webhook error: {str(e)}",
            "OpenSign Integration"
        )
        return {"status": "error", "message": str(e)}


def handle_document_completed(doc, data):
    """Handle document.completed event"""
    doc.status = "Completed"
    doc.completed_at = frappe.utils.now_datetime()
    
    doc.add_activity(
        "Completed",
        details="All signers have signed the document"
    )
    
    # Try to download signed document
    try:
        from opensign_integration.utils.opensign_client import OpenSignClient
        client = OpenSignClient()
        result = client.get_document(doc.opensign_document_id)
        doc.download_signed_document(result)
    except Exception as e:
        frappe.log_error(f"Failed to download signed doc: {str(e)}")
    
    # Update all signers to signed
    for signer in doc.signers:
        if signer.status == "Pending":
            signer.status = "Signed"
    
    # Send notification
    send_completion_notification(doc)
    
    # Trigger realtime event
    frappe.publish_realtime(
        "opensign_completed",
        {
            "document": doc.name,
            "title": doc.document_title,
            "linked_doctype": doc.linked_doctype,
            "linked_document": doc.linked_document
        },
        user=doc.owner
    )


def handle_document_declined(doc, data):
    """Handle document.declined event"""
    doc.status = "Declined"
    
    signer_email = data.get("signer_email", "Unknown")
    reason = data.get("reason", "No reason provided")
    
    doc.decline_reason = f"Declined by {signer_email}: {reason}"
    
    doc.add_activity(
        "Declined",
        signer_email=signer_email,
        details=reason
    )
    
    # Update signer status
    for signer in doc.signers:
        if signer.email == signer_email:
            signer.status = "Declined"
            break
    
    # Send notification
    send_decline_notification(doc, signer_email, reason)


def handle_document_viewed(doc, data):
    """Handle document.viewed event"""
    signer_email = data.get("signer_email", "Unknown")
    ip_address = data.get("ip", "")
    
    doc.add_activity(
        "Viewed",
        signer_email=signer_email,
        ip_address=ip_address,
        details="Document viewed by signer"
    )
    
    # Update signer status to viewed if still pending
    for signer in doc.signers:
        if signer.email == signer_email and signer.status == "Pending":
            signer.status = "Viewed"
            break


def handle_document_signed(doc, data):
    """Handle document.signed event (individual signer signed)"""
    signer_email = data.get("signer_email", "Unknown")
    ip_address = data.get("ip", "")
    
    doc.add_activity(
        "Signed",
        signer_email=signer_email,
        ip_address=ip_address,
        details="Signer completed their signature"
    )
    
    # Update signer status
    for signer in doc.signers:
        if signer.email == signer_email:
            signer.status = "Signed"
            signer.signed_at = frappe.utils.now_datetime()
            signer.ip_address = ip_address
            break
    
    # Check if all signers have signed
    all_signed = all(s.status == "Signed" for s in doc.signers)
    some_signed = any(s.status == "Signed" for s in doc.signers)
    
    if all_signed:
        doc.status = "Completed"
    elif some_signed:
        doc.status = "Partially Signed"
    else:
        doc.status = "In Progress"


def handle_document_expired(doc, data):
    """Handle document.expired event"""
    doc.status = "Expired"
    
    doc.add_activity(
        "Expired",
        details="Document has expired without all signatures"
    )


def send_completion_notification(doc):
    """Send email notification when document is completed"""
    try:
        if doc.owner:
            frappe.sendmail(
                recipients=[doc.owner],
                subject=_("Document Signed: {0}").format(doc.document_title),
                message=_("""
                    <p>Good news! Your document <strong>{0}</strong> has been signed by all parties.</p>
                    <p>You can view and download the signed document from the OpenSign Document record.</p>
                    <p><a href="{1}">View Document</a></p>
                """).format(
                    doc.document_title,
                    frappe.utils.get_url_to_form("OpenSign Document", doc.name)
                ),
                delayed=False
            )
    except Exception as e:
        frappe.log_error(f"Failed to send completion notification: {str(e)}")


def send_decline_notification(doc, signer_email, reason):
    """Send email notification when document is declined"""
    try:
        if doc.owner:
            frappe.sendmail(
                recipients=[doc.owner],
                subject=_("Document Declined: {0}").format(doc.document_title),
                message=_("""
                    <p>Your document <strong>{0}</strong> has been declined.</p>
                    <p><strong>Declined by:</strong> {1}</p>
                    <p><strong>Reason:</strong> {2}</p>
                    <p><a href="{3}">View Document</a></p>
                """).format(
                    doc.document_title,
                    signer_email,
                    reason,
                    frappe.utils.get_url_to_form("OpenSign Document", doc.name)
                ),
                delayed=False
            )
    except Exception as e:
        frappe.log_error(f"Failed to send decline notification: {str(e)}")
