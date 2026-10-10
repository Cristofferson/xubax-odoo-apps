===========================
eCommerce Tag Filter Groups
===========================

Splits the single "Tags" filter of the Odoo 19 online shop into several filter
blocks with their own titles (Style, Stones, Occasion…).

* New model ``product.tag.group`` (*Website ▸ eCommerce ▸ Products ▸ Tag Filter Groups*) and a
  ``filter_group_id`` field on ``product.tag``.
* The shop sidebar and the *Filters* panel show one block per group; tags without
  a group stay in the standard "Tags" block.
* Search logic: tags of the same group are combined with OR, different groups
  (and the ungrouped tags) with AND — see ``product.template._search_get_detail``.

Tests: ``--test-tags /xb_website_sale_tag_groups``.
