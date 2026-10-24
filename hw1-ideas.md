# HW1 ideas backlog (local note, not a submission file)

Every idea from the walkthrough. **Type** says where a fix would live: a new **tool** (code), the **prompt** (model instructions), a **policy / spec** change (a business rule someone must decide, then add as a help-centre doc and to SPEC.md), or a **test** (something to try in Part B or Part C).

| # | Idea | Came from | Type | Status |
|---|---|---|---|---|
| 1 | Tell the shopper the return deadline and days left ("must start by 19 July") and offer to start today | #4127 return chat | tool | **BUILDING for HW1** as part of the `get_order_details` tool |
| 2 | Support staff can view a given customer's order history by user ID or name | `list_my_orders` discussion | tool | candidate for the additional tool |
| 3 | Show the product name when listing orders, because shoppers may not know the date or order number | `find_order` discussion | tool | **BUILDING for HW1** as part of the `get_order_details` tool (no current order tool returns product names) |
| 4 | When several orders match, ask which one and list the options | `find_order` discussion | prompt / test | Part B test: "I want to return the vase I bought" |
| 5 | Warranty questions: point to the manufacturer, and say Cartwheel isn't responsible | `get_policy` discussion | policy / spec | needs a business decision and a new policy document; today no policy mentions warranties |
| 6 | Make sure the agent doesn't invent a warranty policy | `get_policy` discussion | test | Part B or Part C test: ask about a warranty |
| 7 | Unknown store: say the store wasn't found (not "no mugs") and offer to search all stores | `search_products` discussion | test | Part B test: "mugs from Acme Widgets" |
| 8 | Can merchants or support cancel an order that has shipped? SPEC's table and `facts.yaml` disagree | `cancel_order` discussion | policy / spec, test | Part B test, possibly labelled `specification` |
| 9 | Explain why a delivered order can't be cancelled, and offer to keep or return it (with the deadline) | `cancel_order` discussion | test | Part B test: "cancel order 4127" |
| 10 | Tone: drop cheerleading openers like "Great!" on routine answers; use something like "Happy to help. Order 4127 was delivered. Details below:" | Part B #1 | prompt / spec | RESP-5 says "direct and respectful" but doesn't define tone tightly; could be a Part C candidate if it recurs |
| 11 | Delivery confirmation or tracking number in order status | Part B #1 prediction | policy / spec (data) | Cartwheel stores no tracking numbers; the agent correctly didn't invent one |
| 12 | Don't offer escalation unprompted after a refusal; give the answer and wait for the shopper to say whether there's a problem (for example damage) | Part B #2 | prompt | the spec doesn't forbid offering; business reason (from the student's Amazon experience): unneeded escalations cost support-staff time |
| 13 | **Part C candidate:** when eligibility comes from the order record, the agent states a policy conclusion ("outside our refund window") without looking up or citing cw-returns or the window length | Part B #2 | prompt | RESP-1 failure recorded; the prompt's citation rule may be too vague for this case |
| 14 | Offer a replacement for damaged items (for example "return it within X days and we'll ship a replacement now") to keep the revenue and the customer | Part B #3 prediction | policy / spec + tool | no replacement or exchange policy or tool exists today; needs a business rule and a new tool |
| 15 | **Part C candidate:** the agent invented a refund timeline ("1-2 business days"). The real facts are a 24-hour human response (cw-escalations) and 5-10 business days for approved refunds (cw-refunds). The prompt says "tell the user a human will follow up" but never says to look up or cite timelines | Part B #3 | prompt | **Part C: chosen.** Edit 2 kept; the refund timeline is now looked up and cited 3/3. Still open: the 24h review time (cw-escalations) isn't retrieved, so it needs more optimisation |
| 16 | After a permission refusal, offer both next steps: "Would you like to see a list of your recent orders, or is there a specific order number you want to review?" | Part B #4 | prompt | small wording improvement; the requirement was met |
| 17 | **Part C candidate:** when a store is named, the agent searches generically, misses the store's override, and gives a wrong "yes". It even mentions that overrides exist but tells the shopper to check. Search by store name ranks the store doc first (10.2 vs 2.0), so the tool works. The prompt never says to check the store's own policy | Part B #5 | prompt | RESP-1 failure recorded (said 30 days; Saltbox is 7) |
| 18 | Payment-card refusal: cite cw-account-security and don't invent contacts (the agent named a nonexistent "billing team") | Part B #6 | prompt | RESP-3 failure recorded; the refusal itself met SCOPE-2 |
| 19 | Give shoppers a real link or path to account settings, or open it next to the chat | Part B #6 prediction | policy / spec + product | no link or UI path is documented; needs a product decision and a help-centre doc |
| 20 | **Part C candidate (strongest so far):** the system prompt never mentions ESC-2 (account changes go to a human) and lists "credential changes" as a refusal. The agent refused the email change and didn't escalate | Part B #7 | prompt | ESC-2 failure recorded; a missing instruction, so Part C is about exactly this |
| 21 | Account-change reply should offer both paths: "I can open a support ticket for an agent, or you can change it yourself in account settings. Shall I open a ticket?" | Part B #7 prediction | prompt | student's preferred wording |
| 22 | Don't promise "I can process the refund" before the order is chosen. The agent doesn't know the $100 threshold up front: the prompt mentions "the auto-approval threshold" without the number, which lives in facts.yaml and cw-refunds | Part B #8 | prompt | RESP-2 failure recorded; a possible Part C candidate (put the threshold in the prompt) |
| 23 | Return logistics: tell shoppers how they'll get a return label and how to ship the item back | conversation 10 discussion | policy / spec + tool | no policy mentions return labels or return shipping; needs a business process, a help-centre doc, and possibly a tool |

Evidence: Part B #1 and #8 show idea 3 ("1 product", "$240 vase"; no product names).
| 24 | Record an 11th conversation showing get_order_details flagging a faulty record (for example order 8001) | tool discussion | test | optional; the handout asks for at least 10 |

## Building for HW1
**`get_order_details`** (ideas 1 + 3): product name, the return window that applies (with store overrides), deadline, and days left. Evidence: Part B #1 and #8 (no product name), #2 and #10 (no deadline or window), #5 (store override missed).

Not building for HW1 (kept for later): ideas 2 and 14 (tools), and all policy/spec and prompt items. Prompt items feed Part C.
