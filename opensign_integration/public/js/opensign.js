/**
 * OpenSign Integration - Main Client-Side Library
 * ================================================
 * 
 * Provides UI components and helper functions for integrating
 * OpenSign digital signatures into any Frappe DocType.
 * 
 * Usage:
 *   opensign.send_for_signature('Sales Invoice', 'INV-00001');
 *   opensign.show_widget_positioner(pdf_url, callback);
 */

frappe.provide("opensign");

// ============================================================================
// MAIN SIGNATURE WORKFLOW
// ============================================================================

/**
 * Send any Frappe document for signature
 * Opens a dialog to collect signer information and sends to OpenSign
 */
opensign.send_for_signature = function(doctype, docname, options = {}) {
    const dialog = new frappe.ui.Dialog({
        title: __('Send for Digital Signature'),
        size: 'large',
        fields: [
            {
                fieldname: 'document_info',
                fieldtype: 'HTML',
                options: `<div class="alert alert-info">
                    <strong>${doctype}:</strong> ${docname}
                </div>`
            },
            {
                fieldname: 'title',
                fieldtype: 'Data',
                label: __('Document Title'),
                default: options.title || `${doctype} - ${docname}`,
                reqd: 1
            },
            {
                fieldname: 'section_signers',
                fieldtype: 'Section Break',
                label: __('Signers')
            },
            {
                fieldname: 'signers',
                fieldtype: 'Table',
                label: __('Signers'),
                cannot_add_rows: false,
                in_place_edit: true,
                data: options.signers || [],
                fields: [
                    {
                        fieldname: 'name',
                        fieldtype: 'Data',
                        label: __('Name'),
                        in_list_view: 1,
                        reqd: 1,
                        columns: 3
                    },
                    {
                        fieldname: 'email',
                        fieldtype: 'Data',
                        label: __('Email'),
                        in_list_view: 1,
                        reqd: 1,
                        columns: 3
                    },
                    {
                        fieldname: 'include_date',
                        fieldtype: 'Check',
                        label: __('Include Date'),
                        in_list_view: 1,
                        default: 1,
                        columns: 2
                    }
                ]
            },
            {
                fieldname: 'section_options',
                fieldtype: 'Section Break',
                label: __('Options'),
                collapsible: 1
            },
            {
                fieldname: 'send_in_order',
                fieldtype: 'Check',
                label: __('Sequential Signing'),
                description: __('Signers must sign in the order listed')
            },
            {
                fieldname: 'expiry_days',
                fieldtype: 'Int',
                label: __('Expiry Days'),
                default: 30,
                description: __('Days until document expires')
            },
            {
                fieldname: 'column_break_opt',
                fieldtype: 'Column Break'
            },
            {
                fieldname: 'use_template',
                fieldtype: 'Check',
                label: __('Use Template'),
                description: __('Use a pre-configured template')
            },
            {
                fieldname: 'template',
                fieldtype: 'Link',
                label: __('Template'),
                options: 'OpenSign Template',
                depends_on: 'use_template'
            }
        ],
        primary_action_label: __('Send for Signature'),
        primary_action: function(values) {
            if (!values.signers || values.signers.length === 0) {
                frappe.msgprint(__('Please add at least one signer'));
                return;
            }

            // Validate signers
            for (let signer of values.signers) {
                if (!signer.name || !signer.email) {
                    frappe.msgprint(__('All signers must have name and email'));
                    return;
                }
                if (!frappe.utils.validate_type(signer.email, 'email')) {
                    frappe.msgprint(__('Invalid email: {0}', [signer.email]));
                    return;
                }
            }

            dialog.hide();

            frappe.call({
                method: 'opensign_integration.utils.opensign_client.send_document_for_signature',
                args: {
                    doctype: doctype,
                    docname: docname,
                    signers: values.signers,
                    title: values.title,
                    send_in_order: values.send_in_order,
                    expiry_days: values.expiry_days
                },
                freeze: true,
                freeze_message: __('Sending to OpenSign...'),
                callback: function(r) {
                    if (r.message && r.message.success) {
                        frappe.show_alert({
                            message: __('Document sent for signature!'),
                            indicator: 'green'
                        });

                        // Show success dialog with details
                        opensign.show_success_dialog(r.message);

                        // Refresh form if we're on it
                        if (cur_frm && cur_frm.doctype === doctype && cur_frm.docname === docname) {
                            cur_frm.reload_doc();
                        }

                        // Callback
                        if (options.callback) {
                            options.callback(r.message);
                        }
                    }
                }
            });
        }
    });

    dialog.show();

    // Pre-populate signers if provided
    if (options.default_signers) {
        options.default_signers.forEach(signer => {
            dialog.fields_dict.signers.df.data.push(signer);
        });
        dialog.fields_dict.signers.grid.refresh();
    }
};

/**
 * Show success dialog after sending document
 */
opensign.show_success_dialog = function(result) {
    const dialog = new frappe.ui.Dialog({
        title: __('Document Sent Successfully'),
        fields: [
            {
                fieldname: 'success_html',
                fieldtype: 'HTML',
                options: `
                    <div class="text-center" style="padding: 20px;">
                        <i class="fa fa-check-circle text-success" style="font-size: 48px;"></i>
                        <h4 style="margin-top: 15px;">${__('Document Sent for Signature')}</h4>
                        <p class="text-muted">${__('Signers will receive email notifications')}</p>
                        <hr>
                        <p><strong>${__('Document ID')}:</strong> ${result.document_id}</p>
                        <p><strong>${__('Tracking Document')}:</strong> 
                            <a href="/app/opensign-document/${result.tracking_document}">${result.tracking_document}</a>
                        </p>
                    </div>
                `
            }
        ],
        primary_action_label: __('View Tracking Document'),
        primary_action: function() {
            frappe.set_route('Form', 'OpenSign Document', result.tracking_document);
            dialog.hide();
        }
    });
    dialog.show();
};

// ============================================================================
// WIDGET POSITIONER - VISUAL PLACEMENT TOOL
// ============================================================================

/**
 * Show widget positioner for visual placement of signature fields
 * 
 * @param {string} pdf_url - URL to the PDF file
 * @param {function} callback - Called with widget positions
 */
opensign.show_widget_positioner = function(pdf_url, callback) {
    const dialog = new frappe.ui.Dialog({
        title: __('Position Signature Widgets'),
        size: 'extra-large',
        fields: [
            {
                fieldname: 'instructions',
                fieldtype: 'HTML',
                options: `
                    <div class="alert alert-info">
                        <strong>${__('Instructions')}:</strong>
                        <ol>
                            <li>${__('Click on the PDF to place signature widgets')}</li>
                            <li>${__('Drag widgets to reposition them')}</li>
                            <li>${__('Use the controls to change page or widget type')}</li>
                        </ol>
                    </div>
                `
            },
            {
                fieldname: 'controls',
                fieldtype: 'HTML',
                options: `
                    <div class="widget-controls" style="margin-bottom: 15px;">
                        <div class="row">
                            <div class="col-md-3">
                                <label>${__('Page')}</label>
                                <input type="number" class="form-control" id="widget-page" value="1" min="1">
                            </div>
                            <div class="col-md-3">
                                <label>${__('Widget Type')}</label>
                                <select class="form-control" id="widget-type">
                                    <option value="signature">${__('Signature')}</option>
                                    <option value="initials">${__('Initials')}</option>
                                    <option value="date">${__('Date')}</option>
                                    <option value="textbox">${__('Text Box')}</option>
                                    <option value="name">${__('Name')}</option>
                                    <option value="email">${__('Email')}</option>
                                </select>
                            </div>
                            <div class="col-md-3">
                                <label>${__('Signer Role')}</label>
                                <input type="text" class="form-control" id="widget-role" placeholder="e.g., Client">
                            </div>
                            <div class="col-md-3">
                                <label>&nbsp;</label>
                                <button class="btn btn-danger btn-block" id="clear-widgets">
                                    ${__('Clear All')}
                                </button>
                            </div>
                        </div>
                    </div>
                `
            },
            {
                fieldname: 'pdf_container',
                fieldtype: 'HTML',
                options: `
                    <div id="pdf-positioner-container" style="border: 1px solid #ccc; min-height: 600px; position: relative; overflow: auto;">
                        <div id="pdf-canvas-wrapper" style="position: relative; display: inline-block;">
                            <canvas id="pdf-canvas"></canvas>
                            <div id="widget-overlay" style="position: absolute; top: 0; left: 0; width: 100%; height: 100%;"></div>
                        </div>
                    </div>
                `
            },
            {
                fieldname: 'widget_list',
                fieldtype: 'HTML',
                options: `
                    <div style="margin-top: 15px;">
                        <h5>${__('Placed Widgets')}</h5>
                        <table class="table table-bordered" id="widget-list-table">
                            <thead>
                                <tr>
                                    <th>${__('Type')}</th>
                                    <th>${__('Role')}</th>
                                    <th>${__('Page')}</th>
                                    <th>${__('X')}</th>
                                    <th>${__('Y')}</th>
                                    <th>${__('Actions')}</th>
                                </tr>
                            </thead>
                            <tbody></tbody>
                        </table>
                    </div>
                `
            }
        ],
        primary_action_label: __('Save Positions'),
        primary_action: function() {
            const widgets = opensign._get_placed_widgets();
            dialog.hide();
            if (callback) {
                callback(widgets);
            }
        }
    });

    dialog.show();

    // Initialize PDF viewer after dialog is shown
    setTimeout(() => {
        opensign._init_pdf_positioner(pdf_url);
    }, 100);
};

/**
 * Initialize PDF positioner with PDF.js
 */
opensign._init_pdf_positioner = function(pdf_url) {
    // Load PDF.js if not already loaded
    if (typeof pdfjsLib === 'undefined') {
        frappe.require([
            'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.min.js'
        ], () => {
            pdfjsLib.GlobalWorkerOptions.workerSrc = 
                'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.4.120/pdf.worker.min.js';
            opensign._load_pdf(pdf_url);
        });
    } else {
        opensign._load_pdf(pdf_url);
    }
};

opensign._placed_widgets = [];
opensign._current_page = 1;
opensign._pdf_doc = null;

opensign._load_pdf = function(pdf_url) {
    const canvas = document.getElementById('pdf-canvas');
    const ctx = canvas.getContext('2d');

    pdfjsLib.getDocument(pdf_url).promise.then(pdf => {
        opensign._pdf_doc = pdf;
        document.getElementById('widget-page').max = pdf.numPages;
        opensign._render_page(1);
    }).catch(err => {
        console.error('Error loading PDF:', err);
        frappe.msgprint(__('Error loading PDF. Please try again.'));
    });

    // Page change handler
    document.getElementById('widget-page').addEventListener('change', function() {
        opensign._render_page(parseInt(this.value));
    });

    // Click handler for placing widgets
    document.getElementById('widget-overlay').addEventListener('click', function(e) {
        const rect = this.getBoundingClientRect();
        const x = Math.round(e.clientX - rect.left);
        const y = Math.round(e.clientY - rect.top);
        
        opensign._add_widget(x, y);
    });

    // Clear button
    document.getElementById('clear-widgets').addEventListener('click', function() {
        opensign._placed_widgets = [];
        opensign._refresh_widget_display();
    });
};

opensign._render_page = function(pageNum) {
    opensign._current_page = pageNum;
    const canvas = document.getElementById('pdf-canvas');
    const ctx = canvas.getContext('2d');

    opensign._pdf_doc.getPage(pageNum).then(page => {
        const scale = 1.5;
        const viewport = page.getViewport({ scale: scale });

        canvas.height = viewport.height;
        canvas.width = viewport.width;

        page.render({
            canvasContext: ctx,
            viewport: viewport
        }).promise.then(() => {
            opensign._refresh_widget_display();
        });
    });
};

opensign._add_widget = function(x, y) {
    const type = document.getElementById('widget-type').value;
    const role = document.getElementById('widget-role').value || 'Signer';
    const page = opensign._current_page;

    // Default sizes based on widget type
    const sizes = {
        signature: { w: 150, h: 50 },
        initials: { w: 60, h: 30 },
        date: { w: 100, h: 20 },
        textbox: { w: 150, h: 20 },
        name: { w: 150, h: 20 },
        email: { w: 200, h: 20 }
    };

    const widget = {
        id: Date.now(),
        type: type,
        role: role,
        page: page,
        x: x,
        y: y,
        w: sizes[type].w,
        h: sizes[type].h
    };

    opensign._placed_widgets.push(widget);
    opensign._refresh_widget_display();
};

opensign._refresh_widget_display = function() {
    const overlay = document.getElementById('widget-overlay');
    const tbody = document.querySelector('#widget-list-table tbody');

    // Clear overlay
    overlay.innerHTML = '';

    // Clear table
    tbody.innerHTML = '';

    // Add widgets for current page
    opensign._placed_widgets.forEach(widget => {
        // Add to overlay if on current page
        if (widget.page === opensign._current_page) {
            const el = document.createElement('div');
            el.className = 'positioned-widget';
            el.style.cssText = `
                position: absolute;
                left: ${widget.x}px;
                top: ${widget.y}px;
                width: ${widget.w}px;
                height: ${widget.h}px;
                border: 2px solid #007bff;
                background: rgba(0, 123, 255, 0.2);
                cursor: move;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 10px;
                color: #007bff;
            `;
            el.textContent = `${widget.type} (${widget.role})`;
            el.dataset.widgetId = widget.id;

            // Make draggable
            el.addEventListener('mousedown', function(e) {
                opensign._start_drag(e, widget);
            });

            overlay.appendChild(el);
        }

        // Add to table
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${widget.type}</td>
            <td>${widget.role}</td>
            <td>${widget.page}</td>
            <td>${widget.x}</td>
            <td>${widget.y}</td>
            <td>
                <button class="btn btn-xs btn-danger" onclick="opensign._remove_widget(${widget.id})">
                    <i class="fa fa-trash"></i>
                </button>
            </td>
        `;
        tbody.appendChild(row);
    });
};

opensign._start_drag = function(e, widget) {
    e.preventDefault();
    const overlay = document.getElementById('widget-overlay');
    const el = overlay.querySelector(`[data-widget-id="${widget.id}"]`);
    
    const startX = e.clientX;
    const startY = e.clientY;
    const origX = widget.x;
    const origY = widget.y;

    function onMouseMove(e) {
        widget.x = origX + (e.clientX - startX);
        widget.y = origY + (e.clientY - startY);
        el.style.left = widget.x + 'px';
        el.style.top = widget.y + 'px';
    }

    function onMouseUp() {
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
        opensign._refresh_widget_display();
    }

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
};

opensign._remove_widget = function(id) {
    opensign._placed_widgets = opensign._placed_widgets.filter(w => w.id !== id);
    opensign._refresh_widget_display();
};

opensign._get_placed_widgets = function() {
    return opensign._placed_widgets.map(w => ({
        type: w.type,
        role: w.role,
        page: w.page,
        x: Math.round(w.x / 1.5),  // Convert back from scale
        y: Math.round(w.y / 1.5),
        w: Math.round(w.w / 1.5),
        h: Math.round(w.h / 1.5)
    }));
};

// ============================================================================
// MULTI-SIGNER WORKFLOW
// ============================================================================

/**
 * Create a multi-signer document with sequential or parallel signing
 */
opensign.create_multi_signer_document = function(options) {
    const dialog = new frappe.ui.Dialog({
        title: __('Multi-Signer Document'),
        size: 'extra-large',
        fields: [
            {
                fieldname: 'pdf_file',
                fieldtype: 'Attach',
                label: __('PDF Document'),
                reqd: 1
            },
            {
                fieldname: 'title',
                fieldtype: 'Data',
                label: __('Document Title'),
                reqd: 1
            },
            {
                fieldname: 'section_workflow',
                fieldtype: 'Section Break',
                label: __('Signing Workflow')
            },
            {
                fieldname: 'workflow_type',
                fieldtype: 'Select',
                label: __('Workflow Type'),
                options: [
                    { value: 'parallel', label: __('Parallel - All sign simultaneously') },
                    { value: 'sequential', label: __('Sequential - Sign in order') }
                ],
                default: 'parallel'
            },
            {
                fieldname: 'workflow_html',
                fieldtype: 'HTML',
                options: `
                    <div class="workflow-description">
                        <p><strong>${__('Parallel')}:</strong> ${__('All signers receive the document at the same time and can sign in any order.')}</p>
                        <p><strong>${__('Sequential')}:</strong> ${__('Signers receive the document one at a time, in the order specified. Each signer must complete before the next receives the document.')}</p>
                    </div>
                `
            },
            {
                fieldname: 'section_signers',
                fieldtype: 'Section Break',
                label: __('Signers (drag to reorder for sequential signing)')
            },
            {
                fieldname: 'signers',
                fieldtype: 'Table',
                label: __('Signers'),
                data: [],
                fields: [
                    {
                        fieldname: 'order',
                        fieldtype: 'Int',
                        label: __('#'),
                        in_list_view: 1,
                        columns: 1,
                        read_only: 1
                    },
                    {
                        fieldname: 'name',
                        fieldtype: 'Data',
                        label: __('Name'),
                        in_list_view: 1,
                        reqd: 1,
                        columns: 2
                    },
                    {
                        fieldname: 'email',
                        fieldtype: 'Data',
                        label: __('Email'),
                        in_list_view: 1,
                        reqd: 1,
                        columns: 3
                    },
                    {
                        fieldname: 'role',
                        fieldtype: 'Data',
                        label: __('Role'),
                        in_list_view: 1,
                        columns: 2,
                        default: 'Signer'
                    },
                    {
                        fieldname: 'signature_page',
                        fieldtype: 'Int',
                        label: __('Page'),
                        in_list_view: 1,
                        columns: 1,
                        default: 1
                    }
                ]
            },
            {
                fieldname: 'section_options',
                fieldtype: 'Section Break',
                label: __('Additional Options'),
                collapsible: 1
            },
            {
                fieldname: 'expiry_days',
                fieldtype: 'Int',
                label: __('Expiry Days'),
                default: 30
            },
            {
                fieldname: 'include_date_widget',
                fieldtype: 'Check',
                label: __('Include Date Widget'),
                default: 1
            },
            {
                fieldname: 'column_break_opt',
                fieldtype: 'Column Break'
            },
            {
                fieldname: 'reminder_days',
                fieldtype: 'Int',
                label: __('Send Reminder After (days)'),
                default: 3
            },
            {
                fieldname: 'custom_message',
                fieldtype: 'Small Text',
                label: __('Custom Message to Signers')
            }
        ],
        primary_action_label: __('Send Document'),
        primary_action: function(values) {
            if (!values.pdf_file) {
                frappe.msgprint(__('Please upload a PDF file'));
                return;
            }
            
            if (!values.signers || values.signers.length === 0) {
                frappe.msgprint(__('Please add at least one signer'));
                return;
            }

            dialog.hide();

            // Calculate Y positions for each signer
            let y_offset = 600;
            const signers_with_positions = values.signers.map((signer, idx) => {
                const result = {
                    name: signer.name,
                    email: signer.email,
                    role: signer.role || `Signer ${idx + 1}`,
                    widgets: [
                        {
                            type: 'signature',
                            page: signer.signature_page || 1,
                            x: 350,
                            y: y_offset,
                            w: 150,
                            h: 50,
                            options: { hint: `Signature for ${signer.role || signer.name}` }
                        }
                    ]
                };

                if (values.include_date_widget) {
                    result.widgets.push({
                        type: 'date',
                        page: signer.signature_page || 1,
                        x: 350,
                        y: y_offset - 60,
                        w: 100,
                        h: 20,
                        options: { signing_date: true, format: 'mm/dd/yyyy' }
                    });
                }

                y_offset -= 120;
                return result;
            });

            frappe.call({
                method: 'opensign_integration.utils.opensign_client.send_document_for_signature',
                args: {
                    doctype: null,
                    docname: null,
                    signers: signers_with_positions,
                    title: values.title,
                    send_in_order: values.workflow_type === 'sequential',
                    expiry_days: values.expiry_days
                },
                freeze: true,
                freeze_message: __('Creating multi-signer document...'),
                callback: function(r) {
                    if (r.message && r.message.success) {
                        opensign.show_success_dialog(r.message);
                    }
                }
            });
        }
    });

    dialog.show();

    // Update order numbers when rows change
    dialog.$wrapper.on('change', function() {
        const grid = dialog.fields_dict.signers.grid;
        grid.data.forEach((row, idx) => {
            row.order = idx + 1;
        });
        grid.refresh();
    });
};

// ============================================================================
// TEMPLATE-BASED DOCUMENT GENERATION
// ============================================================================

/**
 * Create a document from an existing template
 */
opensign.create_from_template = function(template_name) {
    frappe.call({
        method: 'frappe.client.get',
        args: {
            doctype: 'OpenSign Template',
            name: template_name
        },
        callback: function(r) {
            if (r.message) {
                opensign._show_template_dialog(r.message);
            }
        }
    });
};

opensign._show_template_dialog = function(template) {
    let roles = [];
    try {
        roles = JSON.parse(template.roles || '[]');
    } catch (e) {
        roles = [];
    }

    // Build signer fields for each role
    const signer_fields = [];
    roles.forEach((role, idx) => {
        signer_fields.push({
            fieldname: `section_${idx}`,
            fieldtype: 'Section Break',
            label: role
        });
        signer_fields.push({
            fieldname: `name_${idx}`,
            fieldtype: 'Data',
            label: __('Name'),
            reqd: 1
        });
        signer_fields.push({
            fieldname: `email_${idx}`,
            fieldtype: 'Data',
            label: __('Email'),
            reqd: 1,
            options: 'Email'
        });
        signer_fields.push({
            fieldname: `column_break_${idx}`,
            fieldtype: 'Column Break'
        });
        signer_fields.push({
            fieldname: `phone_${idx}`,
            fieldtype: 'Data',
            label: __('Phone')
        });
    });

    const dialog = new frappe.ui.Dialog({
        title: __('Create Document from Template: {0}', [template.template_title]),
        fields: [
            {
                fieldname: 'template_info',
                fieldtype: 'HTML',
                options: `
                    <div class="alert alert-info">
                        <strong>${__('Template')}:</strong> ${template.template_title}<br>
                        <strong>${__('Roles')}:</strong> ${roles.join(', ')}
                    </div>
                `
            },
            {
                fieldname: 'document_title',
                fieldtype: 'Data',
                label: __('Document Title'),
                default: `${template.template_title} - ${frappe.datetime.now_date()}`
            },
            ...signer_fields
        ],
        primary_action_label: __('Create & Send'),
        primary_action: function(values) {
            // Build signers array from form values
            const signers = roles.map((role, idx) => ({
                name: values[`name_${idx}`],
                email: values[`email_${idx}`],
                phone: values[`phone_${idx}`],
                role: role
            }));

            // Validate
            for (let signer of signers) {
                if (!signer.name || !signer.email) {
                    frappe.msgprint(__('Please fill in all signer details'));
                    return;
                }
            }

            dialog.hide();

            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'OpenSign Template',
                    filters: { name: template.name },
                    fieldname: 'opensign_template_id'
                },
                callback: function(r) {
                    if (r.message && r.message.opensign_template_id) {
                        // Use template API
                        frappe.call({
                            method: 'opensign_integration.utils.opensign_client.create_document_from_template',
                            args: {
                                template_id: r.message.opensign_template_id,
                                signers: signers,
                                title: values.document_title
                            },
                            freeze: true,
                            freeze_message: __('Creating document from template...'),
                            callback: function(r) {
                                if (r.message && r.message.success) {
                                    opensign.show_success_dialog(r.message);
                                }
                            }
                        });
                    } else {
                        frappe.msgprint(__('Template not yet created in OpenSign. Please create it first.'));
                    }
                }
            });
        }
    });

    dialog.show();
};

/**
 * Show template selector dialog
 */
opensign.select_template = function(callback) {
    const dialog = new frappe.ui.Dialog({
        title: __('Select Template'),
        fields: [
            {
                fieldname: 'template',
                fieldtype: 'Link',
                label: __('Template'),
                options: 'OpenSign Template',
                reqd: 1,
                get_query: function() {
                    return {
                        filters: {
                            opensign_template_id: ['!=', '']
                        }
                    };
                }
            }
        ],
        primary_action_label: __('Use Template'),
        primary_action: function(values) {
            dialog.hide();
            if (callback) {
                callback(values.template);
            } else {
                opensign.create_from_template(values.template);
            }
        }
    });
    dialog.show();
};

// ============================================================================
// FORM INTEGRATION - Add buttons to any DocType
// ============================================================================

/**
 * Add OpenSign button to a form
 * Call this in the refresh event of any DocType
 */
opensign.add_signature_button = function(frm, options = {}) {
    if (frm.doc.docstatus === 1 || options.show_always) {
        frm.add_custom_button(__('Send for Signature'), function() {
            opensign.send_for_signature(frm.doctype, frm.doc.name, {
                title: options.title || `${frm.doctype} - ${frm.doc.name}`,
                default_signers: options.signers,
                callback: options.callback
            });
        }, options.group || __('Actions'));
    }
};

/**
 * Check if document has pending signatures
 */
opensign.check_signature_status = function(doctype, docname, callback) {
    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'OpenSign Document',
            filters: {
                linked_doctype: doctype,
                linked_document: docname
            },
            fields: ['name', 'status', 'opensign_document_id']
        },
        callback: function(r) {
            if (callback) {
                callback(r.message || []);
            }
        }
    });
};

// ============================================================================
// INITIALIZATION
// ============================================================================

$(document).ready(function() {
    // Add OpenSign to navbar if settings exist
    frappe.call({
        method: 'frappe.client.get_count',
        args: {
            doctype: 'OpenSign Settings'
        },
        callback: function(r) {
            if (r.message > 0) {
                // OpenSign is configured
                console.log('OpenSign Integration loaded');
            }
        }
    });
});
