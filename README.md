# Smart Approval Center (Odoo 19)

A standalone module in `smart_approval_center/` supporting configurable approval chains.

## Included
- Approval requests for expenses, purchases, advances, or general requests
- Ordered approvers per request type, snapshotted when submitted
- Amount validation and optional min/max limits
- Todo activities for the active approver
- Chatter history and searchable list views
- Dedicated Approval User / Approval Manager security groups

## Install
Add the `smart_approval_center` directory to your Odoo 19 addons path. Update the Apps list, install **Smart Approval Center**, and assign the approval access groups to users. Create an Approval Type with one or more approval steps before submitting requests. Every assigned approver needs the Approval User group.

## Scope
This first version manages approval requests only; it does not automatically create purchases, journal entries, or loans. Validate installation and permissions in an Odoo 19 staging database before production use.
