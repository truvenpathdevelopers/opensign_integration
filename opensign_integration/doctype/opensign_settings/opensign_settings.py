"""
OpenSign Settings DocType
=========================

Single DocType for storing OpenSign API configuration.
"""

import frappe
from frappe.model.document import Document


class OpenSignSettings(Document):
    def validate(self):
        """Validate settings before saving"""
        if self.api_token:
            self.verify_credentials()
    
    def verify_credentials(self):
        """Verify API credentials by fetching user info"""
        try:
            from opensign_integration.utils.opensign_client import OpenSignClient
            client = OpenSignClient()
            
            # Get user info
            user_info = client.get_user()
            self.account_email = user_info.get("email", "")
            self.account_name = user_info.get("name", "")
            
            # Get credits
            try:
                credits_info = client.get_api_credits()
                self.api_credits = credits_info.get("credits", 0)
            except:
                pass
                
        except Exception as e:
            frappe.log_error(f"Failed to verify OpenSign credentials: {str(e)}")
    
    @frappe.whitelist()
    def setup_webhook(self):
        """Setup webhook for receiving OpenSign events"""
        from opensign_integration.utils.opensign_client import setup_webhook
        result = setup_webhook()
        
        if result.get("success"):
            self.webhook_id = result.get("webhook_id")
            self.webhook_url = result.get("webhook_url")
            self.save()
            frappe.msgprint(f"Webhook configured successfully!\nURL: {self.webhook_url}")
        
        return result
    
    @frappe.whitelist()
    def refresh_account_info(self):
        """Refresh account information from OpenSign"""
        self.verify_credentials()
        self.save()
        frappe.msgprint("Account information refreshed!")
