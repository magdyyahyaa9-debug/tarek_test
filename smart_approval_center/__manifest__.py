{
    "name": "Smart Approval Center",
    "version": "19.0.1.0.0",
    "category": "Productivity",
    "summary": "Configurable, multi-step employee approval requests",
    "author": "Magdy Yahyaa",
    "license": "LGPL-3",
    "depends": ["base", "mail"],
    "data": [
        "security/approval_security.xml",
        "security/ir.model.access.csv",
        "data/approval_sequence.xml",
        "views/approval_type_views.xml",
        "views/approval_request_views.xml",
        "views/approval_menus.xml",
    ],
    "application": True,
    "installable": True,
}
