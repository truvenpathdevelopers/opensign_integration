// OpenSign Document Client-Side Controller
// =========================================

frappe.ui.form.on('OpenSign Document', {
    refresh: function(frm) {
        // Set indicator color based on status
        frm.set_indicator_formatter('status', function(doc) {
            const status_colors = {
                'Draft': 'grey',
                'Sent': 'blue',
                'In Progress': 'orange',
                'Partially Signed': 'yellow',
                'Completed': 'green',
                'Declined': 'red',
                'Revoked': 'darkgrey',
                'Expired': 'red'
            };
            return status_colors[doc.status] || 'grey';
        });

        // Add action buttons based on status
        if (!frm.is_new()) {
            // Send for Signature button (only for draft documents)
            if (frm.doc.status === 'Draft' && (frm.doc.pdf_file || frm.doc.linked_document)) {
                frm.add_custom_button(__('Send for Signature'), function() {
                    frm.call({
                        method: 'send_for_signature',
                        doc: frm.doc,
                        freeze: true,
                        freeze_message: __('Sending to OpenSign...'),
                        callback: function(r) {
                            if (r.message) {
                                frm.reload_doc();
                            }
                        }
                    });
                }, __('Actions')).addClass('btn-primary');
            }

            // Check Status button (for sent documents)
            if (frm.doc.status && !['Draft', 'Completed', 'Revoked', 'Expired'].includes(frm.doc.status)) {
                frm.add_custom_button(__('Check Status'), function() {
                    frm.call({
                        method: 'check_status',
                        doc: frm.doc,
                        freeze: true,
                        freeze_message: __('Checking status...'),
                        callback: function(r) {
                            frm.reload_doc();
                        }
                    });
                }, __('Actions'));
            }

            // Resend button (for pending signers)
            if (['Sent', 'In Progress', 'Partially Signed'].includes(frm.doc.status)) {
                frm.add_custom_button(__('Resend to Signer'), function() {
                    show_resend_dialog(frm);
                }, __('Actions'));
            }

            // Revoke button
            if (['Sent', 'In Progress', 'Partially Signed'].includes(frm.doc.status)) {
                frm.add_custom_button(__('Revoke Document'), function() {
                    frappe.confirm(
                        __('Are you sure you want to revoke this document? This action cannot be undone.'),
                        function() {
                            frm.call({
                                method: 'revoke',
                                doc: frm.doc,
                                freeze: true,
                                callback: function(r) {
                                    frm.reload_doc();
                                }
                            });
                        }
                    );
                }, __('Actions'));
            }

            // Get Signing Link button
            if (frm.doc.opensign_document_id && frm.doc.status !== 'Completed') {
                frm.add_custom_button(__('Get Signing Link'), function() {
                    frm.call({
                        method: 'get_signing_link',
                        doc: frm.doc,
                        callback: function(r) {
                            if (r.message) {
                                show_signing_link_dialog(r.message);
                            }
                        }
                    });
                }, __('Actions'));
            }

            // View Audit Trail button
            if (frm.doc.opensign_document_id) {
                frm.add_custom_button(__('Audit Trail'), function() {
                    frm.call({
                        method: 'get_audit_trail',
                        doc: frm.doc,
                        freeze: true,
                        callback: function(r) {
                            if (r.message) {
                                show_audit_trail_dialog(r.message);
                            }
                        }
                    });
                }, __('View'));
            }

            // View Signed PDF button
            if (frm.doc.signed_pdf) {
                frm.add_custom_button(__('Signed PDF'), function() {
                    window.open(frm.doc.signed_pdf, '_blank');
                }, __('View'));
            }

            // View Certificate button
            if (frm.doc.completion_certificate) {
                frm.add_custom_button(__('Certificate'), function() {
                    window.open(frm.doc.completion_certificate, '_blank');
                }, __('View'));
            }
        }

        // Add quick links
        if (frm.doc.opensign_document_id) {
            frm.dashboard.add_indicator(
                __('OpenSign ID: {0}', [frm.doc.opensign_document_id]),
                'blue'
            );
        }
    },

    linked_doctype: function(frm) {
        // Clear linked document when doctype changes
        frm.set_value('linked_document', '');
    },

    linked_document: function(frm) {
        // Auto-set title when linked document is selected
        if (frm.doc.linked_document && !frm.doc.document_title) {
            frm.set_value('document_title', `${frm.doc.linked_doctype} - ${frm.doc.linked_document}`);
        }
    }
});

// Child table events for signers
frappe.ui.form.on('OpenSign Signer', {
    signers_add: function(frm, cdt, cdn) {
        // Set default values for new signer
        const settings = frappe.boot.opensign_settings || {};
        frappe.model.set_value(cdt, cdn, 'include_date', settings.include_date_widget || 1);
        frappe.model.set_value(cdt, cdn, 'signature_page', 1);
        frappe.model.set_value(cdt, cdn, 'signature_x', 350);
        frappe.model.set_value(cdt, cdn, 'signature_y', 600 - (frm.doc.signers.length - 1) * 100);
    }
});

// Dialog for resending to specific signer
function show_resend_dialog(frm) {
    const pending_signers = frm.doc.signers.filter(s => s.status === 'Pending');
    
    if (pending_signers.length === 0) {
        frappe.msgprint(__('No pending signers to resend to.'));
        return;
    }

    const dialog = new frappe.ui.Dialog({
        title: __('Resend Signature Request'),
        fields: [
            {
                fieldname: 'signer_email',
                fieldtype: 'Select',
                label: __('Select Signer'),
                options: pending_signers.map(s => s.email).join('\n'),
                reqd: 1
            }
        ],
        primary_action_label: __('Resend'),
        primary_action: function(values) {
            frm.call({
                method: 'resend_to_signer',
                doc: frm.doc,
                args: {
                    email: values.signer_email
                },
                freeze: true,
                callback: function(r) {
                    dialog.hide();
                    frm.reload_doc();
                }
            });
        }
    });
    dialog.show();
}

// Dialog showing signing link
function show_signing_link_dialog(url) {
    const dialog = new frappe.ui.Dialog({
        title: __('Signing Link'),
        fields: [
            {
                fieldname: 'signing_url',
                fieldtype: 'Data',
                label: __('Signing URL'),
                read_only: 1,
                default: url
            },
            {
                fieldname: 'copy_btn',
                fieldtype: 'HTML',
                options: `<button class="btn btn-default btn-sm" onclick="frappe.utils.copy_to_clipboard('${url}')">
                    ${__('Copy to Clipboard')}
                </button>`
            }
        ]
    });
    dialog.show();
}

// Dialog showing audit trail
function show_audit_trail_dialog(data) {
    let html = '<div class="audit-trail">';
    
    // Activity log
    html += '<h4>' + __('Activity Log') + '</h4>';
    html += '<table class="table table-bordered">';
    html += '<thead><tr><th>Event</th><th>Signer</th><th>Time</th><th>IP</th></tr></thead>';
    html += '<tbody>';
    
    data.activity_log.forEach(log => {
        html += `<tr>
            <td>${log.event}</td>
            <td>${log.signer_email || '-'}</td>
            <td>${log.timestamp}</td>
            <td>${log.ip_address || '-'}</td>
        </tr>`;
    });
    
    html += '</tbody></table>';
    
    // Signer IPs
    if (data.signer_ips && Object.keys(data.signer_ips).length > 0) {
        html += '<h4>' + __('Signer IP Addresses') + '</h4>';
        html += '<ul>';
        for (const [email, ip] of Object.entries(data.signer_ips)) {
            html += `<li><strong>${email}:</strong> ${ip}</li>`;
        }
        html += '</ul>';
    }
    
    html += '</div>';

    const dialog = new frappe.ui.Dialog({
        title: __('Audit Trail'),
        fields: [
            {
                fieldname: 'audit_html',
                fieldtype: 'HTML',
                options: html
            }
        ]
    });
    dialog.show();
}
